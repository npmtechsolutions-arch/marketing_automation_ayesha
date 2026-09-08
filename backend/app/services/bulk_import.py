"""Bulk-importing posts from a CSV.

Two phases, deliberately. The first parses and validates and writes nothing;
the second creates. A spreadsheet of fifty posts is exactly the input where a
column is misnamed or a platform is misspelt, and discovering that after
fifteen rows have been created leaves a mess only the user can untangle.

The validation is the same code the composer uses, not a second implementation.
A CSV row is turned into an unsaved ``Post`` and handed to
``post_validation.validate_post`` -- so an import cannot accept content the
composer would reject, and neither can drift from the other.

Quota is taken as **one reservation** for the whole importable set. Fifty
separate increments would let a concurrent import interleave and take a
workspace over its allowance, and would leave a partial spend behind if the
run failed halfway.
"""

import csv
import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.platform import SocialAccount, SocialPlatform
from app.models.post import Post, PostStatus
from app.models.post_variant import PostVariant
from app.services import post_validation, recurrence
from app.services.dashboard import workspace_timezone

logger = logging.getLogger(__name__)

# Columns the template documents. Extra columns are ignored rather than
# refused: a spreadsheet exported from somewhere else usually carries a few,
# and rejecting the file for them would be unhelpful.
COLUMNS = ("content", "scheduled_at", "platforms", "media_urls", "link")
REQUIRED_COLUMNS = ("content",)

# An upper bound on one file. Chosen to be larger than any plausible month of
# posting and small enough that a run stays inside one request.
MAX_ROWS = 500

# Separators accepted inside the list columns. Comma first, but a comma is also
# what separates CSV fields, so anyone who has fought a spreadsheet will reach
# for a pipe or a semicolon.
LIST_SEPARATORS = ("|", ";", ",")

def template(tz=None, connected: Optional[list[str]] = None) -> str:
    """The example file, with dates in the near future.

    Generated rather than hard-coded because a template with fixed dates goes
    stale: downloading it and uploading it straight back -- the obvious first
    thing to try -- then fails every row on "that date is in the past", which
    is a poor first impression of a validator that is otherwise right.

    Platforms come from what the workspace has actually connected, for the same
    reason: an example naming a platform the user has not connected teaches
    them the importer is broken rather than that the row needs editing.
    """
    today = datetime.now(tz).date() if tz else datetime.now().date()
    first = today + timedelta(days=3)
    second = today + timedelta(days=5)
    available = [slug for slug in (connected or []) if slug] or ["instagram"]
    primary = "|".join(available[:2])
    secondary = available[0]

    return (
        "content,scheduled_at,platforms,media_urls,link\n"
        f'"Your post text. Wrap it in quotes if it contains a comma.",'
        f"{first} 09:00,{primary},https://example.com/photo.jpg,"
        "https://example.com/landing\n"
        f'"A second post, scheduled later.",{second} 14:30,{secondary},,'
        "https://example.com/blog\n"
        '"A draft. Leave scheduled_at empty and it imports as a draft.",,'
        f"{secondary},,\n"
    )


class ImportError_(ValueError):
    """The file itself is unusable, as opposed to a row within it."""


@dataclass
class RowResult:
    """One CSV row, and what we make of it."""

    row_number: int          # 1-based, counting the header as row 1
    content: str = ""
    scheduled_at_local: Optional[str] = None
    platforms: list[str] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)
    link: Optional[str] = None

    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    resolved_accounts: list[uuid.UUID] = field(default_factory=list)
    run_at: Optional[datetime] = None

    @property
    def importable(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "row_number": self.row_number,
            "content": self.content[:280],
            "scheduled_at_local": self.scheduled_at_local,
            "platforms": self.platforms,
            "media_urls": self.media_urls,
            "link": self.link,
            "errors": self.errors,
            "warnings": self.warnings,
            "importable": self.importable,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "target_count": len(self.resolved_accounts),
        }


def _problem(field_name: str, message: str) -> dict:
    return {"field": field_name, "message": message}


def _split_list(raw: str) -> list[str]:
    """Split a list cell on whichever separator it actually uses."""
    text = (raw or "").strip()
    if not text:
        return []
    for separator in LIST_SEPARATORS:
        if separator in text:
            return [part.strip() for part in text.split(separator) if part.strip()]
    return [text]


def parse_csv(raw: bytes) -> list[dict[str, str]]:
    """Rows as dicts, with the header normalised.

    ``utf-8-sig`` because Excel writes a byte-order mark, and without it the
    first column arrives named ``\\ufeffcontent`` and every row looks like it is
    missing its content.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            # Excel on Windows still writes cp1252 for non-ASCII.
            text = raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ImportError_(
                "The file is not readable as text. Save it as CSV (UTF-8)."
            ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportError_("The file is empty.")

    # Case- and space-insensitive headers: "Scheduled At" and "scheduled_at"
    # are the same intent, and a spreadsheet round trip often changes one into
    # the other.
    normalised = {
        (name or "").strip().lower().replace(" ", "_"): name
        for name in reader.fieldnames
    }
    missing = [c for c in REQUIRED_COLUMNS if c not in normalised]
    if missing:
        raise ImportError_(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected: {', '.join(COLUMNS)}. Download the template to compare."
        )

    rows = []
    for row in reader:
        rows.append(
            {key: (row.get(source) or "") for key, source in normalised.items()}
        )
        if len(rows) > MAX_ROWS:
            raise ImportError_(
                f"That file has more than {MAX_ROWS} rows. Split it and import "
                "in batches."
            )
    return rows


async def _connected_by_platform(
    db: AsyncSession, account_id: uuid.UUID
) -> dict[str, list[uuid.UUID]]:
    """Every active connection in the workspace, keyed by platform slug."""
    rows = (
        await db.execute(
            select(SocialAccount.id, SocialPlatform.slug)
            .join(SocialPlatform, SocialPlatform.id == SocialAccount.platform_id)
            .where(
                SocialAccount.account_id == account_id,
                SocialAccount.is_active.is_(True),
            )
        )
    ).all()
    grouped: dict[str, list[uuid.UUID]] = {}
    for row in rows:
        grouped.setdefault((row.slug or "").lower(), []).append(row.id)
    return grouped


def _parse_when(raw: str) -> tuple[Optional[datetime], Optional[str]]:
    """A naive local datetime from a spreadsheet cell, or an explanation.

    Naive on purpose, and resolved against the workspace's timezone later --
    the same contract the composer and recurring schedules use. A spreadsheet
    has no notion of timezone, so interpreting its times as UTC would silently
    move every import for any workspace that is not in UTC.
    """
    text = (raw or "").strip()
    if not text:
        return None, None

    for fmt in (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt), None
        except ValueError:
            continue

    return None, (
        f"'{text}' is not a date and time we recognise. Use "
        "YYYY-MM-DD HH:MM, e.g. 2026-04-01 09:00. Leave it empty to import as "
        "a draft."
    )


def _build_transient_post(
    account: Account, row: RowResult, user_id: uuid.UUID
) -> Post:
    """An unsaved Post, purely so the composer's validator can read it.

    Never added to the session. Building one is what lets the import reuse
    validation rather than reimplement the character limits, media rules and
    per-platform capabilities that 1.7 established.
    """
    post = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        account_id=account.id,
        content=row.content,
        media_urls=list(row.media_urls),
        target_accounts=[
            {"social_account_id": str(value)} for value in row.resolved_accounts
        ],
        status=PostStatus.DRAFT,
    )
    # Transient instances return the empty collection without querying, which
    # is what keeps this safe to build outside a flush.
    post.variants = []
    return post


async def analyse(
    db: AsyncSession,
    account: Account,
    raw: bytes,
    *,
    user_id: uuid.UUID,
) -> dict:
    """Parse and validate a file. Writes nothing and spends no quota."""
    rows = parse_csv(raw)
    if not rows:
        raise ImportError_("The file has a header but no rows.")

    connected = await _connected_by_platform(db, account.id)
    tz = workspace_timezone(account)
    now = datetime.now(timezone.utc)

    results: list[RowResult] = []
    for index, raw_row in enumerate(rows, start=2):  # row 1 is the header
        result = RowResult(row_number=index)
        result.content = (raw_row.get("content") or "").strip()
        result.link = (raw_row.get("link") or "").strip() or None
        result.media_urls = _split_list(raw_row.get("media_urls", ""))
        result.platforms = [p.lower() for p in _split_list(raw_row.get("platforms", ""))]
        result.scheduled_at_local = (raw_row.get("scheduled_at") or "").strip() or None

        if not result.content:
            result.errors.append(_problem("content", "This row has no content."))

        # --- when -------------------------------------------------------
        when, when_error = _parse_when(raw_row.get("scheduled_at", ""))
        if when_error:
            result.errors.append(_problem("scheduled_at", when_error))
        elif when is not None:
            result.run_at = recurrence.to_utc(when, tz)
            if result.run_at <= now:
                result.errors.append(
                    _problem(
                        "scheduled_at",
                        f"{result.scheduled_at_local} is in the past for this "
                        f"workspace ({tz.key}).",
                    )
                )

        # --- platforms --------------------------------------------------
        if not result.platforms:
            result.errors.append(
                _problem("platforms", "Name at least one platform to publish to.")
            )
        for slug in result.platforms:
            matches = connected.get(slug)
            if not matches:
                result.errors.append(
                    _problem(
                        "platforms",
                        f"No connected {slug} account in this workspace."
                        if slug in {"instagram", "facebook", "linkedin", "twitter", "youtube"}
                        else f"'{slug}' is not a platform we publish to.",
                    )
                )
            else:
                result.resolved_accounts.extend(matches)

        # --- the composer's own rules -----------------------------------
        if result.resolved_accounts and result.content:
            report = await post_validation.validate_post(
                db, _build_transient_post(account, result, user_id),
                account_id=account.id,
            )
            for problem in report.get("errors", []):
                target = result.errors if problem.get("severity") == "error" else result.warnings
                target.append(
                    {
                        "field": f"{problem.get('platform') or 'post'}."
                                 f"{problem.get('field') or 'content'}",
                        "message": problem.get("message", ""),
                    }
                )

        results.append(result)

    importable = [r for r in results if r.importable]
    return {
        "rows": [r.as_dict() for r in results],
        "total": len(results),
        "importable": len(importable),
        "rejected": len(results) - len(importable),
        "scheduled": sum(1 for r in importable if r.run_at),
        "drafts": sum(1 for r in importable if not r.run_at),
        "timezone": tz.key,
        "_results": results,
    }


async def create(
    db: AsyncSession,
    account: Account,
    results: list[RowResult],
    *,
    user_id: uuid.UUID,
) -> list[Post]:
    """Create the importable rows. Quota must already be reserved."""
    from app.services import publishing

    created: list[Post] = []
    for result in results:
        if not result.importable:
            continue

        post = Post(
            id=uuid.uuid4(),
            user_id=user_id,
            account_id=account.id,
            content=result.content,
            media_urls=list(result.media_urls) or None,
            target_accounts=[
                {"social_account_id": str(value)} for value in result.resolved_accounts
            ],
            status=PostStatus.SCHEDULED if result.run_at else PostStatus.DRAFT,
            scheduled_at=result.run_at,
        )
        db.add(post)
        await db.flush()

        if result.link:
            # Post has no link column; PostVariant.link_url is where a link
            # lives. One variant per platform, carrying only the link, so the
            # text still tracks the master post.
            for slug in dict.fromkeys(result.platforms):
                db.add(
                    PostVariant(
                        id=uuid.uuid4(),
                        post_id=post.id,
                        platform_slug=slug,
                        link_url=result.link,
                    )
                )

        if result.run_at:
            await publishing.create_jobs_for_post(db, post, run_at=result.run_at)

        created.append(post)

    await db.flush()
    return created


async def connected_slugs(db: AsyncSession, account_id: uuid.UUID) -> list[str]:
    """Platform slugs this workspace has connected, for the template."""
    grouped = await _connected_by_platform(db, account_id)
    return sorted(grouped)
