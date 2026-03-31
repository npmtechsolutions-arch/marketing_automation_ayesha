# Technical Stack Document
## AI Marketing Automation Platform

---

## 📋 Document Information

- **Product Name:** AI Marketing Decision Engine
- **Tech Stack Version:** 1.0
- **Last Updated:** 2025-02-16
- **Engineering Lead:** [Name]
- **Status:** Approved for Development

---

## 🎯 Technical Philosophy

### Core Principles

**1. Speed & Reliability**
- Fast API responses (< 200ms for most endpoints)
- 99.9% uptime target
- Graceful degradation when services fail

**2. Scalability from Day One**
- Horizontal scaling capability
- Async processing for heavy tasks
- Efficient database queries

**3. Developer Experience**
- Clear code structure
- Comprehensive documentation
- Easy local development setup
- Type safety everywhere

**4. Cost Efficiency**
- Optimize AI API costs
- Serverless where appropriate
- Efficient resource usage

---

## 🏗 Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Client Layer                      │
│  ┌──────────────┐         ┌──────────────┐        │
│  │ Web App      │         │ Mobile App   │        │
│  │ (React)      │         │ (Future)     │        │
│  └──────────────┘         └──────────────┘        │
└─────────────────────────────────────────────────────┘
                          │
                          │ HTTPS/WSS
                          ▼
┌─────────────────────────────────────────────────────┐
│                   API Gateway                       │
│              (FastAPI + Uvicorn)                    │
└─────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Auth        │  │  Core API    │  │  Worker      │
│  Service     │  │  Endpoints   │  │  Queue       │
│              │  │              │  │  (Celery)    │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ PostgreSQL   │  │   Redis      │  │  S3/R2       │
│ (Supabase)   │  │   Cache      │  │  Storage     │
└──────────────┘  └──────────────┘  └──────────────┘
                          │
                          │ External APIs
                          ▼
┌─────────────────────────────────────────────────────┐
│  OpenAI │ Meta │ LinkedIn │ Stripe │ SendGrid     │
└─────────────────────────────────────────────────────┘
```

---

## 💻 Technology Stack

### Backend

#### Primary Framework: FastAPI
```
Version: 0.109+
Language: Python 3.11+

Why FastAPI:
✅ High performance (Starlette + Pydantic)
✅ Async/await native support
✅ Automatic API documentation (Swagger)
✅ Type hints & validation built-in
✅ WebSocket support
✅ Excellent for AI/ML integration

Dependencies:
- fastapi==0.109.0
- uvicorn[standard]==0.27.0 (ASGI server)
- pydantic==2.5.0 (data validation)
- python-multipart==0.0.6 (file uploads)
```

#### Database: PostgreSQL
```
Version: 15+
Hosting: Supabase (managed PostgreSQL)

Why PostgreSQL:
✅ ACID compliance
✅ JSON support (JSONB for flexible data)
✅ Full-text search
✅ Excellent performance
✅ Rich ecosystem

ORM: SQLAlchemy 2.0+
- async support
- type-safe queries
- migration management via Alembic

Supabase Features Used:
- Auth (built-in)
- Realtime subscriptions
- Storage (for media)
- Row-level security (RLS)
- Automatic backups
```

#### Background Jobs: Celery
```
Version: 5.3+
Message Broker: Redis

Why Celery:
✅ Reliable task queue
✅ Scheduled tasks (posting, analytics)
✅ Retry mechanisms
✅ Rate limiting
✅ Task chaining

Use Cases:
- Social media posting
- AI content generation (long-running)
- Analytics aggregation
- Email sending
- Platform data syncing
```

#### Cache: Redis
```
Version: 7.2+
Hosting: Upstash (serverless) or Railway

Why Redis:
✅ Fast in-memory cache
✅ Session storage
✅ Rate limiting
✅ Celery message broker
✅ WebSocket pub/sub

Use Cases:
- API response caching
- User session management
- Rate limit tracking
- Real-time features
- Job queue
```

### Frontend

#### Framework: React
```
Version: 18.2+
Build Tool: Vite
Language: TypeScript 5.3+

Why React:
✅ Rich ecosystem
✅ Component reusability
✅ Virtual DOM performance
✅ Large community
✅ Easy to find developers

Project Structure:
/src
├── components/     (reusable UI components)
├── pages/          (route pages)
├── hooks/          (custom React hooks)
├── services/       (API calls)
├── store/          (state management)
├── types/          (TypeScript types)
└── utils/          (helper functions)
```

#### State Management: Zustand
```
Version: 4.4+

Why Zustand (not Redux):
✅ Simpler API
✅ Less boilerplate
✅ Better TypeScript support
✅ Smaller bundle size
✅ Built-in persistence

Stores:
- authStore (user, tokens)
- contentStore (posts, drafts)
- platformStore (connected accounts)
- uiStore (modals, toasts)
```

#### Styling: Tailwind CSS
```
Version: 3.4+

Why Tailwind:
✅ Utility-first approach
✅ Design consistency
✅ No CSS file management
✅ Excellent documentation
✅ Easy to customize

Configuration:
- Custom color palette (from DesignDoc)
- Custom spacing scale
- Component classes using @apply
- Dark mode support (future)
```

#### UI Components: shadcn/ui
```
Based on Radix UI primitives

Why shadcn/ui:
✅ Copy-paste components (not npm package)
✅ Full customization
✅ Accessible by default
✅ Works with Tailwind
✅ TypeScript support

Components Used:
- Dialog, DropdownMenu, Select
- Calendar, DatePicker
- Toast notifications
- Command palette
```

#### API Client: Axios
```
Version: 1.6+

Why Axios (not fetch):
✅ Interceptors (auth tokens)
✅ Request/response transformation
✅ Automatic JSON handling
✅ Better error handling
✅ Cancel requests

Configuration:
- Base URL from env
- Auth token injection
- Error interceptor
- Retry logic
```

### Infrastructure

#### Hosting: Railway (Primary)
```
Why Railway:
✅ Simple deployment (git push)
✅ PostgreSQL + Redis included
✅ Environment variables
✅ Automatic HTTPS
✅ Fair pricing ($5-20/month start)
✅ Easy scaling

Alternative: Vercel (frontend) + Railway (backend)

Services:
- FastAPI app
- Celery worker
- Redis
- PostgreSQL (or use Supabase)
```

#### File Storage: Cloudflare R2
```
Why R2 (not S3):
✅ S3-compatible API
✅ No egress fees
✅ Cheaper storage
✅ Fast CDN included
✅ Simple setup

Use Cases:
- Generated images
- User uploads
- Media assets
- Export files

Alternative: Supabase Storage (integrated)
```

#### DNS & CDN: Cloudflare
```
Free Tier Features:
- DNS management
- SSL certificates
- DDoS protection
- Basic CDN
- Analytics

Configuration:
- Proxied through Cloudflare
- Caching rules for static assets
- Rate limiting on API
```

### External Services

#### AI/ML APIs
```
Primary: OpenAI API
- GPT-4-turbo for strategy generation
- GPT-3.5-turbo for simple content
- DALL-E 3 for image generation

Secondary: Anthropic Claude API
- Complex reasoning tasks
- Long-form content
- Backup for OpenAI

Image Generation: Stable Diffusion (via Replicate)
- Cost-effective alternative
- More style control
```

#### Authentication: Supabase Auth
```
Features:
- Email/password
- OAuth (Google, Facebook, etc.)
- Magic links
- JWT tokens
- Row-level security

Alternative: Auth0, Clerk
```

#### Payments: Stripe
```
Features Used:
- Subscriptions
- Customer portal
- Webhooks
- Payment methods
- Invoices

Alternative: Paddle (merchant of record)
```

#### Email: Resend or SendGrid
```
Resend (Preferred):
- Modern API
- Better DX
- React email templates
- Cheaper

SendGrid (Alternative):
- More features
- Better deliverability tracking
```

---

## 📁 Project Structure

### Backend Structure
```
/backend
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app initialization
│   ├── config.py               # Settings (from env)
│   ├── database.py             # DB connection
│   ├── dependencies.py         # DI (auth, db session)
│   │
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── platform.py
│   │   ├── post.py
│   │   ├── campaign.py
│   │   └── analytics.py
│   │
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── post.py
│   │   └── analytics.py
│   │
│   ├── api/                    # API routes
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py         # Login, signup
│   │   │   ├── platforms.py    # OAuth, connections
│   │   │   ├── content.py      # Generate, manage posts
│   │   │   ├── campaigns.py    # Campaign management
│   │   │   ├── analytics.py    # Performance data
│   │   │   └── webhooks.py     # Stripe, platforms
│   │
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── ai_service.py       # OpenAI integration
│   │   ├── content_service.py  # Content generation
│   │   ├── platform_service.py # Social media APIs
│   │   ├── analytics_service.py
│   │   └── strategy_service.py # AI strategy engine
│   │
│   ├── integrations/           # External API clients
│   │   ├── __init__.py
│   │   ├── meta.py             # Facebook/Instagram
│   │   ├── linkedin.py
│   │   ├── twitter.py
│   │   ├── openai_client.py
│   │   └── stripe_client.py
│   │
│   ├── tasks/                  # Celery tasks
│   │   ├── __init__.py
│   │   ├── content_tasks.py    # Generate content
│   │   ├── posting_tasks.py    # Publish posts
│   │   ├── analytics_tasks.py  # Fetch platform data
│   │   └── email_tasks.py      # Send notifications
│   │
│   ├── utils/                  # Helper functions
│   │   ├── __init__.py
│   │   ├── security.py         # Password hashing
│   │   ├── cache.py            # Redis utilities
│   │   ├── logger.py           # Logging setup
│   │   └── validators.py       # Custom validators
│   │
│   └── tests/                  # Unit & integration tests
│       ├── __init__.py
│       ├── test_auth.py
│       ├── test_content.py
│       └── test_platforms.py
│
├── alembic/                    # DB migrations
│   ├── versions/
│   └── env.py
│
├── .env.example                # Environment variables template
├── .gitignore
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container image
├── docker-compose.yml          # Local development
└── README.md
```

### Frontend Structure
```
/frontend
├── public/
│   ├── favicon.ico
│   └── images/
│
├── src/
│   ├── assets/                 # Static files
│   │   ├── icons/
│   │   └── images/
│   │
│   ├── components/             # Reusable components
│   │   ├── ui/                 # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── dialog.tsx
│   │   │   └── ...
│   │   │
│   │   ├── layout/
│   │   │   ├── Navbar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   │
│   │   ├── content/
│   │   │   ├── ContentCard.tsx
│   │   │   ├── ContentEditor.tsx
│   │   │   └── PlatformPreview.tsx
│   │   │
│   │   └── analytics/
│   │       ├── StatsCard.tsx
│   │       └── PerformanceChart.tsx
│   │
│   ├── pages/                  # Route pages
│   │   ├── Dashboard.tsx
│   │   ├── ContentCalendar.tsx
│   │   ├── Analytics.tsx
│   │   ├── Settings.tsx
│   │   └── auth/
│   │       ├── Login.tsx
│   │       └── Signup.tsx
│   │
│   ├── hooks/                  # Custom hooks
│   │   ├── useAuth.ts
│   │   ├── useContent.ts
│   │   ├── usePlatforms.ts
│   │   └── useAnalytics.ts
│   │
│   ├── services/               # API calls
│   │   ├── api.ts              # Axios instance
│   │   ├── authService.ts
│   │   ├── contentService.ts
│   │   ├── platformService.ts
│   │   └── analyticsService.ts
│   │
│   ├── store/                  # Zustand stores
│   │   ├── authStore.ts
│   │   ├── contentStore.ts
│   │   ├── platformStore.ts
│   │   └── uiStore.ts
│   │
│   ├── types/                  # TypeScript types
│   │   ├── auth.ts
│   │   ├── content.ts
│   │   ├── platform.ts
│   │   └── analytics.ts
│   │
│   ├── utils/                  # Helper functions
│   │   ├── dateUtils.ts
│   │   ├── formatters.ts
│   │   └── validators.ts
│   │
│   ├── App.tsx                 # Root component
│   ├── main.tsx                # Entry point
│   └── router.tsx              # React Router setup
│
├── .env.example
├── .gitignore
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```

---

## 🗄 Database Schema

### Core Tables

#### users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),  -- null for OAuth users
    full_name VARCHAR(255),
    avatar_url TEXT,
    onboarding_completed BOOLEAN DEFAULT false,
    subscription_tier VARCHAR(50) DEFAULT 'free',
    subscription_status VARCHAR(50) DEFAULT 'active',
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stripe ON users(stripe_customer_id);
```

#### businesses
```sql
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    description TEXT,
    target_audience JSONB,  -- {"age": "25-45", "location": "US", ...}
    brand_voice JSONB,      -- {"tone": "professional", "style": "casual"}
    goals JSONB,            -- ["increase_sales", "brand_awareness"]
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_businesses_user ON businesses(user_id);
```

#### platforms
```sql
CREATE TABLE platforms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    platform_type VARCHAR(50) NOT NULL,  -- 'facebook', 'instagram', 'linkedin'
    platform_account_id VARCHAR(255),
    platform_account_name VARCHAR(255),
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB,  -- platform-specific data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_platforms_user ON platforms(user_id);
CREATE INDEX idx_platforms_type ON platforms(platform_type);
```

#### posts
```sql
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    
    -- Content
    content TEXT NOT NULL,
    media_urls JSONB,  -- ["https://...", "https://..."]
    hashtags TEXT[],
    
    -- Platform Distribution
    platforms JSONB,  -- [{"type": "instagram", "platform_id": "uuid", ...}]
    
    -- Status
    status VARCHAR(50) DEFAULT 'draft',  -- draft, scheduled, published, failed
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,
    
    -- AI Metadata
    generated_by_ai BOOLEAN DEFAULT false,
    ai_prompt TEXT,
    strategy_id UUID,  -- link to strategy that generated this
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_scheduled ON posts(scheduled_at);
```

#### post_performance
```sql
CREATE TABLE post_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    platform_type VARCHAR(50) NOT NULL,
    platform_post_id VARCHAR(255),  -- ID from the platform
    
    -- Metrics
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5,2),
    
    -- Metadata
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_performance_post ON post_performance(post_id);
CREATE INDEX idx_performance_platform ON post_performance(platform_type);
```

#### strategies
```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    business_id UUID REFERENCES businesses(id) ON DELETE CASCADE,
    
    -- Strategy Details
    name VARCHAR(255),
    goal VARCHAR(100),  -- 'increase_sales', 'brand_awareness', etc.
    platform_mix JSONB,  -- {"instagram": 0.6, "facebook": 0.3, "linkedin": 0.1}
    posting_frequency JSONB,  -- {"instagram": 5, "facebook": 3, ...}
    content_themes TEXT[],
    
    -- AI Reasoning
    reasoning TEXT,  -- Why this strategy was recommended
    confidence_score DECIMAL(3,2),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    performance_score DECIMAL(5,2),  -- Calculated over time
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_strategies_user ON strategies(user_id);
CREATE INDEX idx_strategies_active ON strategies(is_active);
```

#### campaigns
```sql
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES strategies(id),
    
    name VARCHAR(255) NOT NULL,
    objective VARCHAR(100),  -- 'lead_generation', 'sales', 'awareness'
    platforms TEXT[],  -- ['facebook', 'instagram']
    
    -- Budget
    budget_amount DECIMAL(10,2),
    budget_period VARCHAR(50),  -- 'daily', 'lifetime'
    spend_so_far DECIMAL(10,2) DEFAULT 0,
    
    -- Status
    status VARCHAR(50) DEFAULT 'draft',  -- draft, active, paused, completed
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    
    -- Performance
    results JSONB,  -- platform-specific results
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_campaigns_user ON campaigns(user_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
```

### Supporting Tables

#### ai_generations
```sql
-- Log all AI API calls for cost tracking and debugging
CREATE TABLE ai_generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    generation_type VARCHAR(50),  -- 'content', 'strategy', 'image'
    model VARCHAR(100),  -- 'gpt-4-turbo', 'dall-e-3'
    prompt TEXT,
    response TEXT,
    tokens_used INTEGER,
    cost DECIMAL(10,6),
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_generations_user ON ai_generations(user_id);
CREATE INDEX idx_generations_date ON ai_generations(created_at);
```

#### webhooks
```sql
-- Track webhook events from Stripe, platforms
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50),  -- 'stripe', 'meta', 'linkedin'
    event_type VARCHAR(100),
    payload JSONB,
    processed BOOLEAN DEFAULT false,
    processing_error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_webhooks_source ON webhooks(source);
CREATE INDEX idx_webhooks_processed ON webhooks(processed);
```

---

## 🔐 Security

### Authentication Flow

```
1. User Login/Signup
   ↓
2. Supabase Auth validates credentials
   ↓
3. Returns JWT access token + refresh token
   ↓
4. Frontend stores tokens (httpOnly cookie or localStorage)
   ↓
5. Every API request includes: Authorization: Bearer <token>
   ↓
6. Backend validates JWT (via Supabase or local validation)
   ↓
7. Extracts user_id from token
   ↓
8. Proceeds with request
```

### Security Best Practices

**API Keys & Secrets**
- Store in environment variables (never in code)
- Rotate regularly (every 90 days)
- Use separate keys for dev/staging/prod
- Encrypt at rest in database

**Password Security**
- Bcrypt hashing (cost factor: 12)
- Minimum 8 characters
- Password complexity requirements
- Rate limit login attempts

**API Security**
- Rate limiting (100 requests/min per user)
- CORS configuration (allowed origins only)
- Input validation (Pydantic schemas)
- SQL injection prevention (SQLAlchemy parameterized queries)
- XSS prevention (sanitize user inputs)

**HTTPS Everywhere**
- Enforce HTTPS in production
- HSTS headers
- Secure cookies (httpOnly, secure, sameSite)

**Data Privacy**
- GDPR compliance
- Data retention policies
- User data export
- Right to be forgotten (delete account)

---

## 🚀 Deployment

### Development Environment

```bash
# Backend (FastAPI)
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (React)
cd frontend
npm install
npm run dev  # Vite dev server on port 5173

# Celery Worker
celery -A app.tasks worker --loglevel=info

# Celery Beat (scheduled tasks)
celery -A app.tasks beat --loglevel=info
```

### Docker Compose (Local)

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: marketing_ai
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    env_file:
      - ./backend/.env

  celery_worker:
    build: ./backend
    command: celery -A app.tasks worker --loglevel=info
    volumes:
      - ./backend:/app
    depends_on:
      - postgres
      - redis
    env_file:
      - ./backend/.env

  celery_beat:
    build: ./backend
    command: celery -A app.tasks beat --loglevel=info
    volumes:
      - ./backend:/app
    depends_on:
      - postgres
      - redis
    env_file:
      - ./backend/.env

  frontend:
    build: ./frontend
    command: npm run dev -- --host
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"
    depends_on:
      - backend

volumes:
  postgres_data:
```

### Production Deployment (Railway)

**railway.json**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Deployment Steps:**

1. **Backend Deployment:**
```bash
# Connect Railway CLI
railway login
railway link

# Add services
railway add  # Select PostgreSQL
railway add  # Select Redis

# Deploy backend
cd backend
railway up

# Set environment variables in Railway dashboard
# DATABASE_URL, REDIS_URL, etc.
```

2. **Frontend Deployment (Vercel):**
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd frontend
vercel --prod

# Set environment variables:
# VITE_API_URL=https://your-backend.railway.app
```

3. **Celery Worker (Railway):**
```bash
# Create new service for Celery worker
# Use same codebase, different start command
railway add

# Start command: celery -A app.tasks worker --loglevel=info
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        run: |
          npm i -g @railway/cli
          railway link ${{ secrets.RAILWAY_PROJECT_ID }}
          railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        run: |
          cd frontend
          npm ci
          npm run build
          npx vercel --prod --token=${{ secrets.VERCEL_TOKEN }}
```

---

## 📊 Monitoring & Logging

### Application Monitoring

**Sentry (Error Tracking)**
```python
# Backend
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
)
```

**Railway Metrics (Built-in)**
- CPU usage
- Memory usage
- Request count
- Response times
- Error rates

### Logging Strategy

```python
# app/utils/logger.py
import logging
import sys

def setup_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

# Usage
logger = setup_logger(__name__)
logger.info("User {user_id} generated content")
logger.error("Failed to post to Instagram", exc_info=True)
```

**Log Levels:**
- DEBUG: Development only
- INFO: Important events (user actions)
- WARNING: Recoverable errors
- ERROR: Failures that need attention
- CRITICAL: System failures

### Analytics & Metrics

**Custom Metrics to Track:**
- User signups per day
- Posts generated per user
- Posts published successfully
- Platform connection success rate
- AI API costs per user
- Page load times
- API response times

**Tools:**
- PostHog (product analytics)
- Plausible (website analytics)
- Railway metrics (infrastructure)

---

## 🧪 Testing Strategy

### Backend Testing

```python
# tests/test_content.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_generate_content():
    response = client.post(
        "/api/v1/content/generate",
        json={
            "prompt": "Post about new product launch",
            "platforms": ["instagram", "facebook"]
        },
        headers={"Authorization": f"Bearer {test_token}"}
    )
    assert response.status_code == 200
    assert "content" in response.json()
    assert len(response.json()["platforms"]) == 2

def test_unauthorized_access():
    response = client.get("/api/v1/content")
    assert response.status_code == 401
```

**Test Coverage Target:** 80%+

**Testing Pyramid:**
- Unit tests: 70% (services, utils)
- Integration tests: 20% (API endpoints)
- E2E tests: 10% (critical flows)

### Frontend Testing

```typescript
// tests/ContentCard.test.tsx
import { render, screen } from '@testing-library/react'
import { ContentCard } from '@/components/content/ContentCard'

describe('ContentCard', () => {
  it('renders post content', () => {
    render(<ContentCard post={mockPost} />)
    expect(screen.getByText(mockPost.content)).toBeInTheDocument()
  })

  it('shows edit button for drafts', () => {
    render(<ContentCard post={{...mockPost, status: 'draft'}} />)
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
  })
})
```

**Testing Tools:**
- Vitest (unit tests)
- React Testing Library (component tests)
- Playwright (E2E tests)

---

## 🔧 Development Tools

### Code Quality

```bash
# Backend
black .              # Code formatting
isort .              # Import sorting
flake8 .             # Linting
mypy .               # Type checking
pytest --cov        # Test coverage

# Frontend
npm run lint        # ESLint
npm run format      # Prettier
npm run type-check  # TypeScript
npm run test        # Vitest
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
  
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    hooks:
      - id: isort
```

---

## 💰 Cost Estimates

### Monthly Infrastructure Costs (1000 active users)

| Service | Tier | Cost |
|---------|------|------|
| Railway (Backend + Celery) | Pro | $20 |
| Railway PostgreSQL | Shared | $5 |
| Upstash Redis | Free/Paid | $0-10 |
| Vercel (Frontend) | Pro | $20 |
| Cloudflare R2 (Storage) | 10GB | $2 |
| Supabase | Pro | $25 |
| OpenAI API | Usage-based | $500-1500 |
| Anthropic API | Usage-based | $200-500 |
| Stripe | % of revenue | 2.9% + $0.30 |
| SendGrid | Essentials | $20 |
| Sentry | Team | $26 |
| **Total** | | **$820-2130/month** |

**Cost Optimization Strategies:**
- Cache AI responses aggressively
- Use cheaper models for simple tasks
- Batch API requests where possible
- Implement usage limits per plan
- Consider self-hosted models at scale

---

## 📈 Scalability Plan

### Vertical Scaling (Phase 1: 0-10K users)
- Increase Railway instance size
- Optimize database queries
- Add Redis caching
- CDN for static assets

### Horizontal Scaling (Phase 2: 10K-100K users)
- Multiple backend instances (load balanced)
- Read replicas for PostgreSQL
- Separate Celery workers by task type
- Implement database sharding if needed

### Advanced Scaling (Phase 3: 100K+ users)
- Microservices architecture
  - Auth service
  - Content service
  - Platform integration service
  - Analytics service
- Message queue (RabbitMQ or Kafka)
- Elasticsearch for search
- Separate AI inference service
- CDN for AI-generated images

---

## 🔒 Backup & Disaster Recovery

### Database Backups
- **Frequency:** Daily (automated via Supabase/Railway)
- **Retention:** 30 days
- **Storage:** S3 or Railway backups
- **Testing:** Monthly restore test

### Application Backups
- Code: Git (multiple remotes)
- Config: Environment variables documented
- Secrets: Backup in secure vault

### Disaster Recovery Plan
1. **Detection:** Monitoring alerts
2. **Communication:** Status page + email
3. **Rollback:** Previous working deployment
4. **Database Restore:** From latest backup
5. **Post-mortem:** Document incident

**RTO (Recovery Time Objective):** 1 hour  
**RPO (Recovery Point Objective):** 24 hours

---

## 📚 Documentation

### API Documentation
- **Swagger UI:** Auto-generated at `/docs`
- **ReDoc:** Alternative at `/redoc`
- **Manual Docs:** In `/docs` folder
- **Postman Collection:** For testing

### Developer Onboarding
1. Clone repository
2. Copy `.env.example` to `.env`
3. Fill in required environment variables
4. Run `docker-compose up`
5. Access app at `http://localhost:5173`

### Code Documentation
- Docstrings for all functions
- Type hints everywhere
- README in each major folder
- Architecture decision records (ADRs)

---

## ✅ Technical Checklist (MVP)

### Backend
- [x] FastAPI app structure
- [ ] PostgreSQL database setup
- [ ] Supabase auth integration
- [ ] User CRUD operations
- [ ] Platform OAuth flows (Meta, LinkedIn)
- [ ] Content generation endpoint
- [ ] Post scheduling system
- [ ] Celery task queue
- [ ] Redis caching
- [ ] API documentation
- [ ] Unit tests (80% coverage)
- [ ] Error handling & logging

### Frontend
- [x] React + Vite setup
- [ ] Tailwind CSS configuration
- [ ] shadcn/ui components
- [ ] Authentication flows
- [ ] Dashboard page
- [ ] Content calendar
- [ ] Content editor
- [ ] Platform connection UI
- [ ] Analytics dashboard
- [ ] Responsive design
- [ ] Error boundaries
- [ ] Loading states

### Infrastructure
- [ ] Railway deployment
- [ ] Vercel deployment
- [ ] Environment variables
- [ ] CI/CD pipeline
- [ ] Monitoring (Sentry)
- [ ] Logging setup
- [ ] Backups configured
- [ ] Domain & SSL

### External Integrations
- [ ] OpenAI API integration
- [ ] Meta Graph API
- [ ] LinkedIn API
- [ ] Stripe payments
- [ ] SendGrid emails
- [ ] Cloudflare R2 storage

---

## 🚧 Technical Debt & Future Improvements

### Phase 1 (Accept for MVP)
- Basic error handling (improve later)
- Simple caching strategy
- Monolithic architecture
- Manual deployment steps

### Phase 2 (Post-MVP)
- Advanced error recovery
- Comprehensive caching
- Automated deployments
- Performance optimization
- Security audit
- Load testing

### Phase 3 (Scale)
- Microservices architecture
- Advanced monitoring
- Custom AI models
- Real-time features (WebSockets)
- Mobile app (React Native)

---

**Tech Stack Status:** Ready for Development  
**Next Review:** Monthly  
**Questions:** [Engineering Slack channel]
