"""Post management endpoints."""

import uuid
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db, AsyncSessionLocal
from app.core.deps import get_current_active_user
from app.models.platform import SocialAccount
from app.models.post import Post, PostStatus
from app.models.team_member import TeamMember, TeamRole
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.post import PostCreate, PostResponse, PostUpdate, PostWithPerformance

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _verify_account_access(
    account_id: uuid.UUID,
    user,
    db: AsyncSession,
    *,
    min_role: TeamRole | None = None,
) -> TeamMember:
    """Verify the user belongs to the account and optionally meets a minimum role."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.account_id == account_id,
            TeamMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account",
        )

    role_hierarchy = [TeamRole.VIEWER, TeamRole.EDITOR, TeamRole.MANAGER, TeamRole.ADMIN, TeamRole.OWNER]
    if min_role and role_hierarchy.index(member.role) < role_hierarchy.index(min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least {min_role.value} role",
        )
    return member


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
    await _verify_account_access(account_id, current_user, db)

    conditions = [Post.account_id == account_id, Post.deleted_at.is_(None)]

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
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)

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
    return PostResponse.model_validate(post)


async def _ensure_valid_token(sa: SocialAccount, db: AsyncSession) -> None:
    """Check if the social account's OAuth token has expired (or is expiring soon),
    and refresh it using the refresh token if available.
    """
    if not sa.token_expires_at or not sa.refresh_token:
        return

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    expires_at = sa.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > now + timedelta(minutes=2):
        return

    platform_slug = (sa.platform.slug if sa.platform else "").lower()
    
    # YouTube (Google) Refresh Flow
    if "youtube" in platform_slug:
        import httpx
        from app.core.config import settings
        
        logging.getLogger(__name__).info("YouTube token expired for account %s. Refreshing...", sa.account_name)
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "refresh_token": sa.refresh_token,
                        "grant_type": "refresh_token",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=15.0
                )
            if res.status_code == 200:
                data = res.json()
                sa.access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                sa.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                if "refresh_token" in data:
                    sa.refresh_token = data["refresh_token"]
                db.add(sa)
                await db.flush()
                logging.getLogger(__name__).info("YouTube token successfully refreshed for account %s.", sa.account_name)
            else:
                logging.getLogger(__name__).error("Failed to refresh YouTube token: %s", res.text)
        except Exception as exc:
            logging.getLogger(__name__).exception("Error refreshing YouTube token: %s", exc)

    # Twitter/X Refresh Flow
    elif "twitter" in platform_slug or platform_slug == "x":
        import httpx
        from app.core.config import settings
        import base64
        
        logging.getLogger(__name__).info("Twitter token expired for account %s. Refreshing...", sa.account_name)
        try:
            auth_str = f"{settings.TWITTER_CLIENT_ID}:{settings.TWITTER_CLIENT_SECRET}"
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.twitter.com/2/oauth2/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": sa.refresh_token,
                        "client_id": settings.TWITTER_CLIENT_ID,
                    },
                    headers={
                        "Authorization": f"Basic {b64_auth}",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=15.0
                )
            if res.status_code == 200:
                data = res.json()
                sa.access_token = data["access_token"]
                expires_in = data.get("expires_in", 7200)
                sa.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                if "refresh_token" in data:
                    sa.refresh_token = data["refresh_token"]
                db.add(sa)
                await db.flush()
                logging.getLogger(__name__).info("Twitter token successfully refreshed for account %s.", sa.account_name)
            else:
                logging.getLogger(__name__).error("Failed to refresh Twitter token: %s", res.text)
        except Exception as exc:
            logging.getLogger(__name__).exception("Error refreshing Twitter token: %s", exc)


async def _sync_post_performance(post: Post, db: AsyncSession):
    from app.services.platform_service import PlatformService
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
                select(SocialAccount).where(SocialAccount.id == sa_uuid)
            )
            sa = sa_result.scalar_one_or_none()
            if not sa:
                continue

            import asyncio
            metrics = await asyncio.to_thread(PlatformService.fetch_performance, ext_id, sa)
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
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (PostStatus.DRAFT, PostStatus.PENDING_APPROVAL):
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
    return PostResponse.model_validate(post)


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Soft-delete a post."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    post = await _get_post_or_404(post_id, account_id, db)

    post.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return MessageResponse(message="Post deleted successfully")


async def publish_to_platforms(post_id: uuid.UUID):
    from app.services.platform_service import PlatformService
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
                import random
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
                    select(SocialAccount).where(SocialAccount.id == sa_uuid)
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

                try:
                    import asyncio
                    if "facebook" in platform_slug:
                        res = await asyncio.to_thread(PlatformService.publish_to_facebook, post, sa)
                    elif "instagram" in platform_slug or "insta" in platform_slug:
                        res = await asyncio.to_thread(PlatformService.publish_to_instagram, post, sa)
                    elif "linkedin" in platform_slug:
                        res = await asyncio.to_thread(PlatformService.publish_to_linkedin, post, sa)
                    elif "youtube" in platform_slug:
                        res = await asyncio.to_thread(PlatformService.publish_to_youtube, post, sa)
                    elif "twitter" in platform_slug or platform_slug == "x":
                        res = await asyncio.to_thread(PlatformService.publish_to_twitter, post, sa)
                    else:
                        res = await asyncio.to_thread(PlatformService.publish_to_instagram, post, sa)

                    success_count += 1
                    posting_results.append({
                        "social_account_id": sa_id,
                        "status": "published",
                        "external_post_id": res.get("external_post_id"),
                        "post_url": res.get("post_url", f"https://mock-{platform_slug}.com/posts/{res.get('external_post_id')}"),
                    })
                except Exception as exc:
                    failed_count += 1
                    posting_results.append({
                        "social_account_id": sa_id,
                        "status": "failed",
                        "error": str(exc),
                    })

            if success_count > 0 and failed_count == 0:
                post.status = PostStatus.PUBLISHED
                post.published_at = datetime.now(timezone.utc)
            elif success_count > 0 and failed_count > 0:
                post.status = PostStatus.PARTIALLY_PUBLISHED
                post.published_at = datetime.now(timezone.utc)
            else:
                post.status = PostStatus.FAILED

            if success_count > 0:
                from app.models.post_performance import PostPerformance
                import random
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
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (PostStatus.DRAFT, PostStatus.APPROVED, PostStatus.SCHEDULED):
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
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
    post = await _get_post_or_404(post_id, account_id, db)

    if post.status not in (PostStatus.DRAFT, PostStatus.APPROVED):
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
    return PostResponse.model_validate(post)


@router.post("/{post_id}/duplicate", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Create a copy of an existing post as a new draft."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.EDITOR)
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
    return PostResponse.model_validate(new_post)


@router.post("/{post_id}/approve", response_model=PostResponse)
async def approve_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Approve a post. Requires manager role or above."""
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
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
    await _verify_account_access(account_id, current_user, db, min_role=TeamRole.MANAGER)
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
    return PostResponse.model_validate(post)
