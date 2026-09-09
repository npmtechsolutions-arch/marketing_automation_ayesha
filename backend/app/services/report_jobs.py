"""Creating, generating and scheduling reports.

Generation runs in the worker. A quarter's aggregation plus three renders is
seconds of work, and a request holding the connection for it dies behind a
proxy long before it finishes -- so the endpoint creates a PENDING row and
returns, and the worker picks it up.

Scheduled reports are made idempotent by the period rather than by a
``next_run_at``. "Has a monthly report for August already been made?" is a
question the reports table can answer exactly; a stored next-run timestamp can
drift, be missed while a worker is down, or fire twice after a restart, and
each of those puts a duplicate report in front of a customer.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.campaign import Campaign
from app.models.notification import Notification
from app.models.report import Report, ReportFormat, ReportStatus, ReportType
from app.services import entitlement_service as ent
from app.services import report_render, reporting, storage
from app.services.dashboard import workspace_timezone

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60

# Cadences a workspace can switch on, stored on its settings blob beside the
# timezone and the approval flags.
CADENCE_KEY = "reports_cadence"
CADENCES = {"off": None, "weekly": ReportType.WEEKLY, "monthly": ReportType.MONTHLY}

FORMATS = (ReportFormat.CSV, ReportFormat.XLSX, ReportFormat.PDF)


def storage_key(report: Report, fmt: ReportFormat) -> str:
    """Where a rendered file lives.

    Prefixed by workspace so a bucket policy can be written per tenant, and by
    the report id so regenerating overwrites its own files rather than
    accumulating orphans.
    """
    return f"reports/{report.account_id}/{report.id}.{fmt.value}"


async def white_label_allowed(db: AsyncSession, account_id: uuid.UUID) -> bool:
    organization = await ent.get_organization_for_account(db, account_id)
    return bool(await ent.get_limit(db, organization, ent.WHITE_LABEL))


async def create(
    db: AsyncSession,
    account: Account,
    *,
    report_type: ReportType,
    created_by: Optional[uuid.UUID] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    branding: Optional[dict] = None,
    title: Optional[str] = None,
    campaign_id: Optional[uuid.UUID] = None,
) -> Report:
    """Queue a report. Does not generate it.

    ``campaign_id`` scopes the report to one campaign; the caller is
    responsible for having checked that the campaign belongs to this workspace.
    """
    period = reporting.resolve_period(
        report_type, account=account, start=start, end=end
    )

    # Branding is resolved and frozen here rather than at render time. A
    # customer who rebrands next month should not find last month's PDF has
    # changed colours, and one whose plan lapses should not lose branding on a
    # file they already paid for.
    entitled = await white_label_allowed(db, account.id)
    resolved = reporting.sanitise_branding(branding, entitled=entitled)

    report = Report(
        id=uuid.uuid4(),
        account_id=account.id,
        created_by=created_by,
        type=report_type,
        title=title or f"{account.name} — {period.label}",
        period_start=period.start,
        period_end=period.end,
        status=ReportStatus.PENDING,
        branding=resolved,
        campaign_id=campaign_id,
    )
    db.add(report)
    await db.flush()
    return report


async def already_reported(
    db: AsyncSession, account_id: uuid.UUID, report_type: ReportType, start: date
) -> bool:
    """Whether this workspace already has a report for this exact period."""
    existing = (
        await db.execute(
            select(Report.id).where(
                Report.account_id == account_id,
                Report.type == report_type,
                Report.period_start == start,
                Report.status != ReportStatus.FAILED,
            ).limit(1)
        )
    ).scalar_one_or_none()
    return existing is not None


async def generate(db: AsyncSession, report: Report) -> Report:
    """Aggregate, render every format we can, store, and notify."""
    account = (
        await db.execute(select(Account).where(Account.id == report.account_id))
    ).scalar_one_or_none()
    if account is None:
        report.status = ReportStatus.FAILED
        report.error = "The workspace no longer exists."
        return report

    report.status = ReportStatus.GENERATING
    await db.flush()

    period = reporting.Period(
        report.period_start, report.period_end, report.title or ""
    )
    branding = report.branding or reporting.DEFAULT_BRANDING

    campaign = None
    if report.campaign_id is not None:
        campaign = (
            await db.execute(
                select(Campaign).where(Campaign.id == report.campaign_id)
            )
        ).scalar_one_or_none()
        if campaign is None:
            # The campaign was deleted after the report was queued. The FK is
            # SET NULL, so this is only reachable inside the same transaction
            # as a delete -- but failing loudly beats silently widening the
            # report to the whole workspace under a campaign's title.
            report.status = ReportStatus.FAILED
            report.error = "The campaign this report covers no longer exists."
            return report

    try:
        if campaign is not None:
            payload = await reporting.aggregate_campaign(
                db, account, period, campaign
            )
        else:
            payload = await reporting.aggregate(db, account, period)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Report %s failed to aggregate", report.id)
        report.status = ReportStatus.FAILED
        report.error = f"Could not gather the numbers: {type(exc).__name__}: {exc}"[:500]
        return report

    backend = storage.get_storage()
    keys: dict[str, str] = {}
    skipped: list[str] = []

    for fmt in FORMATS:
        try:
            body = report_render.RENDERERS[fmt](payload, branding)
            key = storage_key(report, fmt)
            backend.put_object(
                key, body, content_type=report_render.CONTENT_TYPES[fmt]
            )
            keys[fmt.value] = key
        except Exception as exc:  # noqa: BLE001
            # One format failing does not fail the report. A PDF is unavailable
            # on a host without pango; the CSV and the workbook are still worth
            # having, and a format absent from file_keys is the honest record.
            skipped.append(fmt.value)
            logger.warning(
                "Report %s: %s could not be rendered (%s)", report.id, fmt.value, exc
            )

    if not keys:
        report.status = ReportStatus.FAILED
        report.error = (
            "No format could be rendered: " + ", ".join(skipped)
        )[:500]
        return report

    report.file_keys = keys
    report.summary = payload
    report.status = ReportStatus.READY
    report.generated_at = datetime.now(timezone.utc)
    report.error = (
        f"Formats unavailable on this host: {', '.join(skipped)}" if skipped else None
    )
    await db.flush()

    await _notify(db, report, account)
    return report


async def _notify(db: AsyncSession, report: Report, account: Account) -> None:
    """Tell whoever asked that the report is ready.

    Only the requester. A scheduled report has no requester, so it goes to the
    workspace owner -- notifying every member of a five-person team that the
    monthly report exists is how people learn to ignore notifications.
    """
    recipient = report.created_by or account.owner_id
    if recipient is None:
        return
    db.add(
        Notification(
            id=uuid.uuid4(),
            user_id=recipient,
            account_id=account.id,
            type="report_ready",
            title="Your report is ready",
            message=f"{report.title} is ready to download.",
            action_url=f"/reports?report={report.id}",
            metadata_={"report_id": str(report.id), "formats": list(report.file_keys or {})},
        )
    )
    await db.flush()


async def run_pending(db: AsyncSession, *, limit: int = 3) -> int:
    """Generate queued reports.

    A small limit on purpose: a render is CPU-bound in this process, and
    clearing a backlog of twenty in one pass would stall the publishing loop
    that shares it.
    """
    reports = (
        await db.execute(
            select(Report)
            .where(Report.status == ReportStatus.PENDING)
            .order_by(Report.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()

    for report in reports:
        try:
            await generate(db, report)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Report %s failed", report.id)
            report.status = ReportStatus.FAILED
            report.error = f"{type(exc).__name__}: {exc}"[:500]
    return len(reports)


async def queue_scheduled(db: AsyncSession) -> int:
    """Queue reports for workspaces with a cadence switched on.

    Idempotent by period: a workspace whose August report exists is skipped,
    however many times this runs.
    """
    accounts = (
        await db.execute(select(Account).where(Account.deleted_at.is_(None)))
    ).scalars().all()

    queued = 0
    for account in accounts:
        cadence = ((account.settings or {}).get(CADENCE_KEY) or "off").lower()
        report_type = CADENCES.get(cadence)
        if report_type is None:
            continue

        period = reporting.resolve_period(report_type, account=account)
        if await already_reported(db, account.id, report_type, period.start):
            continue

        # Nothing to report on before the workspace existed.
        created_local = (
            account.created_at.astimezone(workspace_timezone(account)).date()
            if account.created_at
            else period.start
        )
        if period.end < created_local:
            continue

        await create(db, account, report_type=report_type)
        queued += 1
        logger.info(
            "Queued a %s report for %s covering %s", cadence, account.id, period.label
        )
    return queued


def download_url(report: Report, fmt: ReportFormat) -> str:
    """A presigned URL for one rendered file."""
    keys = report.file_keys or {}
    key = keys.get(fmt.value)
    if not key:
        raise KeyError(fmt.value)
    return storage.get_storage().presign_download(key)


def retention_cutoff(days: int = 365) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)
