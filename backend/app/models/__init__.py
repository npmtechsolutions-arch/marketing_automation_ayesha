"""SQLAlchemy models for the Marketing Automation platform."""

from app.models.account import Account, SubscriptionStatus, SubscriptionTier
from app.models.ai_generation import AIGeneration, AIGenerationStatus, GenerationType
from app.models.audit_log import ActivityLog
from app.models.business import Business
from app.models.campaign import Campaign, CampaignStatus
from app.models.notification import Notification
from app.models.permission import Permission, RolePermission, UserPermission
from app.models.platform import SocialAccount, SocialPlatform
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.models.strategy import Strategy
from app.models.team_member import InvitationStatus, TeamMember, TeamRole
from app.models.user import User
from app.models.webhook import Webhook, WebhookStatus

__all__ = [
    # Core models
    "User",
    "Account",
    "TeamMember",
    "Business",
    # Social & content
    "SocialPlatform",
    "SocialAccount",
    "Post",
    "PostPerformance",
    # Strategy & campaigns
    "Strategy",
    "Campaign",
    # System
    "Notification",
    "ActivityLog",
    "AIGeneration",
    "Webhook",
    # Permissions
    "Permission",
    "RolePermission",
    "UserPermission",
    # Enums
    "SubscriptionTier",
    "SubscriptionStatus",
    "TeamRole",
    "InvitationStatus",
    "PostStatus",
    "CampaignStatus",
    "GenerationType",
    "AIGenerationStatus",
    "WebhookStatus",
]
