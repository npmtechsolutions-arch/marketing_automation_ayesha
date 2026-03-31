import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Rocket,
  PenSquare,
  BarChart3,
  Users,
  CreditCard,
  Share2,
  ChevronDown,
  ChevronRight,
  Clock,
  BookOpen,
  Mail,
  MessageCircle,
  Globe,
  Send,
  Paperclip,
  HelpCircle,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
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
// Data
// ---------------------------------------------------------------------------
const categories = [
  { id: "getting-started", title: "Getting Started", description: "Set up your account and publish your first post", icon: Rocket, color: "from-blue-600/20 to-cyan-600/20", border: "border-blue-500/20", iconColor: "text-blue-400", articles: 12 },
  { id: "content-creation", title: "Content Creation", description: "Create, schedule, and manage your content", icon: PenSquare, color: "from-purple-600/20 to-fuchsia-600/20", border: "border-purple-500/20", iconColor: "text-purple-400", articles: 18 },
  { id: "analytics", title: "Analytics & Reports", description: "Understand your performance metrics", icon: BarChart3, color: "from-emerald-600/20 to-green-600/20", border: "border-emerald-500/20", iconColor: "text-emerald-400", articles: 14 },
  { id: "team", title: "Team & Collaboration", description: "Manage team members and approval workflows", icon: Users, color: "from-amber-600/20 to-yellow-600/20", border: "border-amber-500/20", iconColor: "text-amber-400", articles: 9 },
  { id: "billing", title: "Billing & Plans", description: "Subscriptions, invoices, and plan details", icon: CreditCard, color: "from-pink-600/20 to-rose-600/20", border: "border-pink-500/20", iconColor: "text-pink-400", articles: 11 },
  { id: "platforms", title: "Platform Connections", description: "Connect and manage your social accounts", icon: Share2, color: "from-cyan-600/20 to-teal-600/20", border: "border-cyan-500/20", iconColor: "text-cyan-400", articles: 15 },
];

const popularArticles = [
  { id: 1, title: "How to connect your first social media account", category: "Getting Started", readTime: "3 min", categoryColor: "info" as const },
  { id: 2, title: "Using AI to generate engaging post captions", category: "Content Creation", readTime: "5 min", categoryColor: "default" as const },
  { id: 3, title: "Understanding your engagement rate metrics", category: "Analytics & Reports", readTime: "4 min", categoryColor: "success" as const },
  { id: 4, title: "Setting up approval workflows for your team", category: "Team & Collaboration", readTime: "6 min", categoryColor: "warning" as const },
  { id: 5, title: "Upgrading your plan and managing billing", category: "Billing & Plans", readTime: "3 min", categoryColor: "danger" as const },
  { id: 6, title: "Best times to post on each platform", category: "Content Creation", readTime: "7 min", categoryColor: "default" as const },
];

const faqItems = [
  { q: "How do I connect my Instagram business account?", a: "Navigate to Platform Connections in the sidebar, click 'Add Platform', select Instagram, and follow the OAuth flow. Make sure your Instagram account is converted to a Business or Creator account first, and that it's linked to a Facebook Page." },
  { q: "Can I schedule posts to multiple platforms at once?", a: "Yes! When creating a new post, you can select multiple platforms from the platform selector. The content editor will show platform-specific previews so you can optimize each version before scheduling." },
  { q: "How does the AI content generation work?", a: "Our AI assistant uses advanced language models to generate post captions, hashtag suggestions, and content ideas based on your brand voice, past performance data, and current trends. You can access it from the content editor by clicking the sparkles icon." },
  { q: "What happens when my trial expires?", a: "When your 14-day trial ends, you'll be prompted to select a plan. Your data and connected accounts will be preserved for 30 days. You can upgrade at any time to continue where you left off." },
  { q: "How do I add team members to my account?", a: "Go to Team Settings, click 'Invite Member', enter their email address and select a role (Admin, Editor, or Viewer). They'll receive an email invitation to join your workspace." },
  { q: "Can I export my analytics data?", a: "Yes, all analytics reports can be exported as CSV or PDF. Navigate to any analytics page, click the 'Export' button in the top right, and select your preferred format and date range." },
  { q: "What social media platforms are supported?", a: "We currently support Instagram, Facebook, Twitter/X, LinkedIn, YouTube, TikTok, and Pinterest. We're constantly adding new platform integrations based on user feedback." },
  { q: "How do I cancel my subscription?", a: "You can cancel your subscription at any time from Billing & Plans settings. Your access will continue until the end of your current billing period. No data is deleted upon cancellation." },
];

const ticketCategories = [
  { value: "bug", label: "Bug Report" },
  { value: "feature", label: "Feature Request" },
  { value: "billing", label: "Billing Issue" },
  { value: "account", label: "Account Access" },
  { value: "other", label: "Other" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function HelpCenterPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [ticketSubject, setTicketSubject] = useState("");
  const [ticketCategory, setTicketCategory] = useState("");
  const [ticketDescription, setTicketDescription] = useState("");

  return (
    <DashboardLayout>
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="space-y-10"
      >
        {/* ----------------------------------------------------------------- */}
        {/* Hero / Search                                                     */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp} className="text-center pt-4">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 mb-5">
            <HelpCircle className="w-8 h-8 text-purple-400" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight mb-2">Help Center</h1>
          <p className="text-gray-400 mb-8 max-w-md mx-auto">
            Find answers, explore guides, and get the help you need.
          </p>

          <div className="max-w-xl mx-auto relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 z-10" />
            <input
              type="text"
              placeholder="Search articles, guides, and FAQs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl pl-12 pr-5 py-4 text-white text-base outline-none placeholder-gray-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
            />
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Category Cards                                                    */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {categories.map((cat) => {
              const Icon = cat.icon;
              return (
                <GlassCard key={cat.id} hover className="group">
                  <div className="flex items-start gap-4">
                    <div className={cn("w-12 h-12 rounded-xl bg-gradient-to-br border flex items-center justify-center flex-shrink-0", cat.color, cat.border)}>
                      <Icon className={cn("w-6 h-6", cat.iconColor)} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-base font-semibold text-white mb-1 group-hover:text-purple-300 transition-colors">
                        {cat.title}
                      </h3>
                      <p className="text-sm text-gray-400 leading-relaxed mb-2">
                        {cat.description}
                      </p>
                      <span className="text-xs text-gray-500">{cat.articles} articles</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-purple-400 transition-colors mt-1 flex-shrink-0" />
                  </div>
                </GlassCard>
              );
            })}
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Popular Articles                                                  */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <div className="flex items-center gap-2 mb-5">
            <Sparkles className="w-5 h-5 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Popular Articles</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {popularArticles.map((article) => (
              <GlassCard key={article.id} hover padding="md" className="group cursor-pointer">
                <div className="flex items-start justify-between mb-3">
                  <Badge variant={article.categoryColor} size="sm">
                    {article.category}
                  </Badge>
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <Clock className="w-3 h-3" />
                    {article.readTime}
                  </span>
                </div>
                <h3 className="text-sm font-semibold text-white leading-snug group-hover:text-purple-300 transition-colors">
                  {article.title}
                </h3>
                <div className="mt-3 flex items-center gap-1 text-xs text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity">
                  Read article <ArrowRight className="w-3 h-3" />
                </div>
              </GlassCard>
            ))}
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* FAQ Accordion                                                     */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <div className="flex items-center gap-2 mb-5">
            <BookOpen className="w-5 h-5 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Frequently Asked Questions</h2>
          </div>

          <div className="space-y-2">
            {faqItems.map((faq, i) => {
              const isOpen = openFaq === i;
              return (
                <GlassCard key={i} padding="sm" className="!p-0">
                  <button
                    onClick={() => setOpenFaq(isOpen ? null : i)}
                    className="w-full flex items-center justify-between p-4 text-left"
                  >
                    <span className="text-sm font-medium text-white pr-4">{faq.q}</span>
                    <ChevronDown className={cn("w-4 h-4 text-gray-400 flex-shrink-0 transition-transform duration-200", isOpen && "rotate-180")} />
                  </button>

                  <AnimatePresence>
                    {isOpen && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="px-4 pb-4 pt-0">
                          <p className="text-sm text-gray-400 leading-relaxed">{faq.a}</p>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </GlassCard>
              );
            })}
          </div>
        </motion.div>

        {/* ----------------------------------------------------------------- */}
        {/* Contact Support                                                   */}
        {/* ----------------------------------------------------------------- */}
        <motion.div variants={fadeUp}>
          <div className="flex items-center gap-2 mb-5">
            <Mail className="w-5 h-5 text-purple-400" />
            <h2 className="text-xl font-bold text-white">Contact Support</h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Contact options */}
            <div className="space-y-4">
              <GlassCard padding="md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                    <Mail className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white">Email Support</h4>
                    <p className="text-xs text-gray-400">support@visionaryspace.com</p>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">Typical response time: 2-4 hours</p>
              </GlassCard>

              <GlassCard padding="md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
                    <MessageCircle className="w-5 h-5 text-purple-400" />
                  </div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-white">Live Chat</h4>
                    <Badge variant="default" size="sm">Coming Soon</Badge>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">Real-time support with our team</p>
              </GlassCard>

              <GlassCard padding="md">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <Globe className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white">Community Forum</h4>
                    <p className="text-xs text-gray-400">community.visionaryspace.com</p>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">Connect with other users and share tips</p>
              </GlassCard>
            </div>

            {/* Ticket form */}
            <div className="lg:col-span-2">
              <GlassCard>
                <h3 className="text-lg font-semibold text-white mb-1">Submit a Ticket</h3>
                <p className="text-sm text-gray-400 mb-6">Describe your issue and we'll get back to you.</p>

                <div className="space-y-4">
                  <Input
                    label="Subject"
                    placeholder="Brief summary of your issue"
                    value={ticketSubject}
                    onChange={(e) => setTicketSubject(e.target.value)}
                  />

                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">
                      Category
                    </label>
                    <div className="relative">
                      <select
                        value={ticketCategory}
                        onChange={(e) => setTicketCategory(e.target.value)}
                        className="w-full appearance-none bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 pr-10 text-sm text-white outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all cursor-pointer"
                      >
                        <option value="" className="bg-slate-900" disabled>Select a category</option>
                        {ticketCategories.map((cat) => (
                          <option key={cat.value} value={cat.value} className="bg-slate-900">{cat.label}</option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5 pl-1">
                      Description
                    </label>
                    <textarea
                      value={ticketDescription}
                      onChange={(e) => setTicketDescription(e.target.value)}
                      placeholder="Describe your issue in detail..."
                      rows={5}
                      className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl px-4 py-3 text-sm text-white outline-none placeholder-gray-500 focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all resize-none"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <button className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
                      <Paperclip className="w-4 h-4" />
                      Attach file
                    </button>

                    <Button variant="primary" icon={<Send className="w-4 h-4" />}>
                      Submit Ticket
                    </Button>
                  </div>
                </div>
              </GlassCard>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </DashboardLayout>
  );
}
