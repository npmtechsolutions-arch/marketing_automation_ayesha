# Database Design Document
## Complete Database Schema with ACID Compliance

---

## 📋 Document Information

- **Product:** AI Marketing Automation Platform
- **Document Type:** Database Design Specification
- **Database:** PostgreSQL 15+
- **Last Updated:** 2025-02-16
- **Status:** Implementation Ready

---

## 🎯 Database Overview

### ACID Compliance

**Atomicity:** All transactions are atomic (all-or-nothing)
**Consistency:** Data integrity enforced through constraints
**Isolation:** Proper isolation levels prevent conflicts
**Durability:** WAL (Write-Ahead Logging) ensures data persistence

### Design Principles

1. **Normalized** to 3NF (Third Normal Form)
2. **Referential Integrity** enforced via foreign keys
3. **Soft Deletes** where data recovery needed
4. **Timestamps** on all tables (created_at, updated_at)
5. **UUIDs** for primary keys (security & distribution)
6. **Indexes** for query performance
7. **JSONB** for flexible/dynamic data

---

## 📊 Entity Relationship Diagram (ERD)

```
┌──────────┐         ┌──────────────┐         ┌──────────────┐
│  users   │────1:N──│team_members  │────N:1──│  accounts    │
└──────────┘         └──────────────┘         └──────────────┘
     │                                               │
     │                                               │
     │1:N                                           1:N
     │                                               │
┌──────────────┐                             ┌──────────────┐
│  platforms   │                             │  businesses  │
└──────────────┘                             └──────────────┘
                                                    │
                                                    │1:N
                                                    │
                                             ┌──────────────┐
                                             │    posts     │
                                             └──────────────┘
                                                    │
                                                    │1:N
                                                    │
                                             ┌──────────────┐
                                             │ post_perf    │
                                             └──────────────┘
```

---

## 📋 Complete Table Definitions

### 1. Core Tables

#### users
```sql
CREATE TABLE users (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Authentication
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT false,
    email_verified_at TIMESTAMP,
    password_hash VARCHAR(255), -- NULL for OAuth users
    
    -- Profile
    full_name VARCHAR(255),
    avatar_url TEXT,
    phone VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- System
    is_super_admin BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(50),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    is_suspended BOOLEAN DEFAULT false,
    suspension_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP -- Soft delete
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created ON users(created_at);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = true;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

#### accounts
```sql
CREATE TABLE accounts (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Account Info
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE, -- URL-friendly identifier
    website VARCHAR(500),
    
    -- Ownership
    owner_id UUID NOT NULL REFERENCES users(id),
    
    -- Subscription
    subscription_tier VARCHAR(50) DEFAULT 'free' CHECK (
        subscription_tier IN ('free', 'starter', 'growth', 'pro', 'enterprise')
    ),
    subscription_status VARCHAR(50) DEFAULT 'active' CHECK (
        subscription_status IN ('active', 'trialing', 'past_due', 'canceled', 'paused')
    ),
    trial_ends_at TIMESTAMP,
    subscription_starts_at TIMESTAMP,
    subscription_ends_at TIMESTAMP,
    
    -- Billing
    stripe_customer_id VARCHAR(255) UNIQUE,
    stripe_subscription_id VARCHAR(255),
    
    -- Usage Limits (based on tier)
    monthly_post_limit INTEGER DEFAULT 30,
    monthly_posts_used INTEGER DEFAULT 0,
    team_member_limit INTEGER DEFAULT 1,
    
    -- Settings
    settings JSONB DEFAULT '{}'::JSONB,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_accounts_owner ON accounts(owner_id);
CREATE INDEX idx_accounts_slug ON accounts(slug);
CREATE INDEX idx_accounts_stripe ON accounts(stripe_customer_id);
CREATE INDEX idx_accounts_tier ON accounts(subscription_tier);

-- Trigger
CREATE TRIGGER accounts_updated_at
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

#### team_members
```sql
CREATE TABLE team_members (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Role
    role VARCHAR(50) NOT NULL CHECK (
        role IN ('owner', 'admin', 'manager', 'editor', 'viewer')
    ),
    
    -- Invitation
    invited_by UUID REFERENCES users(id),
    invited_at TIMESTAMP DEFAULT NOW(),
    invitation_token VARCHAR(255) UNIQUE,
    invitation_expires_at TIMESTAMP,
    accepted_at TIMESTAMP,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(account_id, user_id)
);

-- Indexes
CREATE INDEX idx_team_account ON team_members(account_id);
CREATE INDEX idx_team_user ON team_members(user_id);
CREATE INDEX idx_team_role ON team_members(role);
CREATE INDEX idx_team_active ON team_members(account_id, is_active);

-- Trigger
CREATE TRIGGER team_members_updated_at
BEFORE UPDATE ON team_members
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

---

### 2. Business & Content Tables

#### businesses
```sql
CREATE TABLE businesses (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Business Info
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    description TEXT,
    website VARCHAR(500),
    logo_url TEXT,
    
    -- Target Audience
    target_audience JSONB DEFAULT '{}'::JSONB,
    -- Example: {
    --   "age_range": "25-45",
    --   "location": ["US", "UK"],
    --   "interests": ["technology", "startups"]
    -- }
    
    -- Brand Voice
    brand_voice JSONB DEFAULT '{}'::JSONB,
    -- Example: {
    --   "tone": "professional",
    --   "style": "casual",
    --   "values": ["innovation", "customer-first"]
    -- }
    
    -- Goals
    marketing_goals JSONB DEFAULT '[]'::JSONB,
    -- Example: ["increase_sales", "brand_awareness", "lead_generation"]
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_businesses_account ON businesses(account_id);
CREATE INDEX idx_businesses_industry ON businesses(industry);

-- Trigger
CREATE TRIGGER businesses_updated_at
BEFORE UPDATE ON businesses
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

#### posts
```sql
CREATE TABLE posts (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    business_id UUID REFERENCES businesses(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    approved_by UUID REFERENCES users(id),
    
    -- Content
    content TEXT NOT NULL,
    media_urls JSONB DEFAULT '[]'::JSONB, -- ["url1", "url2"]
    media_type VARCHAR(50), -- 'image', 'video', 'carousel'
    hashtags TEXT[], -- PostgreSQL array
    
    -- Platform Distribution
    platforms JSONB NOT NULL,
    -- Example: [
    --   {"type": "instagram", "platform_id": "uuid", "post_id": "ig123"},
    --   {"type": "facebook", "platform_id": "uuid", "post_id": "fb456"}
    -- ]
    
    -- Scheduling
    status VARCHAR(50) DEFAULT 'draft' CHECK (
        status IN ('draft', 'pending_approval', 'scheduled', 'publishing', 'published', 'failed')
    ),
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,
    
    -- AI Metadata
    generated_by_ai BOOLEAN DEFAULT false,
    ai_model VARCHAR(100), -- 'gpt-4-turbo', 'claude-sonnet', etc.
    ai_prompt TEXT,
    ai_generation_cost DECIMAL(10, 6), -- Track AI costs
    
    -- Strategy
    strategy_id UUID REFERENCES strategies(id),
    campaign_id UUID REFERENCES campaigns(id),
    
    -- Approval Workflow
    requires_approval BOOLEAN DEFAULT false,
    approval_requested_at TIMESTAMP,
    approval_status VARCHAR(50), -- 'pending', 'approved', 'rejected'
    rejection_reason TEXT,
    
    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_posts_account ON posts(account_id);
CREATE INDEX idx_posts_business ON posts(business_id);
CREATE INDEX idx_posts_creator ON posts(created_by);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_scheduled ON posts(scheduled_at) WHERE status = 'scheduled';
CREATE INDEX idx_posts_published ON posts(published_at) WHERE status = 'published';
CREATE INDEX idx_posts_created ON posts(created_at);

-- GIN index for JSONB queries
CREATE INDEX idx_posts_platforms ON posts USING gin(platforms);

-- Trigger
CREATE TRIGGER posts_updated_at
BEFORE UPDATE ON posts
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

#### post_performance
```sql
CREATE TABLE post_performance (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    
    -- Platform
    platform_type VARCHAR(50) NOT NULL,
    platform_post_id VARCHAR(255) NOT NULL, -- ID from the platform
    
    -- Metrics
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    video_views INTEGER DEFAULT 0,
    
    -- Calculated
    engagement_rate DECIMAL(5, 2), -- (likes+comments+shares)/reach * 100
    ctr DECIMAL(5, 2), -- Click-through rate
    
    -- Audience Demographics (from platform)
    demographics JSONB DEFAULT '{}'::JSONB,
    -- Example: {
    --   "age": {"18-24": 30, "25-34": 45, "35-44": 20, "45+": 5},
    --   "gender": {"male": 45, "female": 55},
    --   "location": {"US": 60, "UK": 25, "CA": 15}
    -- }
    
    -- Timestamps
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(post_id, platform_type)
);

-- Indexes
CREATE INDEX idx_perf_post ON post_performance(post_id);
CREATE INDEX idx_perf_platform ON post_performance(platform_type);
CREATE INDEX idx_perf_synced ON post_performance(last_synced_at);

-- Trigger
CREATE TRIGGER post_performance_updated_at
BEFORE UPDATE ON post_performance
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- Trigger to calculate engagement rate
CREATE OR REPLACE FUNCTION calculate_engagement_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.reach > 0 THEN
        NEW.engagement_rate = (
            (NEW.likes + NEW.comments + NEW.shares + NEW.saves)::DECIMAL / NEW.reach * 100
        );
    END IF;
    
    IF NEW.impressions > 0 THEN
        NEW.ctr = (NEW.clicks::DECIMAL / NEW.impressions * 100);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER post_performance_calc
BEFORE INSERT OR UPDATE ON post_performance
FOR EACH ROW
EXECUTE FUNCTION calculate_engagement_rate();
```

---

### 3. Platform Integration Tables

#### platforms
```sql
CREATE TABLE platforms (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    connected_by UUID NOT NULL REFERENCES users(id),
    
    -- Platform Info
    platform_type VARCHAR(50) NOT NULL CHECK (
        platform_type IN ('facebook', 'instagram', 'linkedin', 'twitter', 'youtube', 'tiktok', 'pinterest')
    ),
    platform_account_id VARCHAR(255) NOT NULL,
    platform_account_name VARCHAR(255),
    platform_account_username VARCHAR(255),
    platform_profile_url TEXT,
    platform_profile_image TEXT,
    
    -- OAuth Tokens
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    token_expires_at TIMESTAMP,
    token_scope TEXT,
    
    -- Platform-Specific Data
    metadata JSONB DEFAULT '{}'::JSONB,
    -- Example for Facebook: {
    --   "page_id": "123456",
    --   "page_access_token": "token",
    --   "instagram_business_account_id": "789"
    -- }
    
    -- Settings
    posting_enabled BOOLEAN DEFAULT true,
    auto_schedule_enabled BOOLEAN DEFAULT true,
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_health_check TIMESTAMP,
    health_status VARCHAR(50) DEFAULT 'healthy', -- 'healthy', 'token_expired', 'error'
    health_error TEXT,
    
    -- Timestamps
    connected_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(account_id, platform_type, platform_account_id)
);

-- Indexes
CREATE INDEX idx_platforms_account ON platforms(account_id);
CREATE INDEX idx_platforms_type ON platforms(platform_type);
CREATE INDEX idx_platforms_active ON platforms(account_id, is_active);
CREATE INDEX idx_platforms_expires ON platforms(token_expires_at);

-- Trigger
CREATE TRIGGER platforms_updated_at
BEFORE UPDATE ON platforms
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

---

### 4. Strategy & AI Tables

#### strategies
```sql
CREATE TABLE strategies (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    business_id UUID REFERENCES businesses(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    
    -- Strategy Details
    name VARCHAR(255),
    goal VARCHAR(100), -- 'increase_sales', 'brand_awareness', etc.
    
    -- Platform Mix
    platform_mix JSONB NOT NULL,
    -- Example: {
    --   "instagram": 0.6,
    --   "facebook": 0.3,
    --   "linkedin": 0.1
    -- }
    
    -- Posting Schedule
    posting_frequency JSONB NOT NULL,
    -- Example: {
    --   "instagram": {"per_week": 5, "best_times": ["11:00", "13:00", "17:00"]},
    --   "facebook": {"per_week": 3, "best_times": ["09:00", "13:00", "15:00"]}
    -- }
    
    -- Content Themes
    content_themes TEXT[],
    -- Example: ['product_showcase', 'behind_the_scenes', 'customer_stories']
    
    -- AI Reasoning
    reasoning TEXT,
    confidence_score DECIMAL(3, 2), -- 0.00 to 1.00
    ai_model VARCHAR(100),
    
    -- Performance
    performance_score DECIMAL(5, 2), -- Calculated over time
    total_posts INTEGER DEFAULT 0,
    avg_engagement_rate DECIMAL(5, 2),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    archived_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_strategies_account ON strategies(account_id);
CREATE INDEX idx_strategies_business ON strategies(business_id);
CREATE INDEX idx_strategies_active ON strategies(is_active);

-- Trigger
CREATE TRIGGER strategies_updated_at
BEFORE UPDATE ON strategies
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

#### ai_generations
```sql
CREATE TABLE ai_generations (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    post_id UUID REFERENCES posts(id) ON DELETE SET NULL,
    
    -- Generation Details
    generation_type VARCHAR(50) NOT NULL CHECK (
        generation_type IN ('content', 'strategy', 'image', 'caption', 'hashtags')
    ),
    
    -- AI Model
    provider VARCHAR(50) NOT NULL, -- 'openai', 'anthropic', 'stability'
    model VARCHAR(100) NOT NULL, -- 'gpt-4-turbo', 'claude-sonnet', 'dall-e-3'
    
    -- Input/Output
    prompt TEXT NOT NULL,
    response TEXT,
    
    -- Metrics
    tokens_used INTEGER,
    tokens_prompt INTEGER,
    tokens_completion INTEGER,
    cost DECIMAL(10, 6), -- USD
    duration_ms INTEGER, -- Milliseconds
    
    -- Status
    status VARCHAR(50) DEFAULT 'completed' CHECK (
        status IN ('pending', 'completed', 'failed', 'timeout')
    ),
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_ai_gen_account ON ai_generations(account_id);
CREATE INDEX idx_ai_gen_user ON ai_generations(user_id);
CREATE INDEX idx_ai_gen_type ON ai_generations(generation_type);
CREATE INDEX idx_ai_gen_created ON ai_generations(created_at);
CREATE INDEX idx_ai_gen_cost ON ai_generations(cost);

-- Partitioning by month (for large volume)
-- CREATE TABLE ai_generations_y2025m01 PARTITION OF ai_generations
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

---

### 5. Campaign & Analytics Tables

#### campaigns
```sql
CREATE TABLE campaigns (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES strategies(id),
    created_by UUID NOT NULL REFERENCES users(id),
    
    -- Campaign Info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    objective VARCHAR(100), -- 'lead_generation', 'sales', 'awareness', 'engagement'
    
    -- Platforms
    platforms TEXT[] NOT NULL, -- ['facebook', 'instagram']
    
    -- Budget
    budget_type VARCHAR(50) CHECK (budget_type IN ('daily', 'lifetime')),
    budget_amount DECIMAL(10, 2),
    spend_so_far DECIMAL(10, 2) DEFAULT 0,
    
    -- Schedule
    status VARCHAR(50) DEFAULT 'draft' CHECK (
        status IN ('draft', 'active', 'paused', 'completed', 'failed')
    ),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    
    -- Platform Campaign IDs
    platform_campaign_ids JSONB DEFAULT '{}'::JSONB,
    -- Example: {
    --   "facebook": "fb_campaign_123",
    --   "instagram": "ig_campaign_456"
    -- }
    
    -- Results
    results JSONB DEFAULT '{}'::JSONB,
    -- Example: {
    --   "impressions": 50000,
    --   "clicks": 1250,
    --   "conversions": 35,
    --   "cost_per_click": 0.50,
    --   "cost_per_conversion": 17.86
    -- }
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_campaigns_account ON campaigns(account_id);
CREATE INDEX idx_campaigns_strategy ON campaigns(strategy_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_dates ON campaigns(start_date, end_date);

-- Trigger
CREATE TRIGGER campaigns_updated_at
BEFORE UPDATE ON campaigns
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

---

### 6. Permission & Security Tables

#### permissions
```sql
CREATE TABLE permissions (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Permission Details
    name VARCHAR(100) UNIQUE NOT NULL, -- 'content.create', 'analytics.view'
    resource VARCHAR(100) NOT NULL, -- 'content', 'analytics'
    action VARCHAR(50) NOT NULL, -- 'create', 'read', 'update', 'delete'
    description TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index
CREATE INDEX idx_permissions_name ON permissions(name);
CREATE INDEX idx_permissions_resource ON permissions(resource);
```

#### role_permissions
```sql
CREATE TABLE role_permissions (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    role VARCHAR(50) NOT NULL CHECK (
        role IN ('owner', 'admin', 'manager', 'editor', 'viewer')
    ),
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(role, permission_id)
);

-- Indexes
CREATE INDEX idx_role_perm_role ON role_permissions(role);
CREATE INDEX idx_role_perm_permission ON role_permissions(permission_id);
```

#### user_permissions
```sql
CREATE TABLE user_permissions (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    team_member_id UUID NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    
    -- Grant/Revoke
    is_granted BOOLEAN DEFAULT true, -- true = grant, false = revoke
    granted_by UUID REFERENCES users(id),
    
    -- Timestamps
    granted_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(team_member_id, permission_id)
);

-- Indexes
CREATE INDEX idx_user_perm_member ON user_permissions(team_member_id);
CREATE INDEX idx_user_perm_permission ON user_permissions(permission_id);
```

---

### 7. Audit & Logging Tables

#### audit_logs
```sql
CREATE TABLE audit_logs (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Context
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Action
    action VARCHAR(100) NOT NULL, -- 'content.publish', 'team.invite', 'settings.update'
    resource_type VARCHAR(50), -- 'post', 'team_member', 'platform'
    resource_id UUID,
    
    -- Changes
    old_values JSONB,
    new_values JSONB,
    
    -- Details
    details JSONB DEFAULT '{}'::JSONB,
    
    -- Request Info
    ip_address VARCHAR(50),
    user_agent TEXT,
    request_id VARCHAR(255), -- Correlation ID
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_account ON audit_logs(account_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);

-- Partitioning by month (for large volume)
-- CREATE TABLE audit_logs_y2025m01 PARTITION OF audit_logs
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

#### system_logs
```sql
CREATE TABLE system_logs (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Log Level
    level VARCHAR(20) NOT NULL CHECK (
        level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    ),
    
    -- Context
    service VARCHAR(100), -- 'api', 'worker', 'scheduler'
    module VARCHAR(100), -- 'content_service', 'platform_integration'
    
    -- Message
    message TEXT NOT NULL,
    
    -- Additional Data
    data JSONB DEFAULT '{}'::JSONB,
    
    -- Stack Trace (for errors)
    stack_trace TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_system_logs_level ON system_logs(level);
CREATE INDEX idx_system_logs_service ON system_logs(service);
CREATE INDEX idx_system_logs_created ON system_logs(created_at);
```

---

### 8. Notification & Communication Tables

#### notifications
```sql
CREATE TABLE notifications (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Recipient
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Notification Details
    type VARCHAR(100) NOT NULL, -- 'post_published', 'approval_requested', 'team_invited'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    
    -- Action
    action_url TEXT, -- Link to take action
    action_text VARCHAR(100), -- "View Post", "Approve", etc.
    
    -- Related Resources
    related_resource_type VARCHAR(50), -- 'post', 'team_member'
    related_resource_id UUID,
    
    -- Status
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_notif_user ON notifications(user_id);
CREATE INDEX idx_notif_account ON notifications(account_id);
CREATE INDEX idx_notif_unread ON notifications(user_id, is_read) WHERE is_read = false;
CREATE INDEX idx_notif_created ON notifications(created_at);

-- Auto-delete old notifications (keep 90 days)
-- CREATE OR REPLACE FUNCTION delete_old_notifications()
-- RETURNS void AS $$
-- BEGIN
--     DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '90 days';
-- END;
-- $$ LANGUAGE plpgsql;
```

#### email_logs
```sql
CREATE TABLE email_logs (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Recipient
    to_email VARCHAR(255) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Email Details
    email_type VARCHAR(100) NOT NULL, -- 'welcome', 'verification', 'reset_password'
    subject VARCHAR(500) NOT NULL,
    
    -- Provider
    provider VARCHAR(50) DEFAULT 'sendgrid', -- 'sendgrid', 'resend'
    provider_message_id VARCHAR(255),
    
    -- Status
    status VARCHAR(50) DEFAULT 'sent' CHECK (
        status IN ('sent', 'delivered', 'bounced', 'failed', 'opened', 'clicked')
    ),
    error_message TEXT,
    
    -- Events
    sent_at TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    bounced_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_email_to ON email_logs(to_email);
CREATE INDEX idx_email_user ON email_logs(user_id);
CREATE INDEX idx_email_type ON email_logs(email_type);
CREATE INDEX idx_email_status ON email_logs(status);
CREATE INDEX idx_email_sent ON email_logs(sent_at);
```

---

### 9. Webhook & Integration Tables

#### webhooks
```sql
CREATE TABLE webhooks (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source
    source VARCHAR(50) NOT NULL, -- 'stripe', 'meta', 'linkedin'
    event_type VARCHAR(100) NOT NULL, -- 'payment_succeeded', 'post_published'
    
    -- Payload
    payload JSONB NOT NULL,
    headers JSONB, -- Request headers
    
    -- Processing
    processed BOOLEAN DEFAULT false,
    processed_at TIMESTAMP,
    processing_error TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- Timestamps
    received_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_webhooks_source ON webhooks(source);
CREATE INDEX idx_webhooks_type ON webhooks(event_type);
CREATE INDEX idx_webhooks_processed ON webhooks(processed);
CREATE INDEX idx_webhooks_created ON webhooks(created_at);
```

---

## 🔍 Common Query Patterns

### 1. Get User's Accounts with Role
```sql
SELECT 
    a.*,
    tm.role,
    tm.is_active as member_is_active
FROM accounts a
INNER JOIN team_members tm ON a.id = tm.account_id
WHERE tm.user_id = $user_id
    AND tm.is_active = true
    AND a.deleted_at IS NULL
ORDER BY a.created_at DESC;
```

### 2. Get Account's Team Members with User Info
```sql
SELECT 
    tm.*,
    u.email,
    u.full_name,
    u.avatar_url
FROM team_members tm
INNER JOIN users u ON tm.user_id = u.id
WHERE tm.account_id = $account_id
    AND tm.is_active = true
ORDER BY 
    CASE tm.role
        WHEN 'owner' THEN 1
        WHEN 'admin' THEN 2
        WHEN 'manager' THEN 3
        WHEN 'editor' THEN 4
        WHEN 'viewer' THEN 5
    END,
    tm.created_at ASC;
```

### 3. Get Scheduled Posts Due for Publishing
```sql
SELECT *
FROM posts
WHERE status = 'scheduled'
    AND scheduled_at <= NOW()
    AND deleted_at IS NULL
ORDER BY scheduled_at ASC
LIMIT 100;
```

### 4. Get Post Performance Across Platforms
```sql
SELECT 
    p.id,
    p.content,
    p.published_at,
    COALESCE(SUM(pp.impressions), 0) as total_impressions,
    COALESCE(SUM(pp.reach), 0) as total_reach,
    COALESCE(SUM(pp.likes + pp.comments + pp.shares), 0) as total_engagement,
    COALESCE(AVG(pp.engagement_rate), 0) as avg_engagement_rate
FROM posts p
LEFT JOIN post_performance pp ON p.id = pp.post_id
WHERE p.account_id = $account_id
    AND p.status = 'published'
    AND p.published_at >= NOW() - INTERVAL '30 days'
GROUP BY p.id
ORDER BY total_engagement DESC
LIMIT 10;
```

### 5. Get Account Usage Statistics
```sql
SELECT 
    COUNT(DISTINCT p.id) as posts_this_month,
    SUM(ag.cost) as ai_cost_this_month,
    SUM(ag.tokens_used) as tokens_used_this_month,
    COUNT(DISTINCT CASE WHEN p.status = 'published' THEN p.id END) as published_count
FROM accounts a
LEFT JOIN posts p ON a.id = p.account_id 
    AND p.created_at >= date_trunc('month', NOW())
LEFT JOIN ai_generations ag ON a.id = ag.account_id
    AND ag.created_at >= date_trunc('month', NOW())
WHERE a.id = $account_id;
```

### 6. Check if User Has Permission
```sql
-- Via role
SELECT EXISTS (
    SELECT 1
    FROM team_members tm
    INNER JOIN role_permissions rp ON tm.role = rp.role
    INNER JOIN permissions p ON rp.permission_id = p.id
    WHERE tm.user_id = $user_id
        AND tm.account_id = $account_id
        AND tm.is_active = true
        AND p.name = $permission_name
) as has_permission;

-- With custom permission overrides
WITH role_perms AS (
    SELECT p.name
    FROM team_members tm
    INNER JOIN role_permissions rp ON tm.role = rp.role
    INNER JOIN permissions p ON rp.permission_id = p.id
    WHERE tm.user_id = $user_id
        AND tm.account_id = $account_id
        AND tm.is_active = true
),
custom_perms AS (
    SELECT p.name, up.is_granted
    FROM team_members tm
    INNER JOIN user_permissions up ON tm.id = up.team_member_id
    INNER JOIN permissions p ON up.permission_id = p.id
    WHERE tm.user_id = $user_id
        AND tm.account_id = $account_id
)
SELECT EXISTS (
    SELECT 1 FROM role_perms WHERE name = $permission_name
    UNION
    SELECT 1 FROM custom_perms WHERE name = $permission_name AND is_granted = true
    EXCEPT
    SELECT 1 FROM custom_perms WHERE name = $permission_name AND is_granted = false
) as has_permission;
```

---

## 🚀 Database Setup Script

```sql
-- Complete database setup script
-- Run this to create all tables in correct order

BEGIN;

-- 1. Core tables (no dependencies)
-- (users, accounts created above)

-- 2. Tables with foreign keys
-- (team_members, platforms, businesses, strategies, permissions, etc.)

-- 3. Seed data
-- Insert default permissions
-- Insert role-permission mappings

-- 4. Create indexes
-- (Already included in table definitions)

-- 5. Create triggers
-- (Already included in table definitions)

COMMIT;
```

---

## ✅ Database Implementation Checklist

### Setup
- [ ] Install PostgreSQL 15+
- [ ] Configure connection pooling
- [ ] Set up backup schedule
- [ ] Enable WAL archiving
- [ ] Configure monitoring

### Schema
- [ ] Create all tables in order
- [ ] Add all indexes
- [ ] Create all triggers
- [ ] Seed permissions
- [ ] Map roles to permissions

### Performance
- [ ] Analyze query plans
- [ ] Add missing indexes
- [ ] Configure vacuuming
- [ ] Set up connection pooling
- [ ] Enable query caching

### Security
- [ ] Implement row-level security (RLS) if needed
- [ ] Encrypt sensitive columns
- [ ] Secure connection strings
- [ ] Limit user permissions
- [ ] Enable audit logging

### Maintenance
- [ ] Schedule regular VACUUM
- [ ] Monitor table bloat
- [ ] Archive old audit logs
- [ ] Back up daily
- [ ] Test restore procedures

---

**Database Status:** Implementation Ready  
**Next Steps:** Run setup script → Test queries → Optimize performance  
**Review:** Before production deployment
