# API Specification Document
## Complete REST API Endpoints with CRUD Operations

---

## 📋 Document Information

- **Product:** AI Marketing Automation Platform
- **API Version:** v1
- **Base URL:** `https://api.yourapp.com/api/v1`
- **Authentication:** Bearer Token (JWT)
- **Last Updated:** 2025-02-16
- **Status:** Implementation Ready

---

## 🔐 Authentication

### Authentication Flow

```
1. User Login → POST /auth/login
2. Receive JWT access token + refresh token
3. Include token in all requests:
   Header: Authorization: Bearer <access_token>
4. Token expires after 24 hours
5. Refresh token: POST /auth/refresh
```

### Auth Endpoints

#### POST /auth/register
Register new user account

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}
```

**Response:** `201 Created`
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "created_at": "2025-02-16T10:00:00Z"
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

#### POST /auth/login
Login existing user

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:** `200 OK` (same as register)

#### POST /auth/logout
Logout user (invalidate token)

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:** `204 No Content`

#### POST /auth/refresh
Refresh access token

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

#### POST /auth/forgot-password
Request password reset

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset email sent"
}
```

#### POST /auth/reset-password
Reset password with token

**Request:**
```json
{
  "token": "reset_token_from_email",
  "new_password": "NewSecurePass123!"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password reset successful"
}
```

---

## 👤 User Endpoints

#### GET /users/me
Get current user profile

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "avatar_url": "https://...",
  "phone": "+1234567890",
  "timezone": "America/New_York",
  "is_super_admin": false,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-02-16T10:00:00Z"
}
```

#### PUT /users/me
Update current user profile

**Request:**
```json
{
  "full_name": "John Smith",
  "phone": "+1234567890",
  "timezone": "America/Los_Angeles",
  "avatar_url": "https://..."
}
```

**Response:** `200 OK` (returns updated user)

#### POST /users/me/change-password
Change password

**Request:**
```json
{
  "current_password": "OldPass123!",
  "new_password": "NewPass123!"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password changed successfully"
}
```

#### DELETE /users/me
Delete user account

**Request:**
```json
{
  "password": "ConfirmPassword123!"
}
```

**Response:** `204 No Content`

---

## 🏢 Account Endpoints (CRUD)

#### GET /accounts
List user's accounts

**Query Parameters:**
- `page` (integer, default: 1)
- `limit` (integer, default: 10, max: 100)

**Response:** `200 OK`
```json
{
  "accounts": [
    {
      "id": "uuid",
      "name": "My Business",
      "slug": "my-business",
      "subscription_tier": "growth",
      "subscription_status": "active",
      "role": "owner",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 1,
    "pages": 1
  }
}
```

#### POST /accounts
Create new account

**Request:**
```json
{
  "name": "My Business",
  "website": "https://mybusiness.com"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "My Business",
  "slug": "my-business",
  "owner_id": "user_uuid",
  "subscription_tier": "free",
  "subscription_status": "active",
  "created_at": "2025-02-16T10:00:00Z"
}
```

#### GET /accounts/:id
Get account details

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "name": "My Business",
  "slug": "my-business",
  "website": "https://mybusiness.com",
  "owner_id": "user_uuid",
  "subscription_tier": "growth",
  "subscription_status": "active",
  "trial_ends_at": null,
  "monthly_post_limit": 100,
  "monthly_posts_used": 45,
  "team_member_limit": 5,
  "settings": {},
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-02-16T10:00:00Z"
}
```

#### PUT /accounts/:id
Update account

**Request:**
```json
{
  "name": "Updated Business Name",
  "website": "https://newwebsite.com",
  "settings": {
    "notifications_enabled": true
  }
}
```

**Response:** `200 OK` (returns updated account)

#### DELETE /accounts/:id
Delete account (owner only)

**Response:** `204 No Content`

---

## 👥 Team Endpoints (CRUD)

#### GET /accounts/:account_id/team
List team members

**Response:** `200 OK`
```json
{
  "members": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "email": "member@example.com",
      "full_name": "Jane Doe",
      "avatar_url": "https://...",
      "role": "editor",
      "invited_by": "uuid",
      "invited_at": "2025-01-15T00:00:00Z",
      "accepted_at": "2025-01-15T01:00:00Z",
      "is_active": true
    }
  ]
}
```

#### POST /accounts/:account_id/team/invite
Invite team member

**Request:**
```json
{
  "email": "newmember@example.com",
  "role": "editor"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "invitation_token": "token",
  "invitation_expires_at": "2025-02-23T10:00:00Z",
  "message": "Invitation sent successfully"
}
```

#### PUT /accounts/:account_id/team/:member_id
Update team member role

**Request:**
```json
{
  "role": "manager"
}
```

**Response:** `200 OK` (returns updated member)

#### DELETE /accounts/:account_id/team/:member_id
Remove team member

**Response:** `204 No Content`

#### POST /team/accept-invitation
Accept team invitation

**Request:**
```json
{
  "invitation_token": "token_from_email"
}
```

**Response:** `200 OK`
```json
{
  "account": { /* account details */ },
  "member": { /* member details */ }
}
```

---

## 🔗 Platform Endpoints (CRUD)

#### GET /accounts/:account_id/platforms
List connected platforms

**Response:** `200 OK`
```json
{
  "platforms": [
    {
      "id": "uuid",
      "platform_type": "instagram",
      "platform_account_name": "@mybusiness",
      "platform_profile_image": "https://...",
      "posting_enabled": true,
      "is_active": true,
      "health_status": "healthy",
      "connected_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /accounts/:account_id/platforms/:platform_type/connect
Initiate OAuth connection

**Parameters:**
- `platform_type`: facebook, instagram, linkedin, twitter

**Request:**
```json
{
  "redirect_uri": "https://yourapp.com/callback"
}
```

**Response:** `200 OK`
```json
{
  "authorization_url": "https://oauth.platform.com/authorize?...",
  "state": "random_state_string"
}
```

#### POST /accounts/:account_id/platforms/:platform_type/callback
Complete OAuth connection

**Request:**
```json
{
  "code": "oauth_code_from_callback",
  "state": "state_from_initial_request"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "platform_type": "instagram",
  "platform_account_name": "@mybusiness",
  "is_active": true,
  "message": "Platform connected successfully"
}
```

#### PUT /accounts/:account_id/platforms/:platform_id
Update platform settings

**Request:**
```json
{
  "posting_enabled": false,
  "auto_schedule_enabled": true
}
```

**Response:** `200 OK` (returns updated platform)

#### DELETE /accounts/:account_id/platforms/:platform_id
Disconnect platform

**Response:** `204 No Content`

#### POST /accounts/:account_id/platforms/:platform_id/refresh-token
Manually refresh OAuth token

**Response:** `200 OK`
```json
{
  "message": "Token refreshed successfully",
  "expires_at": "2025-04-16T10:00:00Z"
}
```

---

## 📝 Content Endpoints (CRUD)

#### GET /accounts/:account_id/posts
List posts

**Query Parameters:**
- `status` (draft, scheduled, published, failed)
- `platform` (instagram, facebook, linkedin, twitter)
- `start_date` (ISO 8601)
- `end_date` (ISO 8601)
- `page` (integer, default: 1)
- `limit` (integer, default: 20, max: 100)

**Response:** `200 OK`
```json
{
  "posts": [
    {
      "id": "uuid",
      "content": "Check out our new product! 🚀",
      "media_urls": ["https://..."],
      "hashtags": ["#marketing", "#business"],
      "platforms": [
        {
          "type": "instagram",
          "platform_id": "uuid",
          "post_id": "ig_123"
        }
      ],
      "status": "published",
      "scheduled_at": null,
      "published_at": "2025-02-15T14:00:00Z",
      "generated_by_ai": true,
      "created_by": "uuid",
      "created_at": "2025-02-15T13:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 50,
    "pages": 3
  }
}
```

#### POST /accounts/:account_id/posts
Create post

**Request:**
```json
{
  "content": "Check out our new product! 🚀",
  "media_urls": ["https://..."],
  "hashtags": ["#marketing", "#business"],
  "platforms": ["instagram", "facebook"],
  "status": "draft"
}
```

**Response:** `201 Created` (returns created post)

#### GET /accounts/:account_id/posts/:post_id
Get post details

**Response:** `200 OK` (same structure as list, single object)

#### PUT /accounts/:account_id/posts/:post_id
Update post

**Request:**
```json
{
  "content": "Updated content",
  "hashtags": ["#marketing", "#saas"],
  "scheduled_at": "2025-02-20T15:00:00Z"
}
```

**Response:** `200 OK` (returns updated post)

#### DELETE /accounts/:account_id/posts/:post_id
Delete post

**Response:** `204 No Content`

#### POST /accounts/:account_id/posts/:post_id/publish
Publish post immediately

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "status": "publishing",
  "message": "Post is being published"
}
```

#### POST /accounts/:account_id/posts/:post_id/schedule
Schedule post for later

**Request:**
```json
{
  "scheduled_at": "2025-02-20T15:00:00Z"
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "status": "scheduled",
  "scheduled_at": "2025-02-20T15:00:00Z"
}
```

#### POST /accounts/:account_id/posts/:post_id/duplicate
Duplicate post

**Response:** `201 Created` (returns duplicated post)

---

## 🤖 AI Content Generation Endpoints

#### POST /accounts/:account_id/content/generate
Generate content with AI

**Request:**
```json
{
  "prompt": "Post about new product launch",
  "platforms": ["instagram", "facebook"],
  "tone": "professional",
  "include_image": true,
  "business_id": "uuid"
}
```

**Response:** `200 OK`
```json
{
  "generations": [
    {
      "platform": "instagram",
      "content": "🚀 Excited to announce...",
      "hashtags": ["#product", "#launch"],
      "image_url": "https://...",
      "ai_model": "gpt-4-turbo"
    },
    {
      "platform": "facebook",
      "content": "We're thrilled to share...",
      "image_url": "https://...",
      "ai_model": "gpt-4-turbo"
    }
  ],
  "generation_id": "uuid",
  "cost": 0.05
}
```

#### POST /accounts/:account_id/content/regenerate-image
Regenerate image for post

**Request:**
```json
{
  "prompt": "Modern minimalist office space",
  "style": "photography"
}
```

**Response:** `200 OK`
```json
{
  "image_url": "https://...",
  "generation_id": "uuid",
  "cost": 0.04
}
```

#### POST /accounts/:account_id/content/suggest-topics
Get AI content topic suggestions

**Request:**
```json
{
  "business_id": "uuid",
  "count": 10
}
```

**Response:** `200 OK`
```json
{
  "suggestions": [
    {
      "topic": "Customer success story",
      "description": "Share a testimonial from a happy customer",
      "estimated_engagement": "high"
    },
    {
      "topic": "Behind the scenes",
      "description": "Show your team at work",
      "estimated_engagement": "medium"
    }
  ]
}
```

---

## 📊 Analytics Endpoints

#### GET /accounts/:account_id/analytics/overview
Get analytics overview

**Query Parameters:**
- `start_date` (ISO 8601, default: 30 days ago)
- `end_date` (ISO 8601, default: now)

**Response:** `200 OK`
```json
{
  "period": {
    "start_date": "2025-01-16",
    "end_date": "2025-02-16"
  },
  "metrics": {
    "total_posts": 45,
    "total_reach": 125000,
    "total_impressions": 180000,
    "total_engagement": 8500,
    "avg_engagement_rate": 6.8,
    "follower_growth": 1250,
    "follower_growth_rate": 12.5
  },
  "by_platform": {
    "instagram": {
      "posts": 20,
      "reach": 75000,
      "engagement": 5200,
      "engagement_rate": 6.9
    },
    "facebook": {
      "posts": 15,
      "reach": 35000,
      "engagement": 2100,
      "engagement_rate": 6.0
    },
    "linkedin": {
      "posts": 10,
      "reach": 15000,
      "engagement": 1200,
      "engagement_rate": 8.0
    }
  },
  "comparison": {
    "reach_change": 15.3,
    "engagement_change": 23.1
  }
}
```

#### GET /accounts/:account_id/analytics/posts/top
Get top performing posts

**Query Parameters:**
- `limit` (integer, default: 10, max: 50)
- `metric` (reach, engagement, engagement_rate)
- `period` (7d, 30d, 90d, all)

**Response:** `200 OK`
```json
{
  "posts": [
    {
      "id": "uuid",
      "content": "Post content...",
      "published_at": "2025-02-10T12:00:00Z",
      "metrics": {
        "reach": 15000,
        "engagement": 1250,
        "engagement_rate": 8.3,
        "likes": 850,
        "comments": 120,
        "shares": 280
      },
      "platforms": ["instagram"]
    }
  ]
}
```

#### GET /accounts/:account_id/analytics/trends
Get performance trends over time

**Query Parameters:**
- `metric` (reach, engagement, engagement_rate)
- `granularity` (day, week, month)
- `start_date`
- `end_date`

**Response:** `200 OK`
```json
{
  "metric": "engagement",
  "granularity": "day",
  "data": [
    {
      "date": "2025-02-10",
      "value": 450
    },
    {
      "date": "2025-02-11",
      "value": 520
    }
  ]
}
```

#### GET /accounts/:account_id/analytics/export
Export analytics report

**Query Parameters:**
- `format` (pdf, csv)
- `start_date`
- `end_date`

**Response:** `200 OK`
```json
{
  "download_url": "https://...",
  "expires_at": "2025-02-17T10:00:00Z",
  "file_size": 245678
}
```

---

## 🎯 Strategy Endpoints

#### GET /accounts/:account_id/strategies
List strategies

**Response:** `200 OK`
```json
{
  "strategies": [
    {
      "id": "uuid",
      "name": "Q1 2025 Strategy",
      "goal": "increase_sales",
      "is_active": true,
      "performance_score": 8.5,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /accounts/:account_id/strategies/generate
Generate AI strategy

**Request:**
```json
{
  "business_id": "uuid",
  "goal": "increase_sales",
  "monthly_budget": 500
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "Sales Growth Strategy",
  "goal": "increase_sales",
  "platform_mix": {
    "instagram": 0.6,
    "facebook": 0.3,
    "linkedin": 0.1
  },
  "posting_frequency": {
    "instagram": {
      "per_week": 5,
      "best_times": ["11:00", "13:00", "17:00"]
    }
  },
  "content_themes": [
    "product_showcase",
    "customer_stories"
  ],
  "reasoning": "Based on your B2C e-commerce business...",
  "confidence_score": 0.85
}
```

#### GET /accounts/:account_id/strategies/:strategy_id
Get strategy details

**Response:** `200 OK` (same structure as generate)

#### PUT /accounts/:account_id/strategies/:strategy_id
Update strategy

**Request:**
```json
{
  "platform_mix": {
    "instagram": 0.7,
    "facebook": 0.2,
    "linkedin": 0.1
  }
}
```

**Response:** `200 OK` (returns updated strategy)

#### DELETE /accounts/:account_id/strategies/:strategy_id
Delete strategy

**Response:** `204 No Content`

#### POST /accounts/:account_id/strategies/:strategy_id/apply
Apply strategy recommendations

**Response:** `200 OK`
```json
{
  "message": "Strategy applied successfully",
  "changes": [
    "Updated posting frequency",
    "Adjusted platform mix"
  ]
}
```

---

## 🔔 Notification Endpoints

#### GET /notifications
Get user notifications

**Query Parameters:**
- `unread` (boolean)
- `limit` (integer, default: 20)

**Response:** `200 OK`
```json
{
  "notifications": [
    {
      "id": "uuid",
      "type": "post_published",
      "title": "Post Published Successfully",
      "message": "Your post 'Check out...' was published",
      "action_url": "/accounts/uuid/posts/uuid",
      "action_text": "View Post",
      "is_read": false,
      "created_at": "2025-02-16T09:00:00Z"
    }
  ],
  "unread_count": 5
}
```

#### PUT /notifications/:id/read
Mark notification as read

**Response:** `200 OK`

#### PUT /notifications/read-all
Mark all notifications as read

**Response:** `200 OK`

#### DELETE /notifications/:id
Delete notification

**Response:** `204 No Content`

---

## ⚙️ Settings Endpoints

#### GET /accounts/:account_id/settings
Get account settings

**Response:** `200 OK`
```json
{
  "notifications": {
    "email_daily_summary": true,
    "email_post_published": true,
    "email_approval_requested": true
  },
  "posting": {
    "require_approval": false,
    "auto_schedule_enabled": true,
    "default_timezone": "America/New_York"
  },
  "ai": {
    "default_tone": "professional",
    "always_generate_images": true
  }
}
```

#### PUT /accounts/:account_id/settings
Update account settings

**Request:**
```json
{
  "notifications": {
    "email_daily_summary": false
  }
}
```

**Response:** `200 OK` (returns updated settings)

---

## 💳 Billing Endpoints

#### GET /accounts/:account_id/billing
Get billing information

**Response:** `200 OK`
```json
{
  "subscription": {
    "tier": "growth",
    "status": "active",
    "current_period_start": "2025-02-01T00:00:00Z",
    "current_period_end": "2025-03-01T00:00:00Z",
    "cancel_at_period_end": false
  },
  "usage": {
    "posts_this_month": 45,
    "post_limit": 100,
    "ai_cost_this_month": 12.50
  },
  "payment_method": {
    "type": "card",
    "last4": "4242",
    "brand": "visa",
    "exp_month": 12,
    "exp_year": 2026
  }
}
```

#### POST /accounts/:account_id/billing/checkout
Create checkout session for subscription

**Request:**
```json
{
  "tier": "growth",
  "billing_period": "monthly"
}
```

**Response:** `200 OK`
```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_..."
}
```

#### POST /accounts/:account_id/billing/portal
Create customer portal session

**Response:** `200 OK`
```json
{
  "portal_url": "https://billing.stripe.com/..."
}
```

#### GET /accounts/:account_id/billing/invoices
List invoices

**Response:** `200 OK`
```json
{
  "invoices": [
    {
      "id": "in_...",
      "amount": 149.00,
      "currency": "usd",
      "status": "paid",
      "created_at": "2025-02-01T00:00:00Z",
      "invoice_pdf": "https://..."
    }
  ]
}
```

---

## 📋 Common Response Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST creating resource |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing or invalid auth token |
| 403 | Forbidden | Authenticated but no permission |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists |
| 422 | Unprocessable Entity | Validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Maintenance or overload |

---

## 🚨 Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid email format",
    "details": {
      "field": "email",
      "value": "invalid-email"
    },
    "request_id": "req_123abc",
    "timestamp": "2025-02-16T10:00:00Z"
  }
}
```

---

## 🔒 Rate Limiting

**Rate Limits:**
- Free tier: 100 requests/minute
- Starter: 500 requests/minute
- Growth: 1000 requests/minute
- Pro: 5000 requests/minute
- Enterprise: Custom

**Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1613472000
```

---

## ✅ API Implementation Checklist

### Authentication
- [ ] Implement JWT token generation
- [ ] Implement refresh token logic
- [ ] Add token expiration handling
- [ ] Implement password reset flow

### CRUD Operations
- [ ] All account endpoints
- [ ] All user endpoints
- [ ] All post endpoints
- [ ] All platform endpoints
- [ ] All team endpoints

### Business Logic
- [ ] Permission checks on all endpoints
- [ ] Rate limiting
- [ ] Input validation
- [ ] Error handling

### Testing
- [ ] Unit tests for all endpoints
- [ ] Integration tests
- [ ] Load testing
- [ ] Security testing

### Documentation
- [ ] OpenAPI/Swagger docs
- [ ] Postman collection
- [ ] Example requests/responses
- [ ] Error code reference

---

**API Status:** Implementation Ready  
**Next Steps:** Generate OpenAPI spec → Implement endpoints → Test → Document  
**Review:** Before production deployment
