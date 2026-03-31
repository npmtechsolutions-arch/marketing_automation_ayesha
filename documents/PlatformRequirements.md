# Platform & API Requirements Document

## 🎯 Overview
List of all external platforms, API keys, approvals, and third-party dependencies required for the AI marketing automation system.

---

## 📱 Social Media Platform APIs

### Meta (Facebook/Instagram)
- **What:** Meta Graph API
- **Purpose:** Post content, manage ads, access insights
- **Requirements:**
  - Meta Developer Account
  - App Review for `pages_manage_posts`, `instagram_content_publish`
  - Business verification for Ads API
- **API Keys Needed:**
  - App ID
  - App Secret
  - Access Token (per user)
- **Rate Limits:** 200 calls/hour/user
- **Cost:** Free for organic, % of ad spend for Ads API
- **Documentation:** https://developers.facebook.com/docs/graph-api

### LinkedIn
- **What:** LinkedIn Marketing API
- **Purpose:** Publish posts, run campaigns, analytics
- **Requirements:**
  - LinkedIn Developer Application
  - Marketing Developer Platform approval (takes 2-4 weeks)
  - OAuth 2.0 implementation
- **API Keys Needed:**
  - Client ID
  - Client Secret
  - Member Access Token
- **Rate Limits:** Varies by endpoint
- **Cost:** Free for organic posting
- **Documentation:** https://docs.microsoft.com/en-us/linkedin/marketing/

### Twitter/X
- **What:** X API v2
- **Purpose:** Post tweets, manage campaigns
- **Requirements:**
  - Developer Portal access
  - Elevated or Premium tier for ads
- **API Keys Needed:**
  - API Key
  - API Secret
  - Bearer Token
- **Rate Limits:** Based on tier (Basic/Pro/Enterprise)
- **Cost:** $100-$5000/month depending on volume
- **Documentation:** https://developer.twitter.com/en/docs

### YouTube
- **What:** YouTube Data API v3
- **Purpose:** Upload videos, manage channel
- **Requirements:**
  - Google Cloud Project
  - OAuth 2.0 consent screen approval
- **API Keys Needed:**
  - OAuth Client ID
  - Client Secret
- **Rate Limits:** 10,000 quota units/day
- **Cost:** Free up to quota
- **Documentation:** https://developers.google.com/youtube/v3

### TikTok
- **What:** TikTok for Business API
- **Purpose:** Post videos, run ads
- **Requirements:**
  - Business account
  - API access application
- **Status:** ⚠️ Difficult to get approved for small teams
- **Alternative:** Manual posting or later phase
- **Documentation:** https://ads.tiktok.com/marketing_api/docs

### Google My Business
- **What:** Google Business Profile API
- **Purpose:** Post updates to local business listings
- **Requirements:**
  - Google Cloud Project
  - Business Profile verification
- **API Keys Needed:**
  - OAuth 2.0 credentials
- **Cost:** Free
- **Documentation:** https://developers.google.com/my-business

### WhatsApp Business
- **What:** WhatsApp Business API
- **Purpose:** Send marketing messages, customer support
- **Requirements:**
  - Meta Business Account
  - Business verification
  - Phone number registration
- **API Keys Needed:**
  - Phone Number ID
  - WhatsApp Business Account ID
  - System User Token
- **Cost:** Per-message pricing (varies by country)
- **Documentation:** https://developers.facebook.com/docs/whatsapp

---

## 🤖 AI & LLM APIs

### OpenAI (GPT-4)
- **Purpose:** Content generation, strategy reasoning, creative writing
- **API Key:** Required
- **Cost:** 
  - GPT-4: ~$0.03/1K tokens input, $0.06/1K output
  - GPT-4-turbo: ~$0.01/1K tokens input, $0.03/1K output
- **Rate Limits:** Based on tier (Tier 1-5)
- **Documentation:** https://platform.openai.com/docs

### Anthropic Claude
- **Purpose:** Strategic analysis, long-form content, reasoning layer
- **API Key:** Required
- **Cost:** 
  - Claude Sonnet: ~$0.003/1K tokens input, $0.015/1K output
  - Claude Opus: ~$0.015/1K tokens input, $0.075/1K output
- **Rate Limits:** Based on tier
- **Documentation:** https://docs.anthropic.com

### Stability AI / DALL-E
- **Purpose:** Image generation for social posts
- **API Key:** Required
- **Cost:** 
  - DALL-E 3: $0.04-$0.12 per image
  - Stable Diffusion: $0.002-$0.01 per image
- **Alternative:** Use Replicate.com for multiple models
- **Documentation:** 
  - DALL-E: https://platform.openai.com/docs/guides/images
  - Stability: https://platform.stability.ai/docs

### Eleven Labs (Optional)
- **Purpose:** AI voice generation for video content
- **API Key:** Required
- **Cost:** Based on character count
- **Documentation:** https://elevenlabs.io/docs

---

## 📊 Analytics & Data APIs

### Google Analytics 4
- **Purpose:** Track website conversions, user behavior
- **Requirements:**
  - Google Cloud Project
  - OAuth 2.0 setup
- **API Key:** Service Account JSON
- **Cost:** Free
- **Documentation:** https://developers.google.com/analytics/devguides/reporting/data/v1

### Meta Pixel / Conversions API
- **Purpose:** Track ad performance, retargeting
- **Requirements:**
  - Pixel ID
  - Conversion API token
- **Setup:** Client-side + server-side tracking
- **Cost:** Free
- **Documentation:** https://developers.facebook.com/docs/marketing-api/conversions-api

### Google Ads API
- **Purpose:** Campaign management, performance tracking
- **Requirements:**
  - Google Ads Manager Account
  - Developer token (requires approval)
  - OAuth 2.0
- **API Keys Needed:**
  - Developer Token
  - Client ID
  - Client Secret
- **Cost:** Free
- **Documentation:** https://developers.google.com/google-ads/api

---

## 💳 Payment Processing

### Stripe
- **Purpose:** Subscription billing, one-time payments
- **Requirements:**
  - Stripe account
  - Business verification for production
- **API Keys:**
  - Publishable Key (client-side)
  - Secret Key (server-side)
  - Webhook Secret (for events)
- **Cost:** 2.9% + $0.30 per transaction
- **Documentation:** https://stripe.com/docs/api

### Paddle (Alternative)
- **Purpose:** Merchant of record, handles tax/compliance
- **API Keys:** Required
- **Cost:** 5% + $0.50 per transaction
- **Documentation:** https://developer.paddle.com/

---

## 🔐 Authentication & Infrastructure

### Google OAuth 2.0
- **Purpose:** "Sign in with Google"
- **Requirements:** Google Cloud Console setup
- **API Keys:**
  - Client ID
  - Client Secret
- **Cost:** Free
- **Documentation:** https://developers.google.com/identity/protocols/oauth2

### Supabase Auth
- **Purpose:** User authentication management, database
- **Requirements:** Supabase project
- **API Keys:**
  - API URL
  - anon/public key
  - service_role key (server-side only)
- **Cost:** Free tier available, $25/month Pro
- **Documentation:** https://supabase.com/docs/guides/auth

### Auth0 (Alternative)
- **Purpose:** Enterprise-grade authentication
- **Cost:** Free up to 7,000 MAU
- **Documentation:** https://auth0.com/docs

---

## 📧 Communication APIs

### SendGrid / Resend
- **Purpose:** Transactional emails, notifications
- **API Key:** Required
- **Cost:** 
  - SendGrid: Free up to 100 emails/day
  - Resend: Free up to 3,000 emails/month
- **Documentation:** 
  - SendGrid: https://docs.sendgrid.com/
  - Resend: https://resend.com/docs

### Twilio (Optional)
- **Purpose:** SMS notifications, 2FA
- **API Keys:**
  - Account SID
  - Auth Token
- **Cost:** Per-message pricing
- **Documentation:** https://www.twilio.com/docs

---

## 🗄️ Database & Storage

### PostgreSQL (Supabase)
- **Covered in TechStack.md**
- **Purpose:** Primary database
- **Connection String:** Required in .env

### AWS S3 / Cloudflare R2
- **Purpose:** Image/video storage for generated content
- **API Keys:**
  - Access Key ID
  - Secret Access Key
  - Bucket Name
- **Cost:** 
  - R2: $0.015/GB storage (cheaper than S3)
  - S3: $0.023/GB storage
- **Documentation:** 
  - R2: https://developers.cloudflare.com/r2/
  - S3: https://docs.aws.amazon.com/s3/

---

## 🚨 Critical Approvals Timeline

| Platform | Approval Time | Difficulty | Priority | Notes |
|----------|---------------|------------|----------|-------|
| Meta Business | 2-5 days | Medium | HIGH | Needed for Instagram API |
| LinkedIn Marketing API | 2-4 weeks | High | HIGH | Long approval process |
| Google Ads API | 3-7 days | Medium | MEDIUM | Requires spending history |
| Twitter/X API | Instant (paid) | Low | LOW | Can buy immediately |
| WhatsApp Business | 1-2 weeks | Medium | MEDIUM | Business verification needed |
| Stripe Production | 1-2 days | Low | HIGH | Identity verification |

---

## 📋 MVP Phase 1 (Start Here)

**Minimum required to launch basic version:**

✅ **Must Have:**
- OpenAI API (content generation)
- Meta Graph API (Facebook/Instagram posting)
- Stripe (payments)
- Google OAuth (user login)
- Supabase (auth + database)
- SendGrid/Resend (email notifications)

⏳ **Can Add Later:**
- LinkedIn API (if B2B focus)
- Google Ads API (Phase 2)
- Twitter/X API (Phase 3)
- WhatsApp Business (Phase 3)
- Advanced AI models (Phase 2+)

---

## 🛠 Local Development Setup

### Environment Variables Structure

Create a `.env` file in your project root:

```bash
# =================================
# AI APIs
# =================================
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# =================================
# Social Media Platforms
# =================================
# Meta (Facebook/Instagram)
META_APP_ID=...
META_APP_SECRET=...
META_ACCESS_TOKEN=...

# LinkedIn
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...

# Twitter/X
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_BEARER_TOKEN=...

# Google (YouTube + Analytics)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# =================================
# Payments
# =================================
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# =================================
# Authentication
# =================================
JWT_SECRET_KEY=your-super-secret-key-min-32-chars
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...

# =================================
# Database (from TechStack.md)
# =================================
DATABASE_URL=postgresql://user:password@localhost:5432/marketing_ai
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...

# =================================
# Storage
# =================================
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=marketing-ai-assets
AWS_REGION=us-east-1

# Or use Cloudflare R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...

# =================================
# Email
# =================================
SENDGRID_API_KEY=SG....
FROM_EMAIL=noreply@yourdomain.com

# =================================
# Application Settings
# =================================
ENVIRONMENT=development
DEBUG=true
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

### .env.example Template

Create `.env.example` (commit this to git):

```bash
# Copy this file to .env and fill in your actual values
# NEVER commit .env to git

# AI APIs
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Meta
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# etc...
```

---

## ⚠️ Security Best Practices

### 1. Never Commit Secrets
```bash
# Add to .gitignore
.env
.env.local
.env.production
*.key
*.pem
secrets/
```

### 2. Use Secret Management in Production

**Vercel:**
```bash
vercel env add OPENAI_API_KEY
```

**Railway:**
- Use the Variables tab in dashboard
- Enable "Raw Editor" for bulk import

**AWS:**
- Use AWS Secrets Manager
- Or AWS Systems Manager Parameter Store

**Self-Hosted:**
- Use HashiCorp Vault
- Or Docker secrets

### 3. Rotate Keys Regularly
- Rotate all API keys every 90 days
- Immediately rotate if compromised
- Use separate keys for dev/staging/production

### 4. Principle of Least Privilege
- Give each service only the permissions it needs
- Use read-only keys where possible
- Create separate service accounts per environment

### 5. Monitor API Usage
- Set up billing alerts on all platforms
- Monitor for unusual activity
- Log all API calls (without logging sensitive data)

---

## 💰 Monthly Cost Estimate

### Small Scale (100 active users, 1000 posts/month)

| Service | Estimated Cost |
|---------|----------------|
| OpenAI API (GPT-4) | $200-400 |
| Anthropic Claude | $100-200 |
| Image Generation (DALL-E/Stable Diffusion) | $50-100 |
| Meta API | Free (organic posting) |
| Stripe Fees | 2.9% of revenue |
| Supabase | $25 (Pro plan) |
| Hosting (Railway/Vercel) | $20-50 |
| Storage (S3/R2) | $5-10 |
| SendGrid Email | Free (under 100/day) |
| **Total Infrastructure** | **~$400-785/month** |

### Medium Scale (1,000 users, 10,000 posts/month)

| Service | Estimated Cost |
|---------|----------------|
| OpenAI API | $1,000-2,000 |
| Anthropic Claude | $500-1,000 |
| Image Generation | $200-500 |
| Meta API | Free (organic) |
| Stripe Fees | 2.9% of revenue |
| Supabase | $599 (Team plan) |
| Hosting | $100-200 |
| Storage | $50-100 |
| SendGrid Email | $19.95 (Essentials) |
| **Total Infrastructure** | **~$2,469-4,419/month** |

### Large Scale (10,000+ users, 100,000+ posts/month)

- Custom enterprise pricing required
- Consider self-hosting LLMs
- Negotiate volume discounts with providers
- Expected: $10,000-30,000/month

---

## 🔄 Update & Maintenance Cadence

### Monthly
- Review API usage and costs
- Check for deprecated endpoints
- Monitor rate limits and errors

### Quarterly
- Review and rotate API keys
- Audit security practices
- Evaluate new platform integrations
- Check for pricing changes

### Annually
- Full security audit
- Re-evaluate tech stack choices
- Update documentation
- Renew platform approvals (if required)

---

## 📝 Getting Started Checklist

### Week 1: Core Setup
- [ ] Create Meta Developer account
- [ ] Register Google Cloud Project
- [ ] Sign up for OpenAI API
- [ ] Create Stripe account
- [ ] Set up Supabase project
- [ ] Create SendGrid account

### Week 2: Platform Access
- [ ] Submit Meta app for review (pages_manage_posts)
- [ ] Apply for LinkedIn Marketing API access
- [ ] Configure OAuth flows for all platforms
- [ ] Set up webhook endpoints

### Week 3: Testing
- [ ] Test all API connections in development
- [ ] Verify OAuth flows work
- [ ] Test payment processing (Stripe test mode)
- [ ] Load test API rate limits

### Week 4: Production Ready
- [ ] Move all services to production mode
- [ ] Configure production environment variables
- [ ] Set up monitoring and alerts
- [ ] Document incident response procedures

---

## 🆘 Common Issues & Solutions

### Meta API Returns "Invalid Token"
**Solution:** Tokens expire. Implement token refresh flow using OAuth.

### LinkedIn API Request Rejected
**Solution:** Check if Marketing Developer Platform access is approved. Not all LinkedIn API keys have marketing permissions.

### OpenAI Rate Limit Errors
**Solution:** Implement exponential backoff. Consider upgrading to higher tier or using Azure OpenAI (higher limits).

### Stripe Webhook Not Receiving Events
**Solution:** 
1. Check webhook endpoint is publicly accessible
2. Verify webhook secret is correct
3. Use Stripe CLI for local testing: `stripe listen --forward-to localhost:8000/webhooks/stripe`

### Google OAuth "redirect_uri_mismatch"
**Solution:** Add exact redirect URI to Google Cloud Console (including http:// or https://, port number, and path).

---

## 📚 Additional Resources

### API Status Pages (Bookmark These)
- OpenAI: https://status.openai.com/
- Meta: https://developers.facebook.com/status/
- Stripe: https://status.stripe.com/
- Vercel: https://www.vercel-status.com/

### Rate Limit Calculators
- Most APIs provide rate limit headers in responses
- Implement rate limit tracking in your middleware
- Use libraries like `ratelimit` (Python) or built-in framework features

### Testing Tools
- Postman/Insomnia for API testing
- Stripe CLI for webhook testing
- ngrok for exposing localhost to internet (OAuth callbacks)

---

## 🎯 Next Steps

1. **Start with MVP requirements** listed above
2. **Apply for platform access** that requires approval (2-4 weeks lead time)
3. **Set up development environment** with all .env variables
4. **Build authentication flow** first (needed for all APIs)
5. **Integrate one platform at a time** (start with Meta)
6. **Add monitoring** from day one

---

## 📞 Support Contacts

Keep track of support channels for quick help:

- **OpenAI:** help.openai.com
- **Meta Developer Support:** developers.facebook.com/support
- **Stripe Support:** support.stripe.com (chat available)
- **Supabase:** support.supabase.com
- **LinkedIn Developer Support:** Limited, mostly documentation-based

---

**Last Updated:** 2025-02-16  
**Document Owner:** Engineering Team  
**Review Cycle:** Quarterly
