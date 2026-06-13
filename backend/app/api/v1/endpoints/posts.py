"""Post management endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
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
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return PostResponse.model_validate(post)


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


@router.post("/{post_id}/publish", response_model=PostResponse)
async def publish_post(
    account_id: uuid.UUID,
    post_id: uuid.UUID,
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

    # TODO: Dispatch background task to publish to each platform via Celery / ARQ
    # background_tasks.add_task(publish_to_platforms, post.id)

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
