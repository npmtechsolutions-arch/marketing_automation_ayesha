import { useState } from "react";
import { motion } from "framer-motion";
import {
  Code2,
  Copy,
  Check,
  Lock,
  Users,
  FileText,
  BarChart3,
  Lightbulb,
  Webhook,
  Key,
  Zap,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------
const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

interface Param {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

interface Endpoint {
  method: HttpMethod;
  path: string;
  description: string;
  params?: Param[];
  requestBody?: string;
  responseBody: string;
}

interface EndpointCategory {
  id: string;
  label: string;
  icon: typeof Lock;
  endpoints: Endpoint[];
}

// ---------------------------------------------------------------------------
// Method badge config
// ---------------------------------------------------------------------------
const methodConfig: Record<HttpMethod, { bg: string; text: string; border: string }> = {
  GET: { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  POST: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/20" },
  PUT: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/20" },
  DELETE: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/20" },
};

// ---------------------------------------------------------------------------
// API data
// ---------------------------------------------------------------------------
const apiCategories: EndpointCategory[] = [
  {
    id: "auth",
    label: "Authentication",
    icon: Lock,
    endpoints: [
      {
        method: "POST",
        path: "/api/v1/auth/login",
        description: "Authenticate a user and receive an access token and refresh token pair.",
        params: undefined,
        requestBody: `{
  "email": "user@example.com",
  "password": "your-password",
  "mfa_code": "123456"
}`,
        responseBody: `{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "user": {
    "id": "usr_a1b2c3",
    "email": "user@example.com",
    "name": "Sarah Chen"
  }
}`,
      },
      {
        method: "POST",
        path: "/api/v1/auth/refresh",
        description: "Exchange a refresh token for a new access token.",
        requestBody: `{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g..."
}`,
        responseBody: `{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "expires_in": 3600,
  "token_type": "Bearer"
}`,
      },
      {
        method: "POST",
        path: "/api/v1/auth/logout",
        description: "Revoke the current session and invalidate tokens.",
        requestBody: `{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2g..."
}`,
        responseBody: `{
  "success": true,
  "message": "Session revoked successfully"
}`,
      },
    ],
  },
  {
    id: "users",
    label: "Users",
    icon: Users,
    endpoints: [
      {
        method: "GET",
        path: "/api/v1/users/me",
        description: "Retrieve the authenticated user's profile, including plan and connected platforms.",
        responseBody: `{
  "id": "usr_a1b2c3",
  "name": "Sarah Chen",
  "email": "sarah.chen@techstart.io",
  "avatar_url": "https://cdn.visionaryspace.com/avatars/usr_a1b2c3.jpg",
  "plan": "professional",
  "created_at": "2025-06-14T10:30:00Z",
  "connected_platforms": ["instagram", "linkedin", "twitter"]
}`,
      },
      {
        method: "PUT",
        path: "/api/v1/users/me",
        description: "Update the authenticated user's profile fields.",
        requestBody: `{
  "name": "Sarah Chen",
  "timezone": "America/Los_Angeles",
  "notification_preferences": {
    "email_digest": "weekly",
    "push_enabled": true
  }
}`,
        responseBody: `{
  "id": "usr_a1b2c3",
  "name": "Sarah Chen",
  "timezone": "America/Los_Angeles",
  "updated_at": "2026-03-30T09:15:00Z"
}`,
      },
      {
        method: "GET",
        path: "/api/v1/users/me/accounts",
        description: "List all social media accounts connected to the authenticated user.",
        params: [
          { name: "platform", type: "string", required: false, description: "Filter by platform (e.g., instagram, linkedin)" },
          { name: "status", type: "string", required: false, description: "Filter by status: active, expired, error" },
        ],
        responseBody: `{
  "data": [
    {
      "id": "acc_x1y2z3",
      "platform": "instagram",
      "username": "@techstart",
      "followers": 24500,
      "status": "active",
      "connected_at": "2025-08-01T14:00:00Z"
    }
  ],
  "total": 3
}`,
      },
    ],
  },
  {
    id: "content",
    label: "Content",
    icon: FileText,
    endpoints: [
      {
        method: "GET",
        path: "/api/v1/posts",
        description: "Retrieve a paginated list of posts with optional filters.",
        params: [
          { name: "status", type: "string", required: false, description: "Filter: draft, scheduled, published, failed" },
          { name: "platform", type: "string", required: false, description: "Filter by target platform" },
          { name: "page", type: "integer", required: false, description: "Page number (default: 1)" },
          { name: "per_page", type: "integer", required: false, description: "Items per page (default: 20, max: 100)" },
        ],
        responseBody: `{
  "data": [
    {
      "id": "pst_m1n2o3",
      "content": "Excited to share our Q1 results...",
      "platforms": ["linkedin", "twitter"],
      "status": "scheduled",
      "scheduled_for": "2026-04-01T10:00:00Z",
      "media": [],
      "created_at": "2026-03-28T14:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 142,
    "total_pages": 8
  }
}`,
      },
      {
        method: "POST",
        path: "/api/v1/posts",
        description: "Create a new post. It can be saved as a draft or scheduled for publishing.",
        requestBody: `{
  "content": "Check out our latest product update!",
  "platforms": ["instagram", "linkedin"],
  "scheduled_for": "2026-04-02T14:00:00Z",
  "media": [
    {
      "type": "image",
      "url": "https://cdn.visionaryspace.com/media/img_001.jpg"
    }
  ],
  "hashtags": ["#productupdate", "#saas"],
  "ai_optimized": true
}`,
        responseBody: `{
  "id": "pst_p4q5r6",
  "status": "scheduled",
  "scheduled_for": "2026-04-02T14:00:00Z",
  "platforms": ["instagram", "linkedin"],
  "created_at": "2026-03-30T09:00:00Z"
}`,
      },
      {
        method: "PUT",
        path: "/api/v1/posts/:id",
        description: "Update an existing post. Only draft and scheduled posts can be modified.",
        params: [
          { name: "id", type: "string", required: true, description: "The post ID (e.g., pst_m1n2o3)" },
        ],
        requestBody: `{
  "content": "Updated: Check out our latest feature release!",
  "scheduled_for": "2026-04-03T10:00:00Z"
}`,
        responseBody: `{
  "id": "pst_m1n2o3",
  "status": "scheduled",
  "content": "Updated: Check out our latest feature release!",
  "updated_at": "2026-03-30T09:30:00Z"
}`,
      },
      {
        method: "DELETE",
        path: "/api/v1/posts/:id",
        description: "Delete a post permanently. Published posts will be removed from connected platforms.",
        params: [
          { name: "id", type: "string", required: true, description: "The post ID" },
        ],
        responseBody: `{
  "success": true,
  "message": "Post deleted successfully",
  "platforms_removed": ["instagram", "linkedin"]
}`,
      },
    ],
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: BarChart3,
    endpoints: [
      {
        method: "GET",
        path: "/api/v1/analytics/overview",
        description: "Get an aggregated analytics overview across all connected platforms.",
        params: [
          { name: "period", type: "string", required: false, description: "Time period: 7d, 30d, 90d, 12m (default: 30d)" },
        ],
        responseBody: `{
  "period": "30d",
  "impressions": 284500,
  "engagement_rate": 4.8,
  "followers_gained": 1240,
  "posts_published": 34,
  "top_platform": "instagram",
  "best_performing_post": "pst_m1n2o3"
}`,
      },
      {
        method: "GET",
        path: "/api/v1/analytics/posts/:id",
        description: "Retrieve detailed analytics for a specific post across all platforms.",
        params: [
          { name: "id", type: "string", required: true, description: "The post ID" },
        ],
        responseBody: `{
  "post_id": "pst_m1n2o3",
  "platforms": {
    "instagram": {
      "impressions": 12400,
      "likes": 482,
      "comments": 67,
      "shares": 31,
      "saves": 89
    },
    "linkedin": {
      "impressions": 8200,
      "reactions": 124,
      "comments": 18,
      "reposts": 12
    }
  },
  "aggregate": {
    "total_impressions": 20600,
    "total_engagement": 823,
    "engagement_rate": 4.0
  }
}`,
      },
      {
        method: "GET",
        path: "/api/v1/analytics/audience",
        description: "Get audience demographics and growth data for connected platforms.",
        params: [
          { name: "platform", type: "string", required: false, description: "Filter by platform" },
          { name: "period", type: "string", required: false, description: "Time period: 7d, 30d, 90d" },
        ],
        responseBody: `{
  "total_followers": 48200,
  "growth": {
    "absolute": 1240,
    "percentage": 2.6
  },
  "demographics": {
    "age_groups": {
      "18-24": 18.5,
      "25-34": 42.3,
      "35-44": 24.1,
      "45+": 15.1
    },
    "top_countries": [
      { "code": "US", "percentage": 38.2 },
      { "code": "GB", "percentage": 12.5 },
      { "code": "DE", "percentage": 8.1 }
    ]
  }
}`,
      },
    ],
  },
  {
    id: "strategy",
    label: "AI Strategy",
    icon: Lightbulb,
    endpoints: [
      {
        method: "POST",
        path: "/api/v1/strategy/generate",
        description: "Generate an AI-powered content strategy based on your analytics and goals.",
        requestBody: `{
  "goal": "increase_engagement",
  "platforms": ["instagram", "linkedin"],
  "timeframe": "30d",
  "brand_voice": "professional yet approachable",
  "topics": ["product updates", "industry insights"]
}`,
        responseBody: `{
  "strategy_id": "str_k1l2m3",
  "recommendations": [
    {
      "type": "posting_schedule",
      "detail": "Post 4x/week on Instagram, 3x/week on LinkedIn",
      "confidence": 0.89
    },
    {
      "type": "content_mix",
      "detail": "40% educational, 30% behind-the-scenes, 20% product, 10% UGC",
      "confidence": 0.82
    },
    {
      "type": "best_times",
      "detail": "Instagram: Tue/Thu 9am, Sat 11am. LinkedIn: Mon/Wed 8am",
      "confidence": 0.91
    }
  ],
  "generated_at": "2026-03-30T09:45:00Z"
}`,
      },
      {
        method: "POST",
        path: "/api/v1/strategy/caption",
        description: "Generate AI-optimized captions for a given topic and platform.",
        requestBody: `{
  "topic": "Spring product launch announcement",
  "platform": "instagram",
  "tone": "excited",
  "include_hashtags": true,
  "max_length": 300
}`,
        responseBody: `{
  "captions": [
    {
      "text": "Spring is here and so is something BIG 🌸 We've been working behind the scenes on our most requested feature yet. Stay tuned for the big reveal this Thursday!\\n\\n#ProductLaunch #SpringRelease #Innovation",
      "estimated_engagement": "high",
      "hashtag_reach": 142000
    },
    {
      "text": "The wait is almost over. This Thursday, we're launching the feature you've been asking for since day one. Spring cleaning? More like spring shipping 🚀\\n\\n#NewFeature #ComingSoon #BuildInPublic",
      "estimated_engagement": "medium-high",
      "hashtag_reach": 98000
    }
  ]
}`,
      },
      {
        method: "GET",
        path: "/api/v1/strategy/trends",
        description: "Get current trending topics and hashtags relevant to your industry and audience.",
        params: [
          { name: "platform", type: "string", required: false, description: "Filter trends by platform" },
          { name: "industry", type: "string", required: false, description: "Industry vertical (e.g., saas, ecommerce)" },
        ],
        responseBody: `{
  "trends": [
    {
      "topic": "AI in Marketing",
      "volume": "rising",
      "relevance_score": 0.94,
      "suggested_hashtags": ["#AIMarketing", "#MarTech", "#FutureOfMarketing"]
    },
    {
      "topic": "Short-form Video",
      "volume": "high",
      "relevance_score": 0.87,
      "suggested_hashtags": ["#Reels", "#ShortFormContent"]
    }
  ],
  "updated_at": "2026-03-30T06:00:00Z"
}`,
      },
    ],
  },
  {
    id: "webhooks",
    label: "Webhooks",
    icon: Webhook,
    endpoints: [
      {
        method: "GET",
        path: "/api/v1/webhooks",
        description: "List all registered webhook endpoints for the authenticated account.",
        responseBody: `{
  "data": [
    {
      "id": "wh_a1b2c3",
      "url": "https://yourapp.com/webhooks/vs",
      "events": ["post.published", "post.failed"],
      "status": "active",
      "created_at": "2026-01-15T10:00:00Z"
    }
  ],
  "total": 1
}`,
      },
      {
        method: "POST",
        path: "/api/v1/webhooks",
        description: "Register a new webhook endpoint to receive event notifications.",
        requestBody: `{
  "url": "https://yourapp.com/webhooks/vs",
  "events": [
    "post.published",
    "post.failed",
    "platform.disconnected"
  ],
  "secret": "whsec_your_signing_secret"
}`,
        responseBody: `{
  "id": "wh_d4e5f6",
  "url": "https://yourapp.com/webhooks/vs",
  "events": ["post.published", "post.failed", "platform.disconnected"],
  "status": "active",
  "created_at": "2026-03-30T10:00:00Z"
}`,
      },
      {
        method: "DELETE",
        path: "/api/v1/webhooks/:id",
        description: "Delete a webhook endpoint. No further events will be sent to this URL.",
        params: [
          { name: "id", type: "string", required: true, description: "The webhook ID" },
        ],
        responseBody: `{
  "success": true,
  "message": "Webhook deleted successfully"
}`,
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Code block component
// ---------------------------------------------------------------------------
function CodeBlock({ code, label }: { code: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl bg-black/40 border border-white/5 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-white/[0.02] border-b border-white/5">
        <span className="text-[11px] text-gray-500 font-mono uppercase tracking-wider">{label}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-white transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="p-4 text-[13px] text-gray-300 font-mono overflow-x-auto leading-relaxed whitespace-pre">
        {code}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Method badge
// ---------------------------------------------------------------------------
function MethodBadge({ method }: { method: HttpMethod }) {
  const config = methodConfig[method];
  return (
    <span className={cn("inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold font-mono border", config.bg, config.text, config.border)}>
      {method}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ApiDocsPage() {
  const [activeCategory, setActiveCategory] = useState("auth");

  const currentCategory = apiCategories.find((c) => c.id === activeCategory) ?? apiCategories[0];

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Header */}
        <motion.div variants={fadeUp} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-600/20 to-cyan-600/20 border border-emerald-500/20 flex items-center justify-center">
              <Code2 className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">API Documentation</h1>
              <p className="text-sm text-gray-400">
                Base URL: <code className="text-emerald-400 font-mono text-xs bg-emerald-500/10 px-2 py-0.5 rounded">https://api.visionaryspace.com</code>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="success" dot size="sm">v1.0</Badge>
          </div>
        </motion.div>

        {/* Main layout */}
        <motion.div variants={fadeUp} className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="sticky top-6">
              <GlassCard padding="sm">
                <div className="flex items-center gap-2 px-3 py-2 mb-2">
                  <Key className="w-4 h-4 text-gray-400" />
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Endpoints</span>
                </div>
                <nav className="space-y-0.5">
                  {apiCategories.map((cat) => {
                    const Icon = cat.icon;
                    const isActive = cat.id === activeCategory;
                    return (
                      <button
                        key={cat.id}
                        onClick={() => setActiveCategory(cat.id)}
                        className={cn(
                          "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all",
                          isActive
                            ? "bg-purple-500/10 text-purple-300 border border-purple-500/20"
                            : "text-gray-400 hover:text-white hover:bg-white/5"
                        )}
                      >
                        <Icon className="w-4 h-4 flex-shrink-0" />
                        <span className="font-medium">{cat.label}</span>
                        <span className="ml-auto text-[11px] text-gray-600">{cat.endpoints.length}</span>
                      </button>
                    );
                  })}
                </nav>
              </GlassCard>
            </div>
          </div>

          {/* Endpoints */}
          <div className="lg:col-span-4 space-y-6">
            {currentCategory.endpoints.map((endpoint, idx) => (
              <GlassCard key={idx}>
                {/* Endpoint header */}
                <div className="flex items-start gap-3 mb-4">
                  <MethodBadge method={endpoint.method} />
                  <div className="flex-1 min-w-0">
                    <code className="text-base text-white font-mono font-medium break-all">
                      {endpoint.path}
                    </code>
                    <p className="text-sm text-gray-400 mt-1 leading-relaxed">
                      {endpoint.description}
                    </p>
                  </div>
                  <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-400 hover:text-white hover:bg-white/10 transition-colors flex-shrink-0">
                    <Zap className="w-3 h-3" />
                    Try it
                    <Badge variant="default" size="sm" className="ml-1">Soon</Badge>
                  </button>
                </div>

                {/* Parameters */}
                {endpoint.params && endpoint.params.length > 0 && (
                  <div className="mb-5">
                    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Parameters</h4>
                    <div className="rounded-xl bg-white/[0.02] border border-white/5 overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-white/5">
                            <th className="text-left text-gray-500 font-medium py-2.5 px-4 text-xs">Name</th>
                            <th className="text-left text-gray-500 font-medium py-2.5 px-4 text-xs">Type</th>
                            <th className="text-left text-gray-500 font-medium py-2.5 px-4 text-xs">Required</th>
                            <th className="text-left text-gray-500 font-medium py-2.5 px-4 text-xs">Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {endpoint.params.map((param, pi) => (
                            <tr key={pi} className="border-b border-white/5 last:border-0">
                              <td className="py-2.5 px-4">
                                <code className="text-purple-300 text-xs font-mono">{param.name}</code>
                              </td>
                              <td className="py-2.5 px-4">
                                <code className="text-gray-400 text-xs font-mono">{param.type}</code>
                              </td>
                              <td className="py-2.5 px-4">
                                {param.required ? (
                                  <Badge variant="danger" size="sm">Required</Badge>
                                ) : (
                                  <span className="text-xs text-gray-500">Optional</span>
                                )}
                              </td>
                              <td className="py-2.5 px-4 text-gray-400 text-xs">{param.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Request body */}
                {endpoint.requestBody && (
                  <div className="mb-5">
                    <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Request Body</h4>
                    <CodeBlock code={endpoint.requestBody} label="JSON" />
                  </div>
                )}

                {/* Response */}
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Response</h4>
                  <CodeBlock code={endpoint.responseBody} label="200 OK" />
                </div>
              </GlassCard>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
