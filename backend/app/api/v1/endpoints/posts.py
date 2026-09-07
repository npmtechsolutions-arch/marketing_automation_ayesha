"""Post management endpoints."""

import uuid
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount
from app.models.post import Post, PostStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.post import PostCreate, PostResponse, PostUpdate, PostWithPerformance
from app.services.activity_service import log_activity
from app.services.entitlements import enforce_post_limit
from app.core.authz import verify_account_access as _verify_account_access
from app.connectors.base import NotSupportedError
from app.connectors.registry import get_provider
from app.models.platform import SocialAccount
from app.models.publishing_job import (
    JobStatus,
    LogLevel,
    PublishingJob,
    PublishingLog,
)
from app.schemas.publishing_job import (
    PublishingJobList,
    PublishingJobResponse,
    PublishingLogEntry,
)
from app.services import publishing
from app.core.permissions import (  # noqa: F401
    CONTENT_APPROVE,
    CONTENT_CREATE,
    CONTENT_VIEW,
    CONTENT_DELETE,
    CONTENT_PUBLISH,
)
from app.core.permissions import restricts_content_to_approvals

router = APIRouter()


def _post_label(post: Post) -> str:
    """A short human-readable name for a post, for activity descriptions."""
    title = (getattr(post, "title", None) or "").strip()
    if title:
        return title
    content = (getattr(post, "content", None) or "").strip()
    if content:
        return content[:60] + ("…" if len(content) > 60 else "")
    return "Untitled post"



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_post_or_404(
    post_id: uuid.UUID,
    account_id: uuid.UUID,
    db: AsyncSession,
    *,
    with_performances: bool = False,
) -> Post:
    stmt = select(Post).where(
        Post.id == post_id,
        Post.account_id == account_id,
        Post.deleted_at.is_(None),
    )
    if with_performances:
        stmt = stmt.options(selectinload(Post.performances))
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[PostResponse])
async def list_posts(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: PostStatus | None = Query(None, alias="status"),
    platform: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """List posts for an account with optional filters and pagination."""
    member = await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_VIEW
    )

    conditions = [Post.account_id == account_id, Post.deleted_at.is_(None)]
    if restricts_content_to_approvals(member.role):
        # A CLIENT is an external reviewer. Holding content.view lets them open
        # the approval queue and nothing else -- without this they would see
        # every draft in the workspace, which is precisely what the role exists
        # to prevent.
        conditions.append(Post.status == PostStatus.PENDING_APPROVAL)

    if status_filter:
        conditions.append(Post.status == status_filter)
    if date_from:
        conditions.append(Post.created_at >= date_from)
    if date_to:
        conditions.append(Post.created_at <= date_to)

    where_clause = and_(*conditions)

    # Total count
    count_result = await db.execute(select(func.count(Post.id)).where(where_clause))
    total = count_result.scalar() or 0

    # Paginated results
    stmt = (
        select(Post)
        .where(where_clause)
        .options(selectinload(Post.performances))
        .order_by(Post.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()

    # If platform filter specified, filter in-app (target_accounts is JSON)
    if platform:
        posts = [
            p for p in posts
            if any(
                ta.get("platform_name", "").lower() == platform.lower()
                for ta in (p.target_accounts or [])
            )
        ]

    return PaginatedResponse(
        items=[PostResponse.model_validate(p) for p in posts],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page if per_page else 1,
    )


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    account_id: uuid.UUID,
    body: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a new post (draft by default)."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    await enforce_post_limit(db, account_id)

    # Resolve target accounts from IDs to structured JSON
    target_accounts = None
    if body.target_account_ids:
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.id.in_(body.target_account_ids),
                SocialAccount.account_id == account_id,
            )
        )
        social_accounts = result.scalars().all()
        if len(social_accounts) != len(body.target_account_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more target account IDs are invalid or do not belong to this account",
            )
        target_accounts = [
            {
                "social_account_id": str(sa.id),
                "platform_name": sa.platform.name if sa.platform else "Unknown",
                "account_name": sa.account_name,
            }
            for sa in social_accounts
        ]

    post = Post(
        user_id=current_user.id,
        account_id=account_id,
        content=body.content,
        title=body.title,
        hashtags=body.hashtags,
        target_accounts=target_accounts,
        media_urls=body.media_urls,
        scheduled_at=body.scheduled_at,
        business_id=body.business_id,
        strategy_id=body.strategy_id,
        campaign_id=body.campaign_id,
        ai_images=body.ai_images,
        digital_assets=body.digital_assets,
        status=PostStatus.DRAFT,
        instagram_post_type=body.instagram_post_type,
        instagram_music_track=body.instagram_music_track,
        instagram_music_url=body.instagram_music_url,
        instagram_music_start_offset=body.instagram_music_start_offset,
        instagram_music_end_offset=body.instagram_music_end_offset,
        instagram_video_url=body.instagram_video_url,
        facebook_post_type=body.facebook_post_type,
        facebook_music_track=body.facebook_music_track,
        facebook_music_url=body.facebook_music_url,
        facebook_music_start_offset=body.facebook_music_start_offset,
        facebook_music_end_offset=body.facebook_music_end_offset,
        facebook_video_url=body.facebook_video_url,
        youtube_post_type=body.youtube_post_type,
        linkedin_post_type=body.linkedin_post_type,
        twitter_post_type=body.twitter_post_type,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.created",
        category="post",
        description=f"Created post '{_post_label(post)}'",
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
    )

    return PostResponse.model_validate(post)


async def _ensure_valid_token(sa: SocialAccount, db: AsyncSession) -> None:
    """Refresh the account's OAuth token if it is expired or about to be.

    This used to carry its own per-platform if/elif with branches for YouTube
    and X only -- Meta and LinkedIn tokens simply expired mid-publish, even
    though the working refresh for both sat in social_accounts.py. Going
    through the registry means every platform with a refresh implementation
    gets one here, which is the one place this refactor deliberately changes
    behaviour.

    Failure is non-fatal by design: the publish attempt proceeds with the token
    we have and reports the platform's own error, rather than failing the post
    on a refresh that might not have been needed.
    """
    if not sa.token_expires_at:
        return

    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    expires_at = sa.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > now + timedelta(minutes=2):
        return

    provider = get_provider(sa.platform.slug if sa.platform else None)
    try:
        result = await provider.refresh_token(sa)
    except NotSupportedError:
        return
    except Exception as exc:  # noqa: BLE001 - never fail a publish on refresh
        logging.getLogger(__name__).warning(
            "Could not refresh %s token for social account %s: %s",
            provider.slug, sa.id, exc,
        )
        return

    sa.access_token = result.access_token
    if result.refresh_token:
        sa.refresh_token = result.refresh_token
    if result.expires_at:
        sa.token_expires_at = result.expires_at
    await db.flush()


async def _sync_post_performance(post: Post, db: AsyncSession):
    from app.models.post_performance import PostPerformance
    from app.models.platform import SocialAccount
    
    if post.status not in [PostStatus.PUBLISHED, PostStatus.PARTIALLY_PUBLISHED]:
        return

    targets = post.posting_results or []
    if not targets:
        return

    for target in targets:
        if target.get("status") != "published":
            continue
        ext_id = target.get("external_post_id")
        sa_id = target.get("social_account_id")
        if not ext_id or not sa_id:
            continue

        try:
            sa_uuid = uuid.UUID(sa_id)
            sa_result = await db.execute(
                select(SocialAccount)
                .options(selectinload(SocialAccount.platform))
                .where(SocialAccount.id == sa_uuid)
            )
            sa = sa_result.scalar_one_or_none()
            if not sa:
                continue

            await _ensure_valid_token(sa, db)
            provider = get_provider(sa.platform.slug if sa.platform else None)
            metrics = await provider.get_post_metrics(ext_id, sa)
            if not metrics:
                continue

            platform_type = (sa.platform.slug if sa.platform else "instagram").lower()

            existing_perf = None
            duplicates_to_delete = []
            for p in post.performances:
                if p.platform_type == platform_type:
                    if not existing_perf:
                        existing_perf = p
                    else:
                        duplicates_to_delete.append(p)

            if existing_perf:
                existing_perf.impressions = metrics.get("impressions", existing_perf.impressions)
                existing_perf.reach = metrics.get("reach", existing_perf.reach)
                existing_perf.likes = metrics.get("likes", existing_perf.likes)
                existing_perf.comments = metrics.get("comments", existing_perf.comments)
                existing_perf.shares = metrics.get("shares", existing_perf.shares)
                existing_perf.saves = metrics.get("saves", existing_perf.saves)
                existing_perf.clicks = metrics.get("clicks", existing_perf.clicks)
                existing_perf.video_views = metrics.get("video_views", existing_perf.video_views)
                existing_perf.engagement_rate = metrics.get("engagement_rate", existing_perf.engagement_rate)
                existing_perf.click_through_rate = metrics.get("click_through_rate", existing_perf.click_through_rate)
                existing_perf.fetched_at = datetime.now(timezone.utc)
            else:
                db.add(PostPerformance(
                    id=uuid.uuid4(),
                    post_id=post.id,
                    platform_type=platform_type,
                    impressions=metrics.get("impressions", 0),
                    reach=metrics.get("reach", 0),
                    likes=metrics.get("likes", 0),
                    comments=metrics.get("comments", 0),
                    shares=metrics.get("shares", 0),
                    saves=metrics.get("saves", 0),
                    clicks=metrics.get("clicks", 0),
                    video_views=metrics.get("video_views", 0),
                    engagement_rate=metrics.get("engagement_rate", 0.0),
                    click_through_rate=metrics.get("click_through_rate", 0.0),
                ))
            
            if duplicates_to_delete:
                for dup in duplicates_to_delete:
                    await db.delete(dup)
                    
            await db.flush()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to sync post performance: %s", e)


@router.get("/{post_id}", response_model=PostWithPerformance)
async def get_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Get a single post with its performance data."""
    await _verify_account_access(account_id, current_user, db)
    post = await _get_post_or_404(post_id, account_id, db, with_performances=True)
    
    # Sync performance in real-time
    await _sync_post_performance(post, db)
    await db.commit()
    await db.refresh(post, ["performances"])
    
    return PostWithPerformance.model_validate(post)


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    body: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Update a post. Only draft or rejected posts can be edited."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (
        PostStatus.DRAFT,
        PostStatus.PENDING_APPROVAL,
        PostStatus.APPROVED,
        PostStatus.SCHEDULED,
        PostStatus.FAILED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit a post with status '{post.status.value}'",
        )

    update_data = body.model_dump(exclude_unset=True)

    # Handle target_account_ids -> target_accounts resolution
    if "target_account_ids" in update_data:
        target_account_ids = update_data.pop("target_account_ids")
        if target_account_ids:
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.id.in_(target_account_ids),
                    SocialAccount.account_id == account_id,
                )
            )
            social_accounts = result.scalars().all()
            if len(social_accounts) != len(target_account_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more target account IDs are invalid or do not belong to this account",
                )
            update_data["target_accounts"] = [
                {
                    "social_account_id": str(sa.id),
                    "platform_name": sa.platform.name if sa.platform else "Unknown",
                    "account_name": sa.account_name,
                }
                for sa in social_accounts
            ]
        else:
            update_data["target_accounts"] = None

    for field, value in update_data.items():
        setattr(post, field, value)

    await db.flush()
    await db.refresh(post)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.updated",
        category="post",
        description=f"Updated post '{_post_label(post)}'",
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
    )

    return PostResponse.model_validate(post)


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Soft-delete a post."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_DELETE)
    post = await _get_post_or_404(post_id, account_id, db)

    post.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.deleted",
        category="post",
        description=f"Deleted post '{_post_label(post)}'",
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
    )

    return MessageResponse(message="Post deleted successfully")


@router.post("/{post_id}/publish", response_model=PostResponse)
async def publish_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Publish a post now.

    Creates one job per target account with ``run_at`` set to now; the worker
    picks them up on its next pass. Publishing used to happen in a background
    task inside this process, which meant a restart between the response and
    the platform call lost the publish with no record that it had been asked
    for.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_PUBLISH)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (PostStatus.DRAFT, PostStatus.APPROVED, PostStatus.SCHEDULED, PostStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish a post with status '{post.status.value}'",
        )
    if not (post.target_accounts or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This post has no target accounts to publish to.",
        )

    await publishing.create_jobs_for_post(db, post, run_at=datetime.now(timezone.utc))
    post.status = PostStatus.PUBLISHING
    await db.flush()
    await db.refresh(post)

    return PostResponse.model_validate(post)


@router.post("/{post_id}/schedule", response_model=PostResponse)
async def schedule_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    scheduled_at: datetime = Query(..., description="ISO-8601 datetime for scheduling"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Schedule a post for future publication."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_PUBLISH)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (PostStatus.DRAFT, PostStatus.APPROVED, PostStatus.FAILED, PostStatus.SCHEDULED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot schedule a post with status '{post.status.value}'",
        )

    # Validate the scheduled time is in the future
    now = datetime.now(timezone.utc)
    target = scheduled_at if scheduled_at.tzinfo else scheduled_at.replace(tzinfo=timezone.utc)
    if target <= now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scheduled_at must be in the future",
        )

    if not (post.target_accounts or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This post has no target accounts to publish to.",
        )

    # Jobs are created now with run_at in the future rather than when the time
    # arrives, so a scheduled post's pending work is visible (and cancellable)
    # before it runs. create_jobs_for_post cancels any superseded jobs, so
    # rescheduling cannot leave an older run pending.
    await publishing.create_jobs_for_post(db, post, run_at=target)
    post.status = PostStatus.SCHEDULED
    post.scheduled_at = target
    await db.flush()
    await db.refresh(post)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.scheduled",
        category="post",
        description=f"Scheduled post '{_post_label(post)}' for {target.isoformat()}",
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
    )

    return PostResponse.model_validate(post)


@router.post("/{post_id}/duplicate", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a copy of an existing post as a new draft."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_CREATE)
    await enforce_post_limit(db, account_id)
    original = await _get_post_or_404(post_id, account_id, db)

    new_post = Post(
        user_id=current_user.id,
        account_id=account_id,
        business_id=original.business_id,
        strategy_id=original.strategy_id,
        campaign_id=original.campaign_id,
        content=original.content,
        title=original.title,
        media_urls=original.media_urls,
        hashtags=original.hashtags,
        target_accounts=original.target_accounts,
        ai_images=original.ai_images,
        digital_assets=original.digital_assets,
        status=PostStatus.DRAFT,
        ai_generated=original.ai_generated,
        ai_model=original.ai_model,
        ai_prompt=original.ai_prompt,
    )
    db.add(new_post)
    await db.flush()
    await db.refresh(new_post)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.duplicated",
        category="post",
        description=f"Duplicated post '{_post_label(new_post)}'",
        resource_type="post",
        resource_id=str(new_post.id),
        resource_name=_post_label(new_post),
    )

    return PostResponse.model_validate(new_post)


@router.post("/{post_id}/approve", response_model=PostResponse)
async def approve_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Approve a post. Requires manager role or above."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_APPROVE)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status != PostStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only posts with 'pending_approval' status can be approved",
        )

    post.status = PostStatus.APPROVED
    post.approved_by = current_user.id
    post.approved_at = datetime.now(timezone.utc)
    post.rejection_reason = None
    await db.flush()
    await db.refresh(post)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.approved",
        category="post",
        description=f"Approved post '{_post_label(post)}'",
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
    )

    return PostResponse.model_validate(post)


@router.post("/{post_id}/reject", response_model=PostResponse)
async def reject_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    reason: str = Query(..., min_length=1, description="Reason for rejection"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Reject a post with a reason. Requires manager role or above."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_APPROVE)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status != PostStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only posts with 'pending_approval' status can be rejected",
        )

    post.status = PostStatus.DRAFT
    post.rejection_reason = reason
    await db.flush()
    await db.refresh(post)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action="post.rejected",
        category="post",
        description=f"Rejected post '{_post_label(post)}': {reason}",
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
        status="warning",
    )

    return PostResponse.model_validate(post)


# ---------------------------------------------------------------------------
# Publishing jobs
#
# A post's publishing used to be a JSON blob with a status string per target
# and nothing else. These expose the jobs behind it: how many attempts each
# has had, when the next one is due, and what the platform actually said.
# ---------------------------------------------------------------------------

def _job_response(job) -> PublishingJobResponse:
    account = job.social_account
    platform = account.platform if account else None
    return PublishingJobResponse(
        id=job.id,
        post_id=job.post_id,
        social_account_id=job.social_account_id,
        platform_slug=(platform.slug if platform else None),
        account_name=(account.account_name if account else None),
        status=job.status.value,
        run_at=job.run_at,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        attempts_remaining=job.attempts_remaining,
        last_error=job.last_error,
        claimed_by=job.claimed_by,
        claimed_at=job.claimed_at,
        manual_required=job.manual_required,
        external_post_id=job.external_post_id,
        post_url=job.post_url,
        created_at=job.created_at,
        updated_at=job.updated_at,
        logs=[PublishingLogEntry.model_validate(entry) for entry in job.logs],
    )


@router.get("/{post_id}/jobs", response_model=PublishingJobList)
async def list_publishing_jobs(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Every publishing job for a post, with its full log.

    Readable by anyone who can view the post: knowing why a post did not go out
    is not privileged, and gating it behind publish rights is how a client ends
    up asking their agency to check.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    post = await _get_post_or_404(post_id, account_id, db)

    jobs = (
        await db.execute(
            select(PublishingJob)
            .options(
                selectinload(PublishingJob.logs),
                selectinload(PublishingJob.social_account).selectinload(
                    SocialAccount.platform
                ),
            )
            .where(PublishingJob.post_id == post_id)
            .order_by(PublishingJob.created_at)
        )
    ).scalars().all()

    return PublishingJobList(
        post_id=post.id,
        post_status=post.status.value,
        jobs=[_job_response(job) for job in jobs],
    )


@router.post("/{post_id}/jobs/{job_id}/retry", response_model=PublishingJobResponse)
async def retry_publishing_job(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Requeue one failed job.

    Only that job runs again -- the accounts that already succeeded are not
    republished. That is the whole reason publishing is per-target: the old
    recovery path reset the entire post and reposted everything.

    Attempts are reset so a manual retry gets a full allowance; the operator
    has presumably fixed whatever caused the failure, and making them click
    three times to get one real attempt helps nobody.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_PUBLISH)
    await _get_post_or_404(post_id, account_id, db)

    job = (
        await db.execute(
            select(PublishingJob)
            .options(
                selectinload(PublishingJob.logs),
                selectinload(PublishingJob.social_account).selectinload(
                    SocialAccount.platform
                ),
            )
            .where(PublishingJob.id == job_id, PublishingJob.post_id == post_id)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Publishing job not found"
        )

    if job.status in (JobStatus.QUEUED, JobStatus.CLAIMED, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This job is already {job.status.value}; nothing to retry.",
        )
    if job.status is JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This job already published successfully. Retrying it would "
                "post the content a second time."
            ),
        )

    job.status = JobStatus.QUEUED
    job.attempts = 0
    job.claimed_by = None
    job.claimed_at = None
    job.run_at = datetime.now(timezone.utc)
    job.last_error = None
    db.add(
        PublishingLog(
            id=uuid.uuid4(),
            job_id=job.id,
            level=LogLevel.INFO,
            message=f"Requeued manually by {current_user.email}",
        )
    )
    await db.flush()

    await publishing.derive_post_status(db, post_id)

    # Re-query rather than refresh(): refresh drops the eager loads, and
    # touching job.logs afterwards would be a lazy load -- which raises under
    # async SQLAlchemy rather than quietly issuing a query.
    job = (
        await db.execute(
            select(PublishingJob)
            .options(
                selectinload(PublishingJob.logs),
                selectinload(PublishingJob.social_account).selectinload(
                    SocialAccount.platform
                ),
            )
            .where(PublishingJob.id == job_id)
            # Without this the identity map hands back the collection as it was
            # loaded a moment ago, and the "requeued" line we just wrote is
            # missing from the response.
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return _job_response(job)
