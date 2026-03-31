import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Sparkles,
  Share2,
  BarChart3,
  Calendar,
  Users,
  ArrowRight,
  Star,
  Zap,
  Check,
  Play,
  Bot,
  Globe,
  Clock,
  Shield,
  MousePointerClick,
} from "lucide-react";
import PublicLayout from "@/components/layout/PublicLayout";

const fade = { hidden: { opacity: 0, y: 24 }, visible: { opacity: 1, y: 0 } };

export default function LandingPage() {
  const nav = useNavigate();

  return (
    <PublicLayout>
      {/* ═══════════════════════════════════════════
          HERO
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden px-4 pt-20 pb-24 md:pt-32 md:pb-36">
        {/* Subtle bg decoration */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 h-[600px] w-[600px] rounded-full bg-violet-200/30 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 h-[500px] w-[500px] rounded-full bg-sky-200/20 blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-4xl text-center">
          {/* Pill badge */}
          <motion.div initial={fade.hidden} animate={fade.visible} transition={{ duration: 0.5 }}>
            <span className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-violet-50 px-4 py-1.5 text-sm font-medium text-violet-700">
              <Sparkles className="h-3.5 w-3.5" />
              Now with AI-powered content generation
            </span>
          </motion.div>

          {/* Heading */}
          <motion.h1
            initial={fade.hidden}
            animate={fade.visible}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mt-8 text-5xl font-extrabold leading-[1.1] tracking-tight md:text-7xl"
            style={{ color: "var(--page-heading)" }}
          >
            Marketing automation{" "}
            <span className="bg-gradient-to-r from-violet-600 to-pink-500 bg-clip-text text-transparent">
              that works for you
            </span>
          </motion.h1>

          {/* Sub */}
          <motion.p
            initial={fade.hidden}
            animate={fade.visible}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed md:text-xl"
            style={{ color: "var(--page-text-secondary)" }}
          >
            Create, schedule, and publish AI-generated content across all your social
            accounts. Built for agencies managing multiple brands.
          </motion.p>

          {/* CTA */}
          <motion.div
            initial={fade.hidden}
            animate={fade.visible}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
          >
            <button
              onClick={() => nav("/register")}
              className="flex h-12 items-center gap-2 rounded-xl bg-[#7c3aed] px-8 text-[15px] font-semibold text-white shadow-lg shadow-violet-500/20 transition-all hover:-translate-y-0.5 hover:bg-[#6d28d9] hover:shadow-xl hover:shadow-violet-500/25 active:translate-y-0"
            >
              Get started free
              <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={() => {}}
              className="flex h-12 items-center gap-2 rounded-xl border border-gray-200 bg-white px-8 text-[15px] font-semibold transition-all hover:-translate-y-0.5 hover:border-gray-300 hover:shadow-md active:translate-y-0"
              style={{ color: "var(--page-text)" }}
            >
              <Play className="h-4 w-4" />
              Watch demo
            </button>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-5 text-sm"
            style={{ color: "var(--page-text-muted)" }}
          >
            Free 14-day trial &middot; No credit card required
          </motion.p>
        </div>

        {/* ── Dashboard Preview ── */}
        <motion.div
          initial={{ opacity: 0, y: 60 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="relative mx-auto mt-16 max-w-5xl"
        >
          <div className="rounded-2xl border border-gray-200 bg-white p-2 shadow-2xl shadow-gray-200/60">
            {/* Browser bar */}
            <div className="flex items-center gap-2 rounded-t-xl bg-gray-50 px-4 py-2.5">
              <div className="flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-red-400" />
                <div className="h-3 w-3 rounded-full bg-amber-400" />
                <div className="h-3 w-3 rounded-full bg-green-400" />
              </div>
              <div className="ml-4 flex-1 rounded-md bg-gray-200/70 px-3 py-1 text-xs text-gray-400">
                app.marketengine.ai/dashboard
              </div>
            </div>

            {/* App content */}
            <div className="flex rounded-b-xl bg-gray-50/50">
              {/* Sidebar */}
              <div className="hidden w-48 border-r border-gray-100 bg-white p-4 md:block rounded-bl-xl">
                <div className="mb-6 flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600 text-[10px] font-bold text-white">M</div>
                  <span className="text-sm font-bold" style={{ color: "var(--page-heading)" }}>MarketEngine</span>
                </div>
                {[
                  { label: "Dashboard", color: "bg-violet-500", active: true },
                  { label: "Create Post", color: "bg-pink-500", active: false },
                  { label: "Calendar", color: "bg-amber-500", active: false },
                  { label: "Platforms", color: "bg-sky-500", active: false },
                  { label: "Analytics", color: "bg-emerald-500", active: false },
                  { label: "Team", color: "bg-orange-500", active: false },
                ].map((item) => (
                  <div
                    key={item.label}
                    className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] ${
                      item.active
                        ? "bg-violet-50 font-semibold text-violet-700"
                        : "text-gray-500"
                    }`}
                  >
                    <div className={`h-2 w-2 rounded-full ${item.color}`} />
                    {item.label}
                  </div>
                ))}
              </div>

              {/* Main */}
              <div className="flex-1 p-4 md:p-6">
                {/* Stats row */}
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {[
                    { label: "Total Followers", value: "12.4K", change: "+12%", color: "text-violet-600", border: "border-l-violet-500" },
                    { label: "Engagement Rate", value: "8.2%", change: "+23%", color: "text-pink-600", border: "border-l-pink-500" },
                    { label: "Total Reach", value: "143K", change: "+18%", color: "text-sky-600", border: "border-l-sky-500" },
                    { label: "Posts This Month", value: "248", change: "+34%", color: "text-emerald-600", border: "border-l-emerald-500" },
                  ].map((stat) => (
                    <div
                      key={stat.label}
                      className={`rounded-xl border border-gray-100 ${stat.border} border-l-[3px] bg-white p-3 md:p-4`}
                    >
                      <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wide">{stat.label}</div>
                      <div className="mt-1 text-xl font-bold" style={{ color: "var(--page-heading)" }}>{stat.value}</div>
                      <div className={`mt-0.5 text-xs font-medium text-emerald-600`}>{stat.change}</div>
                    </div>
                  ))}
                </div>

                {/* Chart + Calendar row */}
                <div className="mt-4 grid gap-3 md:grid-cols-5">
                  {/* Chart */}
                  <div className="rounded-xl border border-gray-100 bg-white p-4 md:col-span-3">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="text-sm font-semibold" style={{ color: "var(--page-heading)" }}>Engagement Overview</span>
                      <div className="flex gap-3 text-[10px] font-medium text-gray-400">
                        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-violet-500" />Likes</span>
                        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-pink-500" />Shares</span>
                        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-sky-500" />Comments</span>
                      </div>
                    </div>
                    <svg viewBox="0 0 400 120" className="w-full">
                      <defs>
                        <linearGradient id="gViolet" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.3" />
                          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
                        </linearGradient>
                        <linearGradient id="gPink" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#ec4899" stopOpacity="0.2" />
                          <stop offset="100%" stopColor="#ec4899" stopOpacity="0" />
                        </linearGradient>
                      </defs>
                      <path d="M0,90 Q50,80 100,65 T200,50 T300,35 T400,20" fill="none" stroke="#7c3aed" strokeWidth="2" />
                      <path d="M0,90 Q50,80 100,65 T200,50 T300,35 T400,20 V120 H0Z" fill="url(#gViolet)" />
                      <path d="M0,100 Q50,92 100,82 T200,70 T300,60 T400,45" fill="none" stroke="#ec4899" strokeWidth="2" />
                      <path d="M0,100 Q50,92 100,82 T200,70 T300,60 T400,45 V120 H0Z" fill="url(#gPink)" />
                      <path d="M0,105 Q50,100 100,92 T200,85 T300,78 T400,65" fill="none" stroke="#0ea5e9" strokeWidth="1.5" strokeDasharray="4 3" />
                    </svg>
                  </div>

                  {/* Calendar */}
                  <div className="rounded-xl border border-gray-100 bg-white p-4 md:col-span-2">
                    <div className="mb-2 text-sm font-semibold" style={{ color: "var(--page-heading)" }}>Content Calendar</div>
                    <div className="grid grid-cols-7 gap-1 text-center text-[10px]">
                      {["S","M","T","W","T","F","S"].map((d,i) => (
                        <div key={i} className="pb-1 font-medium text-gray-400">{d}</div>
                      ))}
                      {Array.from({ length: 31 }, (_, i) => {
                        const day = i + 1;
                        const hasPost = [3,7,10,14,18,21,25,28].includes(day);
                        const colors = ["bg-violet-500","bg-pink-500","bg-amber-500","bg-sky-500","bg-emerald-500"];
                        return (
                          <div key={day} className="relative flex h-6 items-center justify-center rounded text-gray-500">
                            {day}
                            {hasPost && <span className={`absolute -bottom-0.5 h-1 w-1 rounded-full ${colors[day % 5]}`} />}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          {/* Shadow glow */}
          <div className="pointer-events-none absolute -inset-4 -z-10 rounded-3xl bg-gradient-to-b from-violet-100/40 via-transparent to-transparent blur-2xl" />
        </motion.div>
      </section>

      {/* ═══════════════════════════════════════════
          SOCIAL PROOF
      ═══════════════════════════════════════════ */}
      <section className="border-y border-gray-100 bg-gray-50/50 py-10">
        <div className="mx-auto max-w-5xl px-4 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            Trusted by 10,000+ marketers worldwide
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-12 gap-y-4 opacity-40">
            {["Stripe", "Vercel", "Linear", "Notion", "Figma", "Webflow"].map((name) => (
              <span key={name} className="text-xl font-bold tracking-tight text-gray-900">{name}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          FEATURES
      ═══════════════════════════════════════════ */}
      <section className="py-24 px-4">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
              <Zap className="h-3 w-3" /> Features
            </span>
            <h2 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl" style={{ color: "var(--page-heading)" }}>
              Everything you need to grow
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-base" style={{ color: "var(--page-text-secondary)" }}>
              One platform to create, schedule, publish, and analyze your marketing across every channel.
            </p>
          </div>

          <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: Bot, title: "AI Content Creation", desc: "Generate posts, captions, and images in seconds with GPT-4o. Your brand voice, amplified by AI.", color: "#7c3aed", bg: "bg-violet-50" },
              { icon: Calendar, title: "Smart Scheduling", desc: "AI picks the best time to post for maximum engagement. Drag, drop, and let automation handle the rest.", color: "#f59e0b", bg: "bg-amber-50" },
              { icon: Globe, title: "Multi-Platform Posting", desc: "Publish to Instagram, TikTok, LinkedIn, X, Facebook, YouTube and more from one dashboard.", color: "#3b82f6", bg: "bg-blue-50" },
              { icon: BarChart3, title: "Real-time Analytics", desc: "Track performance across all accounts with beautiful charts and AI-powered insights.", color: "#10b981", bg: "bg-emerald-50" },
              { icon: Users, title: "Agency-ready Teams", desc: "Manage multiple brands with role-based access, approval workflows, and client collaboration.", color: "#ec4899", bg: "bg-pink-50" },
              { icon: Shield, title: "Enterprise Security", desc: "SOC 2 compliant. Encrypted credentials, audit logs, and granular permissions for every account.", color: "#6366f1", bg: "bg-indigo-50" },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={fade.hidden}
                whileInView={fade.visible}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className="group rounded-2xl border border-gray-100 bg-white p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
                style={{ borderTopColor: feature.color, borderTopWidth: "2px" }}
              >
                <div
                  className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${feature.bg}`}
                >
                  <feature.icon className="h-5 w-5" style={{ color: feature.color }} />
                </div>
                <h3 className="text-base font-bold" style={{ color: "var(--page-heading)" }}>{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--page-text-secondary)" }}>{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          HOW IT WORKS
      ═══════════════════════════════════════════ */}
      <section className="bg-gray-50/80 py-24 px-4">
        <div className="mx-auto max-w-5xl">
          <div className="text-center">
            <h2 className="text-3xl font-extrabold tracking-tight md:text-4xl" style={{ color: "var(--page-heading)" }}>
              Up and running in minutes
            </h2>
            <p className="mx-auto mt-3 max-w-lg text-base" style={{ color: "var(--page-text-secondary)" }}>
              Four simple steps to automate your entire marketing workflow.
            </p>
          </div>

          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { step: "01", icon: Share2, title: "Connect Platforms", desc: "Add your social accounts and configure API keys.", color: "#7c3aed" },
              { step: "02", icon: Sparkles, title: "Create with AI", desc: "Generate content, images, and captions in one click.", color: "#ec4899" },
              { step: "03", icon: MousePointerClick, title: "Preview & Approve", desc: "Preview on mobile, tablet, and web before publishing.", color: "#f59e0b" },
              { step: "04", icon: Clock, title: "Schedule & Publish", desc: "Post now or schedule for the perfect time. Done.", color: "#10b981" },
            ].map((step, i) => (
              <motion.div
                key={step.step}
                initial={fade.hidden}
                whileInView={fade.visible}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="text-center"
              >
                <div
                  className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl"
                  style={{ backgroundColor: step.color + "10" }}
                >
                  <step.icon className="h-6 w-6" style={{ color: step.color }} />
                </div>
                <div className="mb-2 text-xs font-bold uppercase tracking-wider" style={{ color: step.color }}>
                  Step {step.step}
                </div>
                <h3 className="text-lg font-bold" style={{ color: "var(--page-heading)" }}>{step.title}</h3>
                <p className="mt-1.5 text-sm" style={{ color: "var(--page-text-secondary)" }}>{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          STATS
      ═══════════════════════════════════════════ */}
      <section className="py-20 px-4">
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 md:grid-cols-4">
          {[
            { value: "10K+", label: "Active users", color: "#7c3aed" },
            { value: "500K+", label: "Posts published", color: "#ec4899" },
            { value: "3.5x", label: "Avg. engagement boost", color: "#f59e0b" },
            { value: "4.9/5", label: "User rating", color: "#3b82f6" },
          ].map((stat) => (
            <motion.div
              key={stat.label}
              initial={fade.hidden}
              whileInView={fade.visible}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="text-center"
            >
              <div className="text-4xl font-extrabold md:text-5xl" style={{ color: stat.color }}>{stat.value}</div>
              <div className="mt-2 text-sm font-medium" style={{ color: "var(--page-text-secondary)" }}>{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          TESTIMONIALS
      ═══════════════════════════════════════════ */}
      <section className="bg-gray-50/80 py-24 px-4">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-3xl font-extrabold tracking-tight md:text-4xl" style={{ color: "var(--page-heading)" }}>
              Loved by marketers
            </h2>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                quote: "MarketEngine completely transformed how we manage social media for our clients. We save 20+ hours every week.",
                name: "Sarah Chen",
                role: "Marketing Director",
                company: "TechFlow",
                color: "#7c3aed",
              },
              {
                quote: "The AI content suggestions are incredibly accurate. Our engagement jumped 300% in the first month.",
                name: "Marcus Rivera",
                role: "Growth Lead",
                company: "ScaleUp",
                color: "#ec4899",
              },
              {
                quote: "Managing 15 client accounts used to be chaos. Now it's a breeze with multi-platform scheduling.",
                name: "Priya Patel",
                role: "Agency Owner",
                company: "BrightSocial",
                color: "#f59e0b",
              },
            ].map((t) => (
              <motion.div
                key={t.name}
                initial={fade.hidden}
                whileInView={fade.visible}
                viewport={{ once: true }}
                transition={{ duration: 0.4 }}
                className="rounded-2xl border border-gray-100 bg-white p-6"
                style={{ borderLeftWidth: "3px", borderLeftColor: t.color }}
              >
                <div className="mb-4 flex gap-0.5">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "var(--page-text)" }}>"{t.quote}"</p>
                <div className="mt-5 flex items-center gap-3">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold text-white"
                    style={{ backgroundColor: t.color }}
                  >
                    {t.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: "var(--page-heading)" }}>{t.name}</div>
                    <div className="text-xs" style={{ color: "var(--page-text-muted)" }}>{t.role}, {t.company}</div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          PRICING TEASER
      ═══════════════════════════════════════════ */}
      <section className="py-24 px-4">
        <div className="mx-auto max-w-5xl">
          <div className="text-center">
            <h2 className="text-3xl font-extrabold tracking-tight md:text-4xl" style={{ color: "var(--page-heading)" }}>
              Simple, transparent pricing
            </h2>
            <p className="mt-3 text-base" style={{ color: "var(--page-text-secondary)" }}>
              Start free. Upgrade when you're ready.
            </p>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              {
                name: "Starter",
                price: "$49",
                desc: "For solo marketers",
                features: ["1 brand", "3 platforms", "30 posts/month", "Basic analytics", "AI content generation"],
                cta: "Start free trial",
                featured: false,
              },
              {
                name: "Growth",
                price: "$149",
                desc: "For growing teams",
                features: ["3 brands", "10 platforms", "200 posts/month", "Advanced analytics", "A/B testing", "Team collaboration"],
                cta: "Start free trial",
                featured: true,
              },
              {
                name: "Agency",
                price: "$399",
                desc: "For agencies at scale",
                features: ["Unlimited brands", "All platforms", "Unlimited posts", "White-label option", "Priority support", "Custom integrations"],
                cta: "Talk to sales",
                featured: false,
              },
            ].map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-2xl border p-6 transition-all hover:-translate-y-1 hover:shadow-lg ${
                  plan.featured
                    ? "border-violet-200 bg-white shadow-md ring-1 ring-violet-100"
                    : "border-gray-100 bg-white"
                }`}
              >
                {plan.featured && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-violet-600 px-3 py-0.5 text-xs font-semibold text-white">
                    Most Popular
                  </span>
                )}
                <div className="text-sm font-semibold" style={{ color: "var(--page-text-secondary)" }}>{plan.name}</div>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="text-4xl font-extrabold" style={{ color: "var(--page-heading)" }}>{plan.price}</span>
                  <span className="text-sm" style={{ color: "var(--page-text-muted)" }}>/month</span>
                </div>
                <p className="mt-1 text-sm" style={{ color: "var(--page-text-muted)" }}>{plan.desc}</p>
                <ul className="mt-6 space-y-2.5">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm" style={{ color: "var(--page-text)" }}>
                      <Check className="h-4 w-4 text-emerald-500" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => nav("/register")}
                  className={`mt-6 w-full rounded-xl py-2.5 text-sm font-semibold transition-all ${
                    plan.featured
                      ? "bg-violet-600 text-white hover:bg-violet-700"
                      : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════
          FINAL CTA
      ═══════════════════════════════════════════ */}
      <section className="relative overflow-hidden bg-[#7c3aed] py-20 px-4">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-20 -right-20 h-80 w-80 rounded-full bg-white/5" />
          <div className="absolute -bottom-20 -left-20 h-60 w-60 rounded-full bg-white/5" />
        </div>
        <div className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-extrabold text-white md:text-4xl">
            Ready to automate your marketing?
          </h2>
          <p className="mt-4 text-lg text-white/70">
            Join 10,000+ marketers who save 20+ hours every week.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <button
              onClick={() => nav("/register")}
              className="flex h-12 items-center gap-2 rounded-xl bg-white px-8 text-[15px] font-semibold text-violet-700 transition-all hover:-translate-y-0.5 hover:shadow-lg active:translate-y-0"
            >
              Get started free
              <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={() => nav("/pricing")}
              className="flex h-12 items-center gap-2 rounded-xl border border-white/20 px-8 text-[15px] font-semibold text-white transition-all hover:-translate-y-0.5 hover:bg-white/10 active:translate-y-0"
            >
              View pricing
            </button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
