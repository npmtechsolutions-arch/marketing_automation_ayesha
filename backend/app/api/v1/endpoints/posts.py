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
from app.models.account import Account
from app.models.platform import SocialAccount
from app.models.post import Post, PostStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.post import PostCreate, PostResponse, PostUpdate, PostWithPerformance
from app.services.activity_service import log_activity
from app.services.entitlements import enforce_post_limit
from app.core.authz import verify_account_access as _verify_account_access
from app.connectors.base import (
    NotSupportedError,
    resolve_content,
    variant_for_slug,
)
from app.connectors.registry import get_provider
from app.models.platform import SocialAccount
from app.models.post_comment import PostComment
from app.models.team_member import InvitationStatus, TeamMember
from app.models.post_variant import PostVariant
from app.models.publishing_job import (
    JobStatus,
    LogLevel,
    PublishingJob,
    PublishingLog,
)
from app.schemas.post_variant import (
    PostValidationResponse,
    PostVariantResponse,
    PostVariantUpsert,
    ResolvedPreview,
)
from app.schemas.review import (
    AssignmentUpdate,
    CommentAuthor,
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    ReviewAction,
    ReviewState,
)
from app.schemas.publishing_job import (
    PublishingJobList,
    PublishingJobResponse,
    PublishingLogEntry,
)
from app.services import approvals, media_service, post_validation, publishing
from app.core.permissions import (  # noqa: F401
    CONTENT_APPROVE,
    CONTENT_CREATE,
    CONTENT_VIEW,
    CONTENT_DELETE,
    CONTENT_PUBLISH,
)
from app.core.permissions import (
    role_has_permission,
)

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

async def _assert_visible(member, post) -> None:
    """A CLIENT must not reach a post outside their review queue by id.

    The list filter alone would leave every single-post route open to anyone
    who guessed or was once sent a link.
    """
    allowed = approvals.visible_status_filter(member)
    if allowed is not None and post.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )


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
    client_statuses = approvals.visible_status_filter(member)
    if client_statuses is not None:
        # A CLIENT is an external reviewer. content.view lets them open the
        # approval queue and see what they signed off; without this they would
        # see every draft in the workspace, which is what the role exists to
        # prevent. Applied to the query, not the response, so pagination counts
        # are right too.
        conditions.append(Post.status.in_(client_statuses))

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
    # Record which library files this post uses, so the library can show a
    # usage count and refuse to lose a file that a post still points at.
    await media_service.sync_post_media(db, post.id, account_id, body.media_ids)
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
    member = await _verify_account_access(account_id, current_user, db)
    post = await _get_post_or_404(post_id, account_id, db, with_performances=True)
    await _assert_visible(member, post)
    
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

    # media_ids is not a column; it drives the PostMedia links instead.
    update_data.pop("media_ids", None)
    for field, value in update_data.items():
        setattr(post, field, value)

    await db.flush()
    # None means "not mentioned", so a caption-only edit leaves attachments be.
    await media_service.sync_post_media(db, post.id, account_id, body.media_ids)
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
    # A gate that exists on publish but not on schedule is not a gate, so both
    # go through the same check.
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    approvals.assert_publishable(account, post)

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

    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    approvals.assert_publishable(account, post)

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


# ---------------------------------------------------------------------------
# Review workflow
#
# Status is never assigned directly here: every move goes through
# app.services.approvals.transition, which is the one place that knows which
# transitions are legal and who may make them. Two endpoints disagreeing about
# that is how a workflow stops meaning anything.
# ---------------------------------------------------------------------------

async def _review_context(account_id, post_id, current_user, db, *, permission):
    member = await _verify_account_access(
        account_id, current_user, db, permission=permission
    )
    post = await _get_post_or_404(post_id, account_id, db)
    await _assert_visible(member, post)
    account = (
        await db.execute(select(Account).where(Account.id == account_id))
    ).scalar_one()
    return member, post, account


async def _run_transition(
    account_id, post_id, current_user, db, action, comment, *, permission
) -> PostResponse:
    member, post, account = await _review_context(
        account_id, post_id, current_user, db, permission=permission
    )
    previous = await approvals.transition(
        db, post=post, account=account, member=member, actor=current_user,
        action=action, comment=comment,
    )

    if comment and comment.strip():
        db.add(
            PostComment(
                id=uuid.uuid4(),
                post_id=post.id,
                author_id=current_user.id,
                body=comment.strip(),
                mentions=[
                    str(m)
                    for m in await approvals.parse_mentions(db, comment, account_id)
                ],
            )
        )
        await db.flush()

    await _notify_transition(db, post, account, current_user, action, previous)

    await log_activity(
        db,
        user_id=current_user.id,
        account_id=account_id,
        action=f"post.{action}",
        category="post",
        description=(
            f"{action.replace('_', ' ').capitalize()}: '{_post_label(post)}' "
            f"moved from {previous.value} to {post.status.value}"
        ),
        resource_type="post",
        resource_id=str(post.id),
        resource_name=_post_label(post),
    )
    await db.refresh(post)
    return PostResponse.model_validate(post)


async def _notify_transition(db, post, account, actor, action, previous) -> None:
    """Tell the people whose turn it now is, and the people who were waiting."""
    label = _post_label(post)
    if action == "submit":
        recipients = await approvals.approvers_for(db, post.account_id)
        title, message = (
            "A post needs your review",
            f"{actor.full_name} submitted '{label}' for review.",
        )
    elif action == "approve" and post.status is PostStatus.CLIENT_REVIEW:
        # Approval moved it onward rather than finishing it: the client is now
        # the one being waited on.
        recipients = await approvals.approvers_for(db, post.account_id, client=True)
        recipients |= await approvals.review_audience(db, post, post.account_id)
        title, message = (
            "A post is ready for client review",
            f"{actor.full_name} approved '{label}'; it is now with the client.",
        )
    elif action == "approve":
        recipients = await approvals.review_audience(db, post, post.account_id)
        title, message = (
            "Your post was approved",
            f"{actor.full_name} approved '{label}'.",
        )
    elif action == "request_changes":
        recipients = await approvals.review_audience(db, post, post.account_id)
        title, message = (
            "Changes requested on your post",
            f"{actor.full_name} asked for changes to '{label}'.",
        )
    else:
        return

    await approvals.notify(
        db,
        recipients=recipients,
        account_id=post.account_id,
        actor=actor,
        post=post,
        notification_type=f"post.{action}",
        title=title,
        message=message,
    )


@router.post("/{post_id}/submit-for-review", response_model=PostResponse)
async def submit_for_review(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: ReviewAction | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Send a draft into review."""
    return await _run_transition(
        account_id, post_id, current_user, db, "submit",
        (payload.comment if payload else None), permission=CONTENT_CREATE,
    )


@router.post("/{post_id}/approve", response_model=PostResponse)
async def approve_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: ReviewAction | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Approve a post.

    Where it lands depends on the workspace: with client approval enabled, a
    manager's approval moves it to CLIENT_REVIEW and only the client's reaches
    APPROVED. An internal approval must not be able to stand in for the
    customer's.
    """
    return await _run_transition(
        account_id, post_id, current_user, db, "approve",
        (payload.comment if payload else None), permission=CONTENT_APPROVE,
    )


@router.post("/{post_id}/request-changes", response_model=PostResponse)
async def request_changes(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: ReviewAction,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Send a post back with a reason. The comment is required."""
    return await _run_transition(
        account_id, post_id, current_user, db, "request_changes",
        payload.comment, permission=CONTENT_APPROVE,
    )


@router.post("/{post_id}/withdraw", response_model=PostResponse)
async def withdraw_from_review(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: ReviewAction | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Pull a post back out of review, e.g. to keep editing it."""
    return await _run_transition(
        account_id, post_id, current_user, db, "withdraw",
        (payload.comment if payload else None), permission=CONTENT_CREATE,
    )


@router.get("/{post_id}/review", response_model=ReviewState)
async def get_review_state(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Everything the review panel needs, in one call."""
    member, post, account = await _review_context(
        account_id, post_id, current_user, db, permission=CONTENT_VIEW
    )
    config = approvals.settings_for(account)
    comments = (
        await db.execute(
            select(PostComment)
            .options(selectinload(PostComment.author))
            .where(PostComment.post_id == post_id, PostComment.deleted_at.is_(None))
            .order_by(PostComment.created_at)
        )
    ).scalars().all()

    return ReviewState(
        post_id=post.id,
        status=post.status.value,
        approvals_required=config.approvals_required,
        client_approval_required=config.client_approval_required,
        allowed_actions=approvals.allowed_actions(member, account, post),
        assigned_to=post.assigned_to,
        due_at=post.due_at,
        approved_by=post.approved_by,
        approved_at=post.approved_at,
        rejection_reason=post.rejection_reason,
        comments=[_comment_response(c) for c in comments],
    )


@router.patch("/{post_id}/assignment", response_model=PostResponse)
async def update_assignment(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Assign a post and set a deadline."""
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    post = await _get_post_or_404(post_id, account_id, db)

    updates = payload.model_dump(exclude_unset=True)
    if "assigned_to" in updates and updates["assigned_to"] is not None:
        # Assigning someone who is not on the workspace would create a task
        # nobody can see, and leak that the user id exists.
        assignee = (
            await db.execute(
                select(TeamMember).where(
                    TeamMember.account_id == account_id,
                    TeamMember.user_id == updates["assigned_to"],
                    TeamMember.invitation_status == InvitationStatus.ACCEPTED,
                )
            )
        ).scalar_one_or_none()
        if assignee is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That person is not a member of this workspace.",
            )

    for field_name, value in updates.items():
        setattr(post, field_name, value)
    await db.flush()

    if updates.get("assigned_to"):
        await approvals.notify(
            db,
            recipients={updates["assigned_to"]},
            account_id=account_id,
            actor=current_user,
            post=post,
            notification_type="post.assigned",
            title="A post was assigned to you",
            message=f"{current_user.full_name} assigned '{_post_label(post)}' to you.",
        )

    await log_activity(
        db, user_id=current_user.id, account_id=account_id,
        action="post.assigned", category="post",
        description=f"Assignment changed on '{_post_label(post)}'",
        resource_type="post", resource_id=str(post.id),
        resource_name=_post_label(post),
    )
    await db.refresh(post)
    return PostResponse.model_validate(post)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def _comment_response(comment: PostComment) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author=(
            CommentAuthor.model_validate(comment.author) if comment.author else None
        ),
        body=comment.body,
        mentions=[uuid.UUID(str(m)) for m in (comment.mentions or [])],
        parent_id=comment.parent_id,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
    )


@router.get("/{post_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    await _get_post_or_404(post_id, account_id, db)

    comments = (
        await db.execute(
            select(PostComment)
            .options(selectinload(PostComment.author))
            .where(PostComment.post_id == post_id, PostComment.deleted_at.is_(None))
            .order_by(PostComment.created_at)
        )
    ).scalars().all()
    return [_comment_response(c) for c in comments]


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Comment on a post, notifying anyone mentioned.

    CONTENT_VIEW rather than CONTENT_CREATE: a CLIENT reviewing a post has to
    be able to say why they are rejecting it, and they cannot create content.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    post = await _get_post_or_404(post_id, account_id, db)

    if payload.parent_id is not None:
        parent = (
            await db.execute(
                select(PostComment).where(
                    PostComment.id == payload.parent_id,
                    PostComment.post_id == post_id,
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The comment being replied to does not exist on this post.",
            )

    mentioned = await approvals.parse_mentions(db, payload.body, account_id)
    comment = PostComment(
        id=uuid.uuid4(),
        post_id=post_id,
        author_id=current_user.id,
        body=payload.body,
        mentions=[str(m) for m in mentioned],
        parent_id=payload.parent_id,
    )
    db.add(comment)
    await db.flush()

    if mentioned:
        await approvals.notify(
            db,
            recipients=set(mentioned),
            account_id=account_id,
            actor=current_user,
            post=post,
            notification_type="post.mentioned",
            title="You were mentioned on a post",
            message=f"{current_user.full_name} mentioned you on '{_post_label(post)}'.",
        )

    await db.refresh(comment)
    comment.author = current_user
    return _comment_response(comment)


@router.patch("/{post_id}/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Edit your own comment.

    Only the author: editing someone else's words in a review thread would let
    a reviewer's objection be rewritten by the person it was aimed at.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    await _get_post_or_404(post_id, account_id, db)

    comment = await _get_comment_or_404(comment_id, post_id, db)
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments.",
        )

    comment.body = payload.body
    comment.edited_at = datetime.now(timezone.utc)
    # Mentions are re-parsed, but the people already notified are not notified
    # again -- only newly added ones.
    previous = {uuid.UUID(str(m)) for m in (comment.mentions or [])}
    mentioned = await approvals.parse_mentions(db, payload.body, account_id)
    comment.mentions = [str(m) for m in mentioned]
    await db.flush()

    added = set(mentioned) - previous
    if added:
        post = await _get_post_or_404(post_id, account_id, db)
        await approvals.notify(
            db, recipients=added, account_id=account_id, actor=current_user,
            post=post, notification_type="post.mentioned",
            title="You were mentioned on a post",
            message=f"{current_user.full_name} mentioned you on '{_post_label(post)}'.",
        )

    comment.author = current_user
    return _comment_response(comment)


@router.delete("/{post_id}/comments/{comment_id}", response_model=MessageResponse)
async def delete_comment(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Soft delete. Authors remove their own; managers can remove any."""
    member = await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_VIEW
    )
    await _get_post_or_404(post_id, account_id, db)
    comment = await _get_comment_or_404(comment_id, post_id, db)

    if comment.author_id != current_user.id and not role_has_permission(
        member.role, CONTENT_APPROVE
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments.",
        )

    comment.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return MessageResponse(message="Comment deleted.")


async def _get_comment_or_404(
    comment_id: uuid.UUID, post_id: uuid.UUID, db: AsyncSession
) -> PostComment:
    comment = (
        await db.execute(
            select(PostComment).where(
                PostComment.id == comment_id,
                PostComment.post_id == post_id,
                PostComment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    return comment


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


# ---------------------------------------------------------------------------
# Per-platform variants
#
# One post, customised per platform. The master Post holds the content an
# author writes once; a variant overrides it for one platform, and every field
# it leaves NULL keeps following the master as that is edited.
# ---------------------------------------------------------------------------

def _variant_response(variant: PostVariant) -> PostVariantResponse:
    return PostVariantResponse(
        id=variant.id,
        post_id=variant.post_id,
        platform_slug=variant.platform_slug,
        content=variant.content,
        media=list(variant.media or []),
        link_url=variant.link_url,
        alt_texts=dict(variant.alt_texts or {}),
        thumbnail_media_id=variant.thumbnail_media_id,
        first_comment=variant.first_comment,
        overrides=variant.overrides,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


@router.get("/{post_id}/variants", response_model=list[PostVariantResponse])
async def list_post_variants(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    await _get_post_or_404(post_id, account_id, db)

    variants = (
        await db.execute(
            select(PostVariant)
            .where(PostVariant.post_id == post_id)
            .order_by(PostVariant.platform_slug)
        )
    ).scalars().all()
    return [_variant_response(v) for v in variants]


@router.put("/{post_id}/variants/{platform_slug}", response_model=PostVariantResponse)
async def upsert_post_variant(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    platform_slug: str,
    payload: PostVariantUpsert,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create or replace one platform's variant.

    PUT rather than POST/PATCH because a platform has at most one variant, so
    the slug fully identifies it -- the composer can save a tab without first
    knowing whether a variant already exists.
    """
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    await _get_post_or_404(post_id, account_id, db)

    # Normalise through the registry so "x", "X (Twitter)" and "twitter" all
    # address the same variant -- otherwise a post could carry two.
    slug = get_provider(platform_slug).slug

    variant = (
        await db.execute(
            select(PostVariant).where(
                PostVariant.post_id == post_id, PostVariant.platform_slug == slug
            )
        )
    ).scalar_one_or_none()

    if variant is None:
        variant = PostVariant(id=uuid.uuid4(), post_id=post_id, platform_slug=slug)
        db.add(variant)

    # exclude_unset so an omitted field keeps whatever the variant already had,
    # while an explicit null clears the override back to inheriting.
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if field_name == "media" and value is not None:
            value = [str(v) for v in value]
        setattr(variant, field_name, value)

    await db.flush()
    await db.refresh(variant)
    return _variant_response(variant)


@router.delete("/{post_id}/variants/{platform_slug}", response_model=MessageResponse)
async def delete_post_variant(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    platform_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Drop a platform's customisation; it goes back to the master post."""
    await _verify_account_access(
        account_id, current_user, db, permission=CONTENT_CREATE
    )
    await _get_post_or_404(post_id, account_id, db)
    slug = get_provider(platform_slug).slug

    variant = (
        await db.execute(
            select(PostVariant).where(
                PostVariant.post_id == post_id, PostVariant.platform_slug == slug
            )
        )
    ).scalar_one_or_none()
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {slug} variant on this post.",
        )

    await db.delete(variant)
    await db.flush()
    return MessageResponse(
        message=f"The {slug} version now follows the master post."
    )


@router.get("/{post_id}/variants/{platform_slug}/preview", response_model=ResolvedPreview)
async def preview_post_variant(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    platform_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """What this platform would actually publish, master and variant combined.

    The same resolution the publish path uses, so a preview cannot disagree
    with what goes out.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    post = await _get_post_or_404(post_id, account_id, db)
    slug = get_provider(platform_slug).slug

    resolved = resolve_content(post, slug, variant_for_slug(post, slug))
    return ResolvedPreview(
        platform=slug,
        content=resolved.content,
        media=[uuid.UUID(str(m)) for m in resolved.media_urls if _is_uuid(m)],
        link_url=resolved.link_url,
        first_comment=resolved.first_comment,
        overrides=list(resolved.overridden),
    )


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


@router.post("/{post_id}/validate", response_model=PostValidationResponse)
async def validate_post_endpoint(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Check the post against every target platform's capabilities.

    Read-only, and deliberately a separate call rather than a gate on save: an
    author should be able to save a draft that is not yet publishable. The
    composer calls this as they type; publishing calls it before scheduling.
    """
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_VIEW)
    post = await _get_post_or_404(post_id, account_id, db)
    return PostValidationResponse(
        **await post_validation.validate_post(db, post, account_id=account_id)
    )
