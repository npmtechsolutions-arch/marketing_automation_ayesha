"""Rendering a report payload into PDF, CSV and Excel.

The three renderers answer the same numbers in three shapes: a PDF to send a
client, a CSV to paste into whatever the agency already uses, and a workbook
for someone who wants to pivot it.

PDF is the one with a system dependency. WeasyPrint needs pango, and a host
without it can still produce the other two -- so an unavailable PDF is reported
as *absent* rather than raising. A report whose CSV and Excel arrived is worth
more than a failed job, and ``file_keys`` not containing "pdf" is the honest
record of what happened.
"""

import csv
import io
import logging
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.report import ReportFormat

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    ReportFormat.PDF: "application/pdf",
    ReportFormat.CSV: "text/csv; charset=utf-8",
    ReportFormat.XLSX: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
}

_TEMPLATE_DIR = "app/templates/reports"


# ---------------------------------------------------------------------------
# Shared formatting
#
# The null discipline from the analytics work has to survive into the files: a
# metric the platform does not report is a dash, never a zero. A spreadsheet
# cell is left genuinely empty rather than holding the string "None", so it
# does not poison a SUM or sort as text.
# ---------------------------------------------------------------------------

def metric(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return str(value)


def percent(value: Any, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}%"


def _delta_text(entry: dict) -> tuple[str, bool, bool]:
    """(text, positive, negative) for a metric's movement."""
    change = entry.get("change")
    pct = entry.get("change_percent")
    if change is None:
        return "no comparison", False, False
    arrow = "▲" if change >= 0 else "▼"
    suffix = f" ({pct:+.1f}%)" if pct is not None else ""
    return f"{arrow} {abs(change):,.0f}{suffix}", change > 0, change < 0


def headline_cards(payload: dict) -> list[dict]:
    """The four numbers at the top, in the order an agency reads them."""
    metrics = payload.get("metrics", {})
    wanted = [
        ("followers", "Followers", False),
        ("reach", "Reach", False),
        ("impressions", "Impressions", False),
        ("engagement_rate", "Engagement rate", True),
    ]
    cards = []
    for key, label, as_percent in wanted:
        entry = metrics.get(key) or {}
        text, positive, negative = _delta_text(entry)
        cards.append({
            "label": label,
            "value": percent(entry.get("value")) if as_percent else metric(entry.get("value")),
            "delta": text,
            "positive": positive,
            "negative": negative,
        })
    return cards


def _platform_rows(payload: dict) -> list[dict]:
    """Platform rows with interactions summed, for every renderer."""
    rows = []
    for row in payload.get("platforms", []):
        parts = [row.get(k) for k in ("likes", "comments", "shares", "saves")]
        rows.append({
            **row,
            "interactions": (
                None if all(p is None for p in parts) else sum(p or 0 for p in parts)
            ),
        })
    return rows


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def pdf_available() -> tuple[bool, Optional[str]]:
    """Whether WeasyPrint can actually render here.

    Importing it is not enough: the package installs cleanly and then fails to
    find pango at call time, so this does a real import of the renderer class.
    """
    try:
        from weasyprint import HTML  # noqa: F401

        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).splitlines()[0][:200]


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        # Autoescaped: the payload carries post titles the workspace's authors
        # wrote, and this document is sent to their clients.
        autoescape=select_autoescape(["html"]),
    )
    env.filters["metric"] = metric
    env.filters["percent"] = percent
    return env


def render_html(payload: dict, branding: dict) -> str:
    template = _environment().get_template("report.html")
    # Built explicitly rather than splatting the payload: `platforms` needs the
    # interactions column added, and `**payload` plus an override is a
    # duplicate-keyword TypeError rather than the last-one-wins it looks like.
    context = {
        **payload,
        "branding": branding,
        "headline": headline_cards(payload),
        "platforms": _platform_rows(payload),
    }
    return template.render(**context)


def render_pdf(payload: dict, branding: dict) -> bytes:
    """The PDF. Raises if WeasyPrint cannot run here -- the caller decides
    whether that fails the report or simply omits the format."""
    from weasyprint import HTML

    return HTML(string=render_html(payload, branding)).write_pdf()


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def render_csv(payload: dict, branding: dict) -> bytes:
    """One file with three labelled blocks.

    Not three files: an agency downloading "the CSV" wants the report, and
    three downloads to reassemble is worse than one file with headings.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow([branding.get("company_name", ""), payload["workspace"]["name"]])
    writer.writerow(["Period", payload["period"]["label"]])
    writer.writerow(["From", payload["period"]["start"], "To", payload["period"]["end"]])
    writer.writerow(["Timezone", payload["period"]["timezone"]])
    writer.writerow([])
    writer.writerow(["Summary", payload.get("executive_summary", "")])
    writer.writerow([])

    writer.writerow(["METRIC", "VALUE", "PREVIOUS", "CHANGE", "CHANGE %"])
    for name, entry in payload.get("metrics", {}).items():
        writer.writerow([
            name,
            _cell(entry.get("value")),
            _cell(entry.get("previous")),
            _cell(entry.get("change")),
            _cell(entry.get("change_percent")),
        ])
    writer.writerow([])

    writer.writerow([
        "PLATFORM", "FOLLOWERS", "REACH", "IMPRESSIONS", "INTERACTIONS", "ENGAGEMENT RATE"
    ])
    for row in _platform_rows(payload):
        writer.writerow([
            row.get("platform_name"),
            _cell(row.get("followers")), _cell(row.get("reach")),
            _cell(row.get("impressions")), _cell(row.get("interactions")),
            _cell(row.get("engagement_rate")),
        ])
    writer.writerow([])

    writer.writerow([
        "TOP POSTS", "PUBLISHED", "ENGAGEMENT", "REACH", "IMPRESSIONS", "ENGAGEMENT RATE"
    ])
    for post in payload.get("top_posts", []):
        writer.writerow([
            post.get("title"),
            (post.get("published_at") or "")[:10],
            _cell(post.get("engagement")), _cell(post.get("reach")),
            _cell(post.get("impressions")), _cell(post.get("engagement_rate")),
        ])

    return buffer.getvalue().encode("utf-8-sig")


def _cell(value: Any) -> Any:
    """Empty for null, never the string "None" -- a spreadsheet reads an
    unreported metric as blank rather than as text."""
    return "" if value is None else value


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

def render_xlsx(payload: dict, branding: dict) -> bytes:
    """A workbook with a sheet per section.

    Numbers are written as numbers. Writing "1,234" as a formatted string would
    make every column sort alphabetically and every SUM return zero, which is
    the one thing a spreadsheet user will certainly try.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    accent = (branding.get("primary_color") or "#6d5ef6").lstrip("#")
    header_fill = PatternFill("solid", fgColor=accent)
    header_font = Font(bold=True, color="FFFFFF")

    book = Workbook()

    overview = book.active
    overview.title = "Overview"
    overview["A1"] = branding.get("company_name", "")
    overview["A1"].font = Font(bold=True, size=14)
    overview["A2"] = payload["workspace"]["name"]
    overview["A3"] = payload["period"]["label"]
    overview["A4"] = (
        f"{payload['period']['start']} to {payload['period']['end']} "
        f"({payload['period']['timezone']})"
    )
    overview["A6"] = "Summary"
    overview["A6"].font = Font(bold=True)
    overview["A7"] = payload.get("executive_summary", "")
    overview["A7"].alignment = Alignment(wrap_text=True, vertical="top")
    overview.merge_cells("A7:F11")
    overview.column_dimensions["A"].width = 28

    def _sheet(title: str, headers: list[str], rows: list[list[Any]]):
        sheet = book.create_sheet(title)
        sheet.append(headers)
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
        for row in rows:
            sheet.append(row)
        for index, header in enumerate(headers, start=1):
            width = max(len(str(header)) + 4, 14)
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.freeze_panes = "A2"
        return sheet

    _sheet(
        "Metrics",
        ["Metric", "Value", "Previous", "Change", "Change %"],
        [
            [name, _cell(e.get("value")), _cell(e.get("previous")),
             _cell(e.get("change")), _cell(e.get("change_percent"))]
            for name, e in payload.get("metrics", {}).items()
        ],
    )
    _sheet(
        "Platforms",
        ["Platform", "Accounts", "Followers", "Reach", "Impressions",
         "Interactions", "Engagement rate"],
        [
            [r.get("platform_name"), r.get("accounts"), _cell(r.get("followers")),
             _cell(r.get("reach")), _cell(r.get("impressions")),
             _cell(r.get("interactions")), _cell(r.get("engagement_rate"))]
            for r in _platform_rows(payload)
        ],
    )
    _sheet(
        "Top posts",
        ["Post", "Published", "Engagement", "Reach", "Impressions", "Engagement rate"],
        [
            [p.get("title"), (p.get("published_at") or "")[:10],
             _cell(p.get("engagement")), _cell(p.get("reach")),
             _cell(p.get("impressions")), _cell(p.get("engagement_rate"))]
            for p in payload.get("top_posts", [])
        ],
    )
    _sheet(
        "Audience",
        ["Date", "Followers", "Following"],
        [
            [point.get("date"), _cell(point.get("followers")), _cell(point.get("following"))]
            for point in payload.get("audience", {}).get("series", [])
        ],
    )

    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


RENDERERS = {
    ReportFormat.PDF: render_pdf,
    ReportFormat.CSV: render_csv,
    ReportFormat.XLSX: render_xlsx,
}
