import { useState } from "react";
import { motion } from "framer-motion";
import {
  ChevronRight,
  Clock,
  Calendar,
  User,
  ThumbsUp,
  ThumbsDown,
  BookOpen,
  ArrowLeft,
  ArrowRight,
  Hash,
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
    transition: { staggerChildren: 0.06, delayChildren: 0.1 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// ---------------------------------------------------------------------------
// Mock article data
// ---------------------------------------------------------------------------
const article = {
  id: 1,
  title: "How to Connect Your First Social Media Account",
  category: "Getting Started",
  author: "Sarah Chen",
  updatedAt: "2026-03-15",
  readTime: "3 min read",
  tableOfContents: [
    { id: "prerequisites", label: "Prerequisites" },
    { id: "connect-account", label: "Connecting Your Account" },
    { id: "platform-setup", label: "Platform-Specific Setup" },
    { id: "permissions", label: "Required Permissions" },
    { id: "troubleshooting", label: "Troubleshooting" },
  ],
};

const relatedArticles = [
  { id: 2, title: "Managing Multiple Social Accounts", category: "Getting Started", readTime: "4 min" },
  { id: 3, title: "Understanding Platform Permissions", category: "Platform Connections", readTime: "5 min" },
  { id: 4, title: "Reconnecting a Disconnected Account", category: "Platform Connections", readTime: "2 min" },
];

const prevArticle = { id: 0, title: "Creating Your Account" };
const nextArticle = { id: 2, title: "Managing Multiple Social Accounts" };

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ArticlePage() {
  const [helpfulVote, setHelpfulVote] = useState<"yes" | "no" | null>(null);
  const [activeTocId, setActiveTocId] = useState("prerequisites");

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Breadcrumb */}
        <motion.div variants={fadeUp} className="flex items-center gap-2 text-sm">
          <button className="text-gray-400 hover:text-white transition-colors">Help Center</button>
          <ChevronRight className="w-3.5 h-3.5 text-gray-600" />
          <button className="text-gray-400 hover:text-white transition-colors">{article.category}</button>
          <ChevronRight className="w-3.5 h-3.5 text-gray-600" />
          <span className="text-purple-400 truncate max-w-[250px]">{article.title}</span>
        </motion.div>

        {/* Main layout: sidebar + article */}
        <motion.div variants={fadeUp} className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Table of Contents sidebar */}
          <div className="hidden lg:block lg:col-span-1">
            <div className="sticky top-6">
              <GlassCard padding="md">
                <div className="flex items-center gap-2 mb-4">
                  <BookOpen className="w-4 h-4 text-purple-400" />
                  <h3 className="text-sm font-semibold text-white">On this page</h3>
                </div>
                <nav className="space-y-1">
                  {article.tableOfContents.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setActiveTocId(item.id)}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
                        activeTocId === item.id
                          ? "bg-purple-500/10 text-purple-300 border-l-2 border-purple-500"
                          : "text-gray-400 hover:text-white hover:bg-white/5"
                      )}
                    >
                      {item.label}
                    </button>
                  ))}
                </nav>
              </GlassCard>
            </div>
          </div>

          {/* Article content */}
          <div className="lg:col-span-3">
            <GlassCard>
              {/* Article header */}
              <div className="mb-8">
                <Badge variant="info" size="sm" className="mb-4">{article.category}</Badge>
                <h1 className="text-2xl lg:text-3xl font-bold text-white tracking-tight mb-4">
                  {article.title}
                </h1>
                <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400">
                  <span className="flex items-center gap-1.5">
                    <User className="w-4 h-4" />
                    {article.author}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-4 h-4" />
                    Updated {article.updatedAt}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4" />
                    {article.readTime}
                  </span>
                </div>
              </div>

              {/* Article body */}
              <div className="prose-dark space-y-6">
                {/* Introduction */}
                <p className="text-gray-300 leading-relaxed">
                  Connecting your social media accounts is the first step to unlocking the full power of
                  VisionarySpace. This guide walks you through the process for each supported platform,
                  including the permissions needed and common troubleshooting steps.
                </p>

                {/* Section: Prerequisites */}
                <div id="prerequisites">
                  <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-3">
                    <Hash className="w-4 h-4 text-purple-400" />
                    Prerequisites
                  </h2>
                  <p className="text-gray-300 leading-relaxed mb-3">
                    Before connecting your accounts, make sure you have the following:
                  </p>
                  <ul className="space-y-2 pl-5">
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      An active VisionarySpace account (any plan)
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      Admin or owner access to the social media accounts you want to connect
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      For Instagram: a Business or Creator account linked to a Facebook Page
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      For LinkedIn: admin access to the Company Page (for company page posting)
                    </li>
                  </ul>
                </div>

                {/* Section: Connecting */}
                <div id="connect-account">
                  <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-3">
                    <Hash className="w-4 h-4 text-purple-400" />
                    Connecting Your Account
                  </h2>
                  <p className="text-gray-300 leading-relaxed mb-3">
                    Follow these steps to connect your first social media account:
                  </p>
                  <ol className="space-y-3 pl-5">
                    <li className="text-gray-300 text-sm leading-relaxed list-decimal">
                      Navigate to <span className="text-purple-300 font-medium">Platform Connections</span> in the sidebar
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-decimal">
                      Click the <span className="text-purple-300 font-medium">"Add Platform"</span> button
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-decimal">
                      Select the platform you want to connect (Instagram, Facebook, Twitter, etc.)
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-decimal">
                      You will be redirected to the platform's authorization page
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-decimal">
                      Grant the requested permissions and you will be redirected back
                    </li>
                  </ol>

                  {/* Code block */}
                  <div className="mt-4 rounded-xl bg-black/40 border border-white/5 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-2 bg-white/[0.02] border-b border-white/5">
                      <span className="text-xs text-gray-500 font-mono">API Example</span>
                      <button className="text-xs text-gray-500 hover:text-white transition-colors">Copy</button>
                    </div>
                    <pre className="p-4 text-sm text-gray-300 font-mono overflow-x-auto">
{`POST /api/v1/platforms/connect
Content-Type: application/json
Authorization: Bearer <your-api-token>

{
  "platform": "instagram",
  "redirect_uri": "https://app.visionaryspace.com/callback",
  "scopes": ["publish", "read_insights"]
}`}
                    </pre>
                  </div>
                </div>

                {/* Section: Platform setup */}
                <div id="platform-setup">
                  <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-3">
                    <Hash className="w-4 h-4 text-purple-400" />
                    Platform-Specific Setup
                  </h2>
                  <p className="text-gray-300 leading-relaxed mb-3">
                    Each platform has slightly different requirements. Here is a quick reference:
                  </p>

                  <div className="rounded-xl bg-white/[0.02] border border-white/5 overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/5">
                          <th className="text-left text-gray-400 font-medium py-3 px-4">Platform</th>
                          <th className="text-left text-gray-400 font-medium py-3 px-4">Account Type</th>
                          <th className="text-left text-gray-400 font-medium py-3 px-4">Requirements</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-white/5">
                          <td className="py-3 px-4 text-white font-medium">Instagram</td>
                          <td className="py-3 px-4 text-gray-300">Business / Creator</td>
                          <td className="py-3 px-4 text-gray-400">Linked Facebook Page</td>
                        </tr>
                        <tr className="border-b border-white/5">
                          <td className="py-3 px-4 text-white font-medium">Facebook</td>
                          <td className="py-3 px-4 text-gray-300">Page</td>
                          <td className="py-3 px-4 text-gray-400">Page admin access</td>
                        </tr>
                        <tr className="border-b border-white/5">
                          <td className="py-3 px-4 text-white font-medium">LinkedIn</td>
                          <td className="py-3 px-4 text-gray-300">Personal / Company</td>
                          <td className="py-3 px-4 text-gray-400">Company page admin (for org posts)</td>
                        </tr>
                        <tr>
                          <td className="py-3 px-4 text-white font-medium">Twitter / X</td>
                          <td className="py-3 px-4 text-gray-300">Standard</td>
                          <td className="py-3 px-4 text-gray-400">OAuth 2.0 enabled</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Section: Permissions */}
                <div id="permissions">
                  <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-3">
                    <Hash className="w-4 h-4 text-purple-400" />
                    Required Permissions
                  </h2>
                  <p className="text-gray-300 leading-relaxed">
                    VisionarySpace requests only the minimum permissions needed to publish content and
                    read analytics on your behalf. We never post without your explicit action, and you
                    can revoke access at any time from the Platform Connections page or from the
                    platform's own settings.
                  </p>
                </div>

                {/* Section: Troubleshooting */}
                <div id="troubleshooting">
                  <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-3">
                    <Hash className="w-4 h-4 text-purple-400" />
                    Troubleshooting
                  </h2>
                  <p className="text-gray-300 leading-relaxed mb-3">
                    If you encounter issues during the connection process, try the following:
                  </p>
                  <ul className="space-y-2 pl-5">
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      <span className="font-medium text-white">Clear browser cookies</span> -- Some OAuth flows can conflict with cached sessions
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      <span className="font-medium text-white">Check account type</span> -- Instagram personal accounts cannot be connected; switch to Business or Creator
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      <span className="font-medium text-white">Verify admin access</span> -- You must have admin permissions on the social account
                    </li>
                    <li className="text-gray-300 text-sm leading-relaxed list-disc">
                      <span className="font-medium text-white">Try a different browser</span> -- Browser extensions can sometimes block OAuth popups
                    </li>
                  </ul>
                </div>
              </div>

              {/* Helpful vote */}
              <div className="mt-10 pt-6 border-t border-white/5">
                <div className="flex items-center justify-center gap-4">
                  <span className="text-sm text-gray-400">Was this article helpful?</span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setHelpfulVote("yes")}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                        helpfulVote === "yes"
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          : "bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10 hover:text-white"
                      )}
                    >
                      <ThumbsUp className="w-4 h-4" /> Yes
                    </button>
                    <button
                      onClick={() => setHelpfulVote("no")}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                        helpfulVote === "no"
                          ? "bg-red-500/15 text-red-400 border border-red-500/30"
                          : "bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10 hover:text-white"
                      )}
                    >
                      <ThumbsDown className="w-4 h-4" /> No
                    </button>
                  </div>
                </div>
                {helpfulVote && (
                  <motion.p
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center text-sm text-gray-500 mt-3"
                  >
                    {helpfulVote === "yes"
                      ? "Thanks for your feedback!"
                      : "Sorry to hear that. Consider submitting a ticket so we can improve."}
                  </motion.p>
                )}
              </div>
            </GlassCard>

            {/* Related Articles */}
            <div className="mt-6">
              <h3 className="text-base font-semibold text-white mb-4">Related Articles</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {relatedArticles.map((ra) => (
                  <GlassCard key={ra.id} hover padding="md" className="group cursor-pointer">
                    <Badge variant="info" size="sm" className="mb-2">{ra.category}</Badge>
                    <h4 className="text-sm font-medium text-white group-hover:text-purple-300 transition-colors leading-snug">
                      {ra.title}
                    </h4>
                    <span className="flex items-center gap-1 text-xs text-gray-500 mt-2">
                      <Clock className="w-3 h-3" /> {ra.readTime}
                    </span>
                  </GlassCard>
                ))}
              </div>
            </div>

            {/* Previous / Next navigation */}
            <div className="mt-6 grid grid-cols-2 gap-4">
              <GlassCard hover padding="md" className="group cursor-pointer">
                <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                  <ArrowLeft className="w-3 h-3" /> Previous
                </div>
                <p className="text-sm font-medium text-white group-hover:text-purple-300 transition-colors">
                  {prevArticle.title}
                </p>
              </GlassCard>

              <GlassCard hover padding="md" className="group cursor-pointer text-right">
                <div className="flex items-center justify-end gap-2 text-xs text-gray-500 mb-1">
                  Next <ArrowRight className="w-3 h-3" />
                </div>
                <p className="text-sm font-medium text-white group-hover:text-purple-300 transition-colors">
                  {nextArticle.title}
                </p>
              </GlassCard>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
