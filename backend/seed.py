"""Seed script to create test users, platforms, accounts, and sample data."""

import asyncio
import uuid
import random
from datetime import datetime, timezone, timedelta

from app.core.database import engine, AsyncSessionLocal, Base
from app.core.security import get_password_hash
from app.models.user import User
from app.models.account import Account, SubscriptionTier, SubscriptionStatus
from app.models.team_member import TeamMember, TeamRole, InvitationStatus
from app.models.business import Business
from app.models.platform import SocialPlatform, SocialAccount
from app.models.post import Post, PostStatus
from app.models.post_performance import PostPerformance
from app.models.notification import Notification
from app.models.strategy import Strategy
from app.models.audit_log import ActivityLog


async def seed():
    # Drop and recreate all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")

    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)

        # ── Users ────────────────────────────────────────────────
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="user@gmail.com",
            password_hash=get_password_hash("user123"),
            full_name="John Marketing",
            is_active=True,
            is_superadmin=False,
            email_verified=True,
            last_login_at=now,
        )
        session.add(user)
        print("✅ User created: user@gmail.com / user123")

        admin_id = uuid.uuid4()
        admin = User(
            id=admin_id,
            email="admin@gmail.com",
            password_hash=get_password_hash("admin123"),
            full_name="Admin SuperUser",
            is_active=True,
            is_superadmin=True,
            email_verified=True,
            last_login_at=now,
        )
        session.add(admin)
        print("✅ Admin created: admin@gmail.com / admin123")

        # ── Accounts (Agency) ────────────────────────────────────
        user_account_id = uuid.uuid4()
        user_account = Account(
            id=user_account_id,
            name="Digital Spark Agency",
            slug="digital-spark-agency",
            owner_id=user_id,
            subscription_tier=SubscriptionTier.GROWTH,
            subscription_status=SubscriptionStatus.ACTIVE,
            monthly_post_limit=100,
            max_team_members=10,
            max_platforms=20,
            trial_ends_at=now + timedelta(days=14),
        )
        session.add(user_account)
        session.add(TeamMember(
            id=uuid.uuid4(), user_id=user_id, account_id=user_account_id,
            role=TeamRole.OWNER, invitation_status=InvitationStatus.ACCEPTED,
            accepted_at=now,
        ))
        print("✅ Agency created: Digital Spark Agency (Growth plan)")

        admin_account_id = uuid.uuid4()
        admin_account = Account(
            id=admin_account_id,
            name="MarketEngine Admin",
            slug="marketengine-admin",
            owner_id=admin_id,
            subscription_tier=SubscriptionTier.PRO,
            subscription_status=SubscriptionStatus.ACTIVE,
            monthly_post_limit=999999,
            max_team_members=50,
            max_platforms=100,
        )
        session.add(admin_account)
        session.add(TeamMember(
            id=uuid.uuid4(), user_id=admin_id, account_id=admin_account_id,
            role=TeamRole.OWNER, invitation_status=InvitationStatus.ACCEPTED,
            accepted_at=now,
        ))
        print("✅ Admin agency created: MarketEngine Admin (Pro plan)")

        # ── Business ─────────────────────────────────────────────
        business_id = uuid.uuid4()
        business = Business(
            id=business_id,
            account_id=user_account_id,
            name="TechStartup Pro",
            industry="Technology",
            description="AI-powered productivity tools for remote teams.",
            website="https://techstartuppro.com",
            target_audience={"age_range": "25-45", "interests": ["technology", "AI", "remote work"]},
            brand_voice={"tone": ["professional", "innovative"], "style": "Conversational yet authoritative"},
            goals={"primary": "Increase brand awareness", "secondary": ["drive traffic", "generate leads"]},
        )
        session.add(business)
        print("✅ Business created: TechStartup Pro")

        # ── Social Platforms (user-defined) ──────────────────────
        platforms_data = [
            {"name": "Facebook", "slug": "facebook", "icon": "facebook", "color": "#1877F2",
             "description": "Meta's social networking platform",
             "base_url": "https://graph.facebook.com/v18.0",
             "api_config_template": {"fields": [
                 {"key": "app_id", "label": "App ID", "type": "text", "required": True},
                 {"key": "app_secret", "label": "App Secret", "type": "password", "required": True},
                 {"key": "page_id", "label": "Page ID", "type": "text", "required": True},
             ]}},
            {"name": "Instagram", "slug": "instagram", "icon": "instagram", "color": "#E4405F",
             "description": "Photo and video sharing platform",
             "base_url": "https://graph.facebook.com/v18.0",
             "api_config_template": {"fields": [
                 {"key": "app_id", "label": "App ID", "type": "text", "required": True},
                 {"key": "app_secret", "label": "App Secret", "type": "password", "required": True},
                 {"key": "ig_user_id", "label": "Instagram User ID", "type": "text", "required": True},
             ]}},
            {"name": "LinkedIn", "slug": "linkedin", "icon": "linkedin", "color": "#0A66C2",
             "description": "Professional networking platform",
             "base_url": "https://api.linkedin.com/v2",
             "api_config_template": {"fields": [
                 {"key": "client_id", "label": "Client ID", "type": "text", "required": True},
                 {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
                 {"key": "organization_id", "label": "Organization ID", "type": "text", "required": False},
             ]}},
            {"name": "X (Twitter)", "slug": "twitter", "icon": "twitter", "color": "#000000",
             "description": "Microblogging and social networking",
             "base_url": "https://api.twitter.com/2",
             "api_config_template": {"fields": [
                 {"key": "api_key", "label": "API Key", "type": "text", "required": True},
                 {"key": "api_secret", "label": "API Secret", "type": "password", "required": True},
                 {"key": "bearer_token", "label": "Bearer Token", "type": "password", "required": True},
             ]}},
            {"name": "YouTube", "slug": "youtube", "icon": "youtube", "color": "#FF0000",
             "description": "Video sharing platform",
             "base_url": "https://www.googleapis.com/youtube/v3",
             "api_config_template": {"fields": [
                 {"key": "api_key", "label": "API Key", "type": "text", "required": True},
                 {"key": "channel_id", "label": "Channel ID", "type": "text", "required": True},
             ]}},
            {"name": "TikTok", "slug": "tiktok", "icon": "tiktok", "color": "#010101",
             "description": "Short-form video platform",
             "base_url": "https://open.tiktokapis.com/v2",
             "api_config_template": {"fields": [
                 {"key": "client_key", "label": "Client Key", "type": "text", "required": True},
                 {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True},
             ]}},
        ]

        platform_ids = {}
        for i, pdata in enumerate(platforms_data):
            pid = uuid.uuid4()
            platform_ids[pdata["slug"]] = pid
            session.add(SocialPlatform(
                id=pid, user_id=user_id, account_id=user_account_id,
                name=pdata["name"], slug=pdata["slug"], icon=pdata["icon"],
                color=pdata["color"], description=pdata["description"],
                base_url=pdata["base_url"],
                api_config_template=pdata["api_config_template"],
                sort_order=i, is_active=True,
            ))
        print(f"✅ {len(platforms_data)} social platforms created")

        # ── Social Accounts (multiple per platform) ──────────────
        accounts_data = [
            {"platform": "facebook", "name": "Acme Corp Facebook", "handle": "@acmecorp",
             "profile_url": "https://facebook.com/acmecorp", "verified": True},
            {"platform": "facebook", "name": "TechStartup Pro Page", "handle": "@techstartuppro",
             "profile_url": "https://facebook.com/techstartuppro", "verified": True},
            {"platform": "instagram", "name": "Acme Corp Instagram", "handle": "@acmecorp",
             "profile_url": "https://instagram.com/acmecorp", "verified": True},
            {"platform": "instagram", "name": "TechStartup Pro IG", "handle": "@techstartuppro",
             "profile_url": "https://instagram.com/techstartuppro", "verified": True},
            {"platform": "instagram", "name": "Digital Spark Studio", "handle": "@digispark",
             "profile_url": "https://instagram.com/digispark", "verified": False},
            {"platform": "linkedin", "name": "Acme Corp LinkedIn", "handle": "acme-corp",
             "profile_url": "https://linkedin.com/company/acme-corp", "verified": True},
            {"platform": "linkedin", "name": "John Marketing Personal", "handle": "johnmarketing",
             "profile_url": "https://linkedin.com/in/johnmarketing", "verified": True},
            {"platform": "twitter", "name": "TechStartup Pro X", "handle": "@techstartup",
             "profile_url": "https://x.com/techstartup", "verified": True},
            {"platform": "youtube", "name": "TechStartup Pro Channel", "handle": "@TechStartupPro",
             "profile_url": "https://youtube.com/@TechStartupPro", "verified": False},
            {"platform": "tiktok", "name": "Digital Spark TikTok", "handle": "@digispark",
             "profile_url": "https://tiktok.com/@digispark", "verified": False},
        ]

        social_account_ids = {}
        for adata in accounts_data:
            said = uuid.uuid4()
            social_account_ids[adata["name"]] = said
            session.add(SocialAccount(
                id=said, user_id=user_id, account_id=user_account_id,
                platform_id=platform_ids[adata["platform"]],
                account_name=adata["name"],
                account_handle=adata["handle"],
                profile_url=adata["profile_url"],
                is_active=True,
                is_verified=adata["verified"],
                last_verified_at=now - timedelta(hours=2) if adata["verified"] else None,
                access_token="mock_access_token_" + said.hex[:8],
                api_key="mock_api_key_" + said.hex[:8],
                config={"mock": True},
                metadata_={"followers": random.randint(500, 50000), "following": random.randint(100, 5000)},
            ))
        print(f"✅ {len(accounts_data)} social accounts created across platforms")

        # ── Strategy ─────────────────────────────────────────────
        strategy_id = uuid.uuid4()
        session.add(Strategy(
            id=strategy_id, user_id=user_id, account_id=user_account_id,
            business_id=business_id,
            name="Q2 Multi-Platform Growth",
            goal="Increase brand awareness across all client accounts",
            platform_mix={"instagram": 35, "linkedin": 25, "facebook": 20, "twitter": 15, "tiktok": 5},
            posting_frequency={"instagram": 5, "linkedin": 3, "facebook": 3, "twitter": 7, "tiktok": 2},
            content_themes=["Product tips", "Behind-the-scenes", "Industry insights", "Client spotlights", "Team culture"],
            reasoning="Instagram and LinkedIn provide the best ROI for B2B tech audiences. Twitter for real-time engagement. TikTok for experimental short-form content.",
            confidence_score=0.91, is_active=True,
        ))
        print("✅ Strategy created: Q2 Multi-Platform Growth")

        # ── Posts targeting multiple accounts ─────────────────────
        sa = social_account_ids  # shorthand
        posts_data = [
            {
                "content": "🚀 Excited to announce our new AI-powered feature that helps remote teams collaborate 3x faster! Check it out at techstartuppro.com/ai-collab #AI #RemoteWork #Productivity",
                "title": "AI Collaboration Feature Launch",
                "hashtags": ["AI", "RemoteWork", "Productivity", "TechStartup"],
                "target_accounts": [
                    {"social_account_id": str(sa["Acme Corp Instagram"]), "platform_name": "Instagram", "account_name": "Acme Corp Instagram"},
                    {"social_account_id": str(sa["TechStartup Pro IG"]), "platform_name": "Instagram", "account_name": "TechStartup Pro IG"},
                    {"social_account_id": str(sa["Acme Corp LinkedIn"]), "platform_name": "LinkedIn", "account_name": "Acme Corp LinkedIn"},
                ],
                "status": PostStatus.PUBLISHED,
                "published_at": now - timedelta(days=5),
                "ai_generated": True,
                "posting_results": [
                    {"social_account_id": str(sa["Acme Corp Instagram"]), "status": "published", "post_url": "https://instagram.com/p/abc123"},
                    {"social_account_id": str(sa["TechStartup Pro IG"]), "status": "published", "post_url": "https://instagram.com/p/def456"},
                    {"social_account_id": str(sa["Acme Corp LinkedIn"]), "status": "published", "post_url": "https://linkedin.com/posts/789"},
                ],
            },
            {
                "content": "The future of work is here. Our latest blog post explores 5 ways AI is transforming team productivity. Link in bio! 💡",
                "title": "5 Ways AI Transforms Productivity",
                "hashtags": ["FutureOfWork", "AI", "TeamProductivity"],
                "target_accounts": [
                    {"social_account_id": str(sa["Acme Corp Facebook"]), "platform_name": "Facebook", "account_name": "Acme Corp Facebook"},
                    {"social_account_id": str(sa["TechStartup Pro Page"]), "platform_name": "Facebook", "account_name": "TechStartup Pro Page"},
                ],
                "status": PostStatus.PUBLISHED,
                "published_at": now - timedelta(days=3),
                "ai_generated": True,
                "posting_results": [
                    {"social_account_id": str(sa["Acme Corp Facebook"]), "status": "published", "post_url": "https://facebook.com/post/111"},
                    {"social_account_id": str(sa["TechStartup Pro Page"]), "status": "published", "post_url": "https://facebook.com/post/222"},
                ],
            },
            {
                "content": "Behind the scenes at our engineering sprint 🧵 We shipped a major update in record time. Here's how we did it...",
                "title": "Engineering Sprint BTS",
                "hashtags": ["BehindTheScenes", "Engineering", "Startup"],
                "target_accounts": [
                    {"social_account_id": str(sa["TechStartup Pro X"]), "platform_name": "X (Twitter)", "account_name": "TechStartup Pro X"},
                    {"social_account_id": str(sa["John Marketing Personal"]), "platform_name": "LinkedIn", "account_name": "John Marketing Personal"},
                ],
                "status": PostStatus.PUBLISHED,
                "published_at": now - timedelta(days=1),
                "ai_generated": False,
                "posting_results": [
                    {"social_account_id": str(sa["TechStartup Pro X"]), "status": "published", "post_url": "https://x.com/status/333"},
                    {"social_account_id": str(sa["John Marketing Personal"]), "status": "published", "post_url": "https://linkedin.com/posts/444"},
                ],
            },
            {
                "content": "📊 Weekly tip: Use analytics to track which content resonates most. Data-driven decisions = better results!",
                "title": "Weekly Analytics Tip",
                "hashtags": ["Analytics", "DataDriven", "MarketingTips"],
                "target_accounts": [
                    {"social_account_id": str(sa["Acme Corp Instagram"]), "platform_name": "Instagram", "account_name": "Acme Corp Instagram"},
                    {"social_account_id": str(sa["Acme Corp LinkedIn"]), "platform_name": "LinkedIn", "account_name": "Acme Corp LinkedIn"},
                    {"social_account_id": str(sa["TechStartup Pro X"]), "platform_name": "X (Twitter)", "account_name": "TechStartup Pro X"},
                    {"social_account_id": str(sa["Acme Corp Facebook"]), "platform_name": "Facebook", "account_name": "Acme Corp Facebook"},
                ],
                "status": PostStatus.SCHEDULED,
                "scheduled_at": now + timedelta(days=1, hours=10),
                "ai_generated": True,
            },
            {
                "content": "Join us for a live Q&A this Thursday at 2 PM EST! We'll discuss AI trends in marketing. Drop your questions! 🎙️",
                "title": "Live Q&A Announcement",
                "hashtags": ["LiveQA", "AI", "Marketing", "Community"],
                "target_accounts": [
                    {"social_account_id": str(sa["TechStartup Pro IG"]), "platform_name": "Instagram", "account_name": "TechStartup Pro IG"},
                    {"social_account_id": str(sa["Digital Spark Studio"]), "platform_name": "Instagram", "account_name": "Digital Spark Studio"},
                ],
                "status": PostStatus.SCHEDULED,
                "scheduled_at": now + timedelta(days=3, hours=14),
                "ai_generated": True,
            },
            {
                "content": "Customer spotlight: How @acme_corp increased productivity by 40% using our platform. Full case study coming soon!",
                "title": "Acme Corp Case Study Teaser",
                "hashtags": ["CustomerSuccess", "CaseStudy", "Productivity"],
                "target_accounts": [
                    {"social_account_id": str(sa["Acme Corp LinkedIn"]), "platform_name": "LinkedIn", "account_name": "Acme Corp LinkedIn"},
                ],
                "status": PostStatus.DRAFT,
                "ai_generated": False,
            },
            {
                "content": "🎨 New product photography just dropped! Swipe through our latest brand shoot for TechStartup Pro →",
                "title": "Brand Photography Showcase",
                "hashtags": ["BrandPhotography", "ProductShoot", "Design"],
                "target_accounts": [
                    {"social_account_id": str(sa["Acme Corp Instagram"]), "platform_name": "Instagram", "account_name": "Acme Corp Instagram"},
                    {"social_account_id": str(sa["TechStartup Pro IG"]), "platform_name": "Instagram", "account_name": "TechStartup Pro IG"},
                ],
                "status": PostStatus.PREVIEW,
                "ai_generated": True,
                "ai_images": [
                    {"url": "/mock/ai-photo-1.jpg", "prompt": "Modern tech office with team collaboration", "model": "dall-e-3"},
                    {"url": "/mock/ai-photo-2.jpg", "prompt": "Minimalist product shot of laptop with dashboard", "model": "dall-e-3"},
                ],
                "digital_assets": [
                    {"url": "/mock/photo-1.jpg", "type": "photo", "filters": {"brightness": 1.1, "contrast": 1.05, "saturation": 1.2}},
                ],
                "device_previews": {
                    "mobile": {"width": 375, "height": 812, "scale": 2},
                    "tablet": {"width": 768, "height": 1024, "scale": 2},
                    "web": {"width": 1280, "height": 720, "scale": 1},
                },
            },
        ]

        post_ids = []
        for pdata in posts_data:
            pid = uuid.uuid4()
            post_ids.append(pid)
            session.add(Post(
                id=pid, user_id=user_id, account_id=user_account_id,
                business_id=business_id, strategy_id=strategy_id,
                content=pdata["content"],
                title=pdata.get("title"),
                hashtags=pdata["hashtags"],
                target_accounts=pdata["target_accounts"],
                posting_results=pdata.get("posting_results"),
                status=pdata["status"],
                published_at=pdata.get("published_at"),
                scheduled_at=pdata.get("scheduled_at"),
                ai_generated=pdata["ai_generated"],
                ai_model="gpt-4o" if pdata["ai_generated"] else None,
                ai_images=pdata.get("ai_images"),
                digital_assets=pdata.get("digital_assets"),
                device_previews=pdata.get("device_previews"),
            ))
        print(f"✅ {len(posts_data)} posts created (published, scheduled, draft, preview)")

        # ── Performance data for published posts ─────────────────
        for i in range(3):  # first 3 are published
            post = posts_data[i]
            for ta in post["target_accounts"]:
                session.add(PostPerformance(
                    id=uuid.uuid4(), post_id=post_ids[i],
                    platform_type=ta["platform_name"].lower().split()[0],
                    impressions=random.randint(500, 8000),
                    reach=random.randint(300, 5000),
                    likes=random.randint(50, 800),
                    comments=random.randint(10, 150),
                    shares=random.randint(5, 80),
                    saves=random.randint(5, 50),
                    clicks=random.randint(20, 300),
                    engagement_rate=round(random.uniform(2.0, 9.0), 2),
                    click_through_rate=round(random.uniform(0.5, 4.0), 2),
                ))
        print("✅ Performance data created")

        # Flush everything so FKs are satisfied for activity logs
        await session.flush()

        # ── Activity Logs ────────────────────────────────────────
        activities = [
            {"action": "auth.login", "category": "auth", "description": "Logged in to the platform", "status": "success"},
            {"action": "platform.created", "category": "platform", "description": "Created platform: Facebook", "resource_type": "social_platform", "resource_name": "Facebook"},
            {"action": "platform.created", "category": "platform", "description": "Created platform: Instagram", "resource_type": "social_platform", "resource_name": "Instagram"},
            {"action": "account.created", "category": "account", "description": "Added account: Acme Corp Instagram", "resource_type": "social_account", "resource_name": "Acme Corp Instagram"},
            {"action": "account.verified", "category": "account", "description": "Verified connection: Acme Corp Instagram", "resource_type": "social_account", "resource_name": "Acme Corp Instagram"},
            {"action": "post.created", "category": "post", "description": "Created post: AI Collaboration Feature Launch", "resource_type": "post", "resource_name": "AI Collaboration Feature Launch"},
            {"action": "ai.content_generated", "category": "ai", "description": "Generated AI content for post", "resource_type": "post"},
            {"action": "post.published", "category": "post", "description": "Published to 3 accounts: Acme Corp Instagram, TechStartup Pro IG, Acme Corp LinkedIn", "resource_type": "post", "resource_name": "AI Collaboration Feature Launch"},
            {"action": "post.scheduled", "category": "post", "description": "Scheduled post: Weekly Analytics Tip for 4 accounts", "resource_type": "post", "resource_name": "Weekly Analytics Tip"},
            {"action": "ai.image_generated", "category": "ai", "description": "Generated 2 AI images for Brand Photography Showcase", "resource_type": "post"},
            {"action": "post.previewed", "category": "post", "description": "Previewed post on mobile, tablet, and web", "resource_type": "post", "resource_name": "Brand Photography Showcase"},
            {"action": "strategy.created", "category": "strategy", "description": "Created strategy: Q2 Multi-Platform Growth", "resource_type": "strategy", "resource_name": "Q2 Multi-Platform Growth"},
            {"action": "settings.updated", "category": "settings", "description": "Updated notification preferences"},
            {"action": "account.created", "category": "account", "description": "Added account: TechStartup Pro X", "resource_type": "social_account", "resource_name": "TechStartup Pro X"},
            {"action": "post.created", "category": "post", "description": "Created draft: Acme Corp Case Study Teaser", "resource_type": "post", "resource_name": "Acme Corp Case Study Teaser"},
        ]
        for i, act in enumerate(activities):
            session.add(ActivityLog(
                id=uuid.uuid4(), user_id=user_id, account_id=user_account_id,
                action=act["action"], category=act["category"],
                description=act["description"],
                resource_type=act.get("resource_type"),
                resource_name=act.get("resource_name"),
                status=act.get("status", "success"),
                ip_address="192.168.1.100",
                created_at=now - timedelta(hours=len(activities) - i),
            ))
        print(f"✅ {len(activities)} activity logs created")

        # ── Notifications ────────────────────────────────────────
        notifications = [
            {"type": "post_published", "title": "Post Published!", "message": "Your post 'AI Collaboration Feature Launch' was published to 3 accounts.", "is_read": True},
            {"type": "ai_insight", "title": "AI Insight", "message": "Posts published at 10 AM get 3x more engagement on Instagram.", "is_read": False},
            {"type": "strategy_ready", "title": "Strategy Updated", "message": "Your Q2 strategy has been optimized based on recent performance.", "is_read": False},
            {"type": "account_alert", "title": "Token Expiring", "message": "The access token for 'Digital Spark TikTok' expires in 3 days.", "is_read": False},
            {"type": "system", "title": "Welcome to MarketEngine!", "message": "Your agency is set up. Start by creating platforms and connecting accounts!", "is_read": True},
        ]
        for n in notifications:
            session.add(Notification(
                id=uuid.uuid4(), user_id=user_id, account_id=user_account_id,
                type=n["type"], title=n["title"], message=n["message"], is_read=n["is_read"],
            ))
        print(f"✅ {len(notifications)} notifications created")

        await session.commit()

    print("\n" + "=" * 55)
    print("🎉 Database seeded successfully!")
    print("=" * 55)
    print("\n📋 Test Accounts:")
    print("─" * 55)
    print("👤 Regular User (Agency Owner):")
    print("   Email:    user@gmail.com")
    print("   Password: user123")
    print("   Agency:   Digital Spark Agency (Growth)")
    print("   Platforms: 6 (Facebook, Instagram, LinkedIn, X, YouTube, TikTok)")
    print("   Accounts: 10 (multiple per platform)")
    print("   Posts:    7 (published, scheduled, draft, preview)")
    print()
    print("🔑 Admin User (Super Admin):")
    print("   Email:    admin@gmail.com")
    print("   Password: admin123")
    print("   Agency:   MarketEngine Admin (Pro)")
    print("─" * 55)


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
    asyncio.run(seed())
