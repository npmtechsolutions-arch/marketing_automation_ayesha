"""Post management endpoints."""

import asyncio
import uuid
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount
from app.models.post import Post, PostStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.post import PostCreate, PostResponse, PostUpdate, PostWithPerformance
from app.services.activity_service import log_activity
from app.services.entitlements import enforce_post_limit
from app.core.authz import verify_account_access as _verify_account_access
from app.connectors.base import MediaRef, NotSupportedError, variant_for
from app.connectors.registry import get_provider
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

# Caps how many posts publish to the social platforms at the same time across the
# whole process. Both the immediate-publish endpoint and the scheduled-post
# worker funnel through publish_to_platforms(), so this single semaphore bounds
# total publish concurrency and protects CPU, the thread pool and DB connections
# during a burst (e.g. many users' scheduled posts firing at once).
_PUBLISH_SEMAPHORE = asyncio.Semaphore(settings.MAX_CONCURRENT_PUBLISHES)


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


async def publish_to_platforms(post_id: uuid.UUID):
    """Publish a post to all its target platforms, bounded by a global
    concurrency limit.

    A burst of simultaneous publishes (many scheduled posts becoming due at the
    same time, or several users hitting publish at once) would otherwise spawn
    unbounded blocking work — ffmpeg renders, platform HTTP calls, one DB session
    each — and saturate the single web process. The semaphore is acquired BEFORE
    opening a DB session so queued publishes wait without holding a connection.
    """
    async with _PUBLISH_SEMAPHORE:
        await _do_publish_to_platforms(post_id)


async def _do_publish_to_platforms(post_id: uuid.UUID):
    from app.models.platform import SocialAccount
    import logging

    async with AsyncSessionLocal() as session:
        try:
            # Fetch post
            result = await session.execute(
                select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
            )
            post = result.scalar_one_or_none()
            if not post:
                return

            targets = post.target_accounts or []
            if not targets:
                post.status = PostStatus.PUBLISHED
                post.published_at = datetime.now(timezone.utc)
                from app.models.post_performance import PostPerformance
                session.add(PostPerformance(
                    id=uuid.uuid4(),
                    post_id=post.id,
                    platform_type="instagram",
                    impressions=0,
                    reach=0,
                    likes=0,
                    comments=0,
                    shares=0,
                    saves=0,
                    clicks=0,
                    video_views=0,
                    engagement_rate=0.0,
                    click_through_rate=0.0,
                ))
                await session.flush()
                await session.commit()
                return

            success_count = 0
            failed_count = 0
            posting_results = []

            for target in targets:
                sa_id = target.get("social_account_id")
                if not sa_id:
                    continue

                try:
                    sa_uuid = uuid.UUID(sa_id)
                except ValueError:
                    failed_count += 1
                    continue

                sa_result = await session.execute(
                    select(SocialAccount)
                    .options(selectinload(SocialAccount.platform))
                    .where(SocialAccount.id == sa_uuid)
                )
                sa = sa_result.scalar_one_or_none()
                if not sa:
                    failed_count += 1
                    posting_results.append({
                        "social_account_id": sa_id,
                        "status": "failed",
                        "error": "Social account not found",
                    })
                    continue

                platform_name = (sa.platform.name if sa.platform else "").lower()
                platform_slug = (sa.platform.slug if sa.platform else "").lower() or platform_name

                # Auto-refresh OAuth tokens if expired/expiring
                await _ensure_valid_token(sa, session)

                # One registry lookup replaces the if/elif chain that used to
                # live here. The provider owns the platform's quirks, including
                # turning an exception into a result -- so this loop no longer
                # needs its own try/except around the publish itself.
                provider = get_provider(platform_slug)
                variant = variant_for(post, provider.slug)
                media = [MediaRef(url=u) for u in variant.media_urls]
                result = await provider.publish_post(variant, media, sa)

                if result.succeeded:
                    success_count += 1
                    posting_results.append({
                        "social_account_id": sa_id,
                        "status": "published",
                        "external_post_id": result.external_post_id,
                        "post_url": result.post_url or f"https://mock-{platform_slug}.com/posts/{result.external_post_id}",
                    })
                else:
                    failed_count += 1
                    entry = {
                        "social_account_id": sa_id,
                        "status": result.status,
                        "error": result.error,
                    }
                    # Kept out of the payload when false so existing consumers
                    # of posting_results see the shape they always have.
                    if result.retryable:
                        entry["retryable"] = True
                    posting_results.append(entry)

            if success_count > 0 and failed_count == 0:
                post.status = PostStatus.PUBLISHED
                post.published_at = datetime.now(timezone.utc)
                post.error_message = None
            elif success_count > 0 and failed_count > 0:
                post.status = PostStatus.PARTIALLY_PUBLISHED
                post.published_at = datetime.now(timezone.utc)
                failed_item = next((r for r in posting_results if r.get("status") in ("failed", "manual_required")), None)
                post.error_message = failed_item.get("error") if failed_item else "Some account postings failed"
            else:
                post.status = PostStatus.FAILED
                failed_item = next((r for r in posting_results if r.get("status") in ("failed", "manual_required")), None)
                post.error_message = failed_item.get("error") if failed_item else "Publishing failed"

            if success_count > 0:
                from app.models.post_performance import PostPerformance
                for res_item in posting_results:
                    if res_item["status"] == "published":
                        sa_id = res_item["social_account_id"]
                        try:
                            sa_uuid = uuid.UUID(sa_id)
                            sa_result = await session.execute(
                                select(SocialAccount).where(SocialAccount.id == sa_uuid)
                            )
                            sa = sa_result.scalar_one_or_none()
                            platform_type = (sa.platform.slug if sa and sa.platform else "instagram").lower()
                        except Exception:
                            platform_type = "instagram"
                        
                        session.add(PostPerformance(
                            id=uuid.uuid4(),
                            post_id=post.id,
                            platform_type=platform_type,
                            impressions=0,
                            reach=0,
                            likes=0,
                            comments=0,
                            shares=0,
                            saves=0,
                            clicks=0,
                            video_views=0,
                            engagement_rate=0.0,
                            click_through_rate=0.0,
                        ))

            post.posting_results = posting_results

            if post.status == PostStatus.PUBLISHED:
                activity_status, verb = "success", "Published"
            elif post.status == PostStatus.PARTIALLY_PUBLISHED:
                activity_status, verb = "warning", "Partially published"
            else:
                activity_status, verb = "failed", "Failed to publish"
            total_targets = success_count + failed_count
            await log_activity(
                session,
                user_id=post.user_id,
                account_id=post.account_id,
                action="post.published",
                category="post",
                description=(
                    f"{verb} post '{_post_label(post)}' "
                    f"({success_count}/{total_targets} account(s) succeeded)"
                ),
                resource_type="post",
                resource_id=str(post.id),
                resource_name=_post_label(post),
                status=activity_status,
            )

            await session.flush()
            await session.commit()

        except Exception as e:
            await session.rollback()
            logging.getLogger(__name__).exception("Failed to run publish background task: %s", e)
            try:
                async with AsyncSessionLocal() as fail_session:
                    db_post = await fail_session.get(Post, post_id)
                    if db_post:
                        db_post.status = PostStatus.FAILED
                        db_post.error_message = f"Failed to run publish background task: {str(e)}"
                        await fail_session.commit()
            except Exception as final_err:
                logging.getLogger(__name__).error("Failed to mark post as failed in DB: %s", final_err)


@router.post("/{post_id}/publish", response_model=PostResponse)
async def publish_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Publish a post immediately. Sets status to 'publishing' and triggers a background task."""
    await _verify_account_access(account_id, current_user, db, permission=CONTENT_PUBLISH)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (PostStatus.DRAFT, PostStatus.APPROVED, PostStatus.SCHEDULED, PostStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish a post with status '{post.status.value}'",
        )

    post.status = PostStatus.PUBLISHING
    post.published_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(post)
    await db.commit()

    background_tasks.add_task(publish_to_platforms, post.id)

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
