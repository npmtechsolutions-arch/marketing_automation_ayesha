"""Reports: create, list, download, and the branding settings behind them."""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import verify_account_access as _verify_account_access
from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.permissions import CONTENT_VIEW, REPORTS_VIEW, SETTINGS_MANAGE
from app.models.account import Account
from app.models.report import Report, ReportFormat, ReportStatus, ReportType
from app.services import entitlement_service as ent
from app.services import report_jobs, reporting, storage
from app.services.activity_service import log_activity

router = APIRouter()


class ReportCreate(BaseModel):
    type: ReportType = ReportType.MONTHLY
    title: Optional[str] = Field(None, max_length=200)
    # Only for a custom period; ignored otherwise, since weekly/monthly/
    # quarterly each mean one specific span.
    start: Optional[date] = None
    end: Optional[date] = None
    branding: Optional[dict] = None


class BrandingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: Optional[str] = Field(None, max_length=120)
    primary_color: Optional[str] = Field(None, max_length=7)
    accent_color: Optional[str] = Field(None, max_length=7)
    logo_url: Optional[str] = Field(None, max_length=500)
    footer_note: Optional[str] = Field(None, max_length=120)

    @field_validator("primary_color", "accent_color")
    @classmethod
    def _hex_only(cls, value: Optional[str]) -> Optional[str]:
        """A colour reaches a stylesheet in a PDF sent to the workspace's own
        clients, so only a hex literal is accepted."""
        if value is None:
            return value
        text = value.strip()
        valid = len(text) in (4, 7) and text.startswith("#") and all(
            ch in "0123456789abcdefABCDEF" for ch in text[1:]
        )
        if not valid:
            raise ValueError("Use a hex colour such as #6d5ef6.")
        return text


def _serialise(report: Report) -> dict:
    return {
        "id": str(report.id),
        "title": report.title,
        "type": report.type.value,
        "status": report.status.value,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "formats": sorted((report.file_keys or {}).keys()),
        "branding": report.branding,
        "executive_summary": (report.summary or {}).get("executive_summary"),
        "error": report.error,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "created_at": report.created_at.isoformat(),
    }


async def _account(account_id: uuid.UUID, db: AsyncSession) -> Account:
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return account


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    account_id: uuid.UUID,
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Queue a report.

    202 rather than 201: the row exists, the files do not yet. Generating
    inline would hold the connection through an aggregation and three renders,
    which dies behind a proxy on any period worth reporting on.
    """
    await _verify_account_access(account_id, current_user, db, permission=REPORTS_VIEW)
    account = await _account(account_id, db)

    organization = await ent.get_organization_for_account(db, account_id)
    await ent.check_and_increment(db, organization, ent.REPORTS_PER_MONTH)

    try:
        report = await report_jobs.create(
            db, account,
            report_type=body.type,
            created_by=current_user.id,
            start=body.start,
            end=body.end,
            branding=body.branding or (account.settings or {}).get("report_branding"),
            title=body.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="report.requested", category="report",
        description=f"Requested a {body.type.value} report",
        resource_type="report", resource_id=str(report.id),
        resource_name=report.title,
    )
    return _serialise(report)


@router.get("/")
async def list_reports(
    account_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=REPORTS_VIEW)
    rows = (
        await db.execute(
            select(Report)
            .where(Report.account_id == account_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "reports": [_serialise(row) for row in rows],
        "white_label": await report_jobs.white_label_allowed(db, account_id),
    }


@router.get("/{report_id}")
async def get_report(
    account_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """One report, with the aggregated numbers so the page can preview it
    without downloading a file."""
    await _verify_account_access(account_id, current_user, db, permission=REPORTS_VIEW)
    report = await _get_or_404(db, account_id, report_id)
    return {**_serialise(report), "summary": report.summary}


@router.get("/{report_id}/download")
async def download_report(
    account_id: uuid.UUID,
    report_id: uuid.UUID,
    format: ReportFormat = Query(ReportFormat.PDF),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """A short-lived presigned URL for one rendered file.

    A redirect rather than proxying the bytes: the file is already in object
    storage, and streaming it back through the API would put a megabyte of PDF
    through the request path for no gain.
    """
    await _verify_account_access(account_id, current_user, db, permission=REPORTS_VIEW)
    report = await _get_or_404(db, account_id, report_id)

    if report.status is not ReportStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"That report is {report.status.value}, not ready to download.",
        )
    try:
        url = report_jobs.download_url(report, format)
    except KeyError as exc:
        available = ", ".join(sorted((report.file_keys or {}).keys())) or "none"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"This report has no {format.value} file. Available: {available}."
            ),
        ) from exc
    except storage.StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"url": url, "format": format.value, "expires_in": 3600}


@router.get("/settings/branding")
async def get_branding(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The workspace's white-label settings, and whether they will be applied."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    account = await _account(account_id, db)
    entitled = await report_jobs.white_label_allowed(db, account_id)
    stored = (account.settings or {}).get("report_branding")
    return {
        "branding": reporting.sanitise_branding(stored, entitled=True),
        "white_label": entitled,
        # What a report would actually use today, which differs from the above
        # when the plan does not include white-label.
        "effective": reporting.sanitise_branding(stored, entitled=entitled),
        "defaults": reporting.DEFAULT_BRANDING,
        "cadence": ((account.settings or {}).get(report_jobs.CADENCE_KEY) or "off"),
    }


class CadenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cadence: str = Field(..., pattern="^(off|weekly|monthly)$")


@router.put("/settings/branding")
async def update_branding(
    account_id: uuid.UUID,
    body: BrandingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Store branding. Accepted whatever the plan says, applied only with the
    entitlement -- a customer trialling the setting should be able to fill it
    in before they upgrade, not after."""
    await _verify_account_access(account_id, current_user, db, permission=SETTINGS_MANAGE)
    account = await _account(account_id, db)

    updates = body.model_dump(exclude_unset=True)
    stored = dict((account.settings or {}).get("report_branding") or {})
    stored.update(updates)
    # A new dict: a plain JSON column has no change tracking, so mutating the
    # loaded one and assigning it back writes nothing.
    account.settings = {**(account.settings or {}), "report_branding": stored}
    await db.flush()

    entitled = await report_jobs.white_label_allowed(db, account_id)
    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="report.branding_updated", category="settings",
        description="Updated report branding",
        resource_type="account", resource_id=str(account_id),
    )
    return {
        "branding": reporting.sanitise_branding(stored, entitled=True),
        "effective": reporting.sanitise_branding(stored, entitled=entitled),
        "white_label": entitled,
    }


@router.put("/settings/cadence")
async def update_cadence(
    account_id: uuid.UUID,
    body: CadenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Switch automatic weekly or monthly reports on or off."""
    await _verify_account_access(account_id, current_user, db, permission=SETTINGS_MANAGE)
    account = await _account(account_id, db)
    account.settings = {
        **(account.settings or {}), report_jobs.CADENCE_KEY: body.cadence
    }
    await db.flush()
    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="report.cadence_updated", category="settings",
        description=f"Automatic reports: {body.cadence}",
        resource_type="account", resource_id=str(account_id),
    )
    return {"cadence": body.cadence}


async def _get_or_404(
    db: AsyncSession, account_id: uuid.UUID, report_id: uuid.UUID
) -> Report:
    report = (
        await db.execute(
            select(Report).where(
                Report.id == report_id, Report.account_id == account_id
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
