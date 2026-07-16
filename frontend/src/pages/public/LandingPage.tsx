import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  motion,
  MotionConfig,
  useScroll,
  useSpring,
  useMotionValue,
  useTransform,
  useReducedMotion,
  type Variants,
} from "framer-motion";
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
  TrendingUp,
} from "lucide-react";
import PublicLayout from "@/components/layout/PublicLayout";
import { EASE, CountUp } from "@/components/shared/motion";

const fade: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
};

const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};

/* Container that only orchestrates its children's stagger (no self-reveal),
   used so the hero heading can reveal word-by-word. */
const wordContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.15 } },
};

const wordReveal: Variants = {
  hidden: { opacity: 0, y: "0.5em", filter: "blur(10px)" },
  visible: {
    opacity: 1,
    y: "0em",
    filter: "blur(0px)",
    transition: { duration: 0.7, ease: EASE },
  },
};

/* Reveal a heading one word at a time. `gradient` words get the animated
   brand gradient; every word keeps the blur-in rhythm. */
function AnimatedHeading({
  words,
}: {
  words: { text: string; gradient?: boolean }[];
}) {
  return (
    <motion.h1
      variants={wordContainer}
      className="mt-8 text-5xl font-extrabold leading-[1.1] tracking-tight md:text-7xl"
      style={{ color: "var(--page-heading)" }}
    >
      {words.map((w, i) => (
        <motion.span
          key={i}
          variants={wordReveal}
          className="inline-block will-change-transform"
          style={{ marginRight: "0.25em" }}
        >
          {w.gradient ? (
            <span
              className="animate-gradient-shift bg-gradient-to-r from-violet-600 via-fuchsia-500 to-sky-500 bg-clip-text text-transparent"
              style={{ backgroundSize: "200% auto" }}
            >
              {w.text}
            </span>
          ) : (
            w.text
          )}
        </motion.span>
      ))}
    </motion.h1>
  );
}

/* Primary CTA with a diagonal light sheen that sweeps across on hover. */
function ShineButton({
  children,
  onClick,
  variant = "primary",
  className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "light";
  className?: string;
}) {
  const base =
    "group relative flex h-12 cursor-pointer items-center justify-center gap-2 overflow-hidden rounded-xl px-8 text-[15px] font-semibold backdrop-blur";
  const styles =
    variant === "primary"
      ? "shadow-lg shadow-violet-500/30 hover:shadow-xl hover:shadow-violet-500/40"
      : variant === "light"
      ? "shadow-lg hover:shadow-xl"
      : "hover:shadow-md";

  // Colors are set inline (not via text-white / bg-* classes) so they are immune
  // to the global class→token remap, which would otherwise flip on-purple text
  // to a dark heading color in light mode.
  const colorStyle: React.CSSProperties =
    variant === "primary"
      ? { backgroundColor: "#7c3aed", color: "#ffffff" }
      : variant === "light"
      ? { backgroundColor: "#ffffff", color: "#7c3aed" }
      : {
          backgroundColor: "var(--surface-bg)",
          color: "var(--page-text)",
          border: "1px solid var(--surface-border)",
        };

  return (
    <motion.button
      onClick={onClick}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.2, ease: EASE }}
      className={`${base} ${styles} ${className}`}
      style={colorStyle}
    >
      {/* sheen */}
      <span className="pointer-events-none absolute inset-0 -translate-x-[150%] skew-x-[-20deg] bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-[150%]" />
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </motion.button>
  );
}

/* Card that renders a soft radial spotlight following the cursor. */
function SpotlightCard({
  color,
  children,
  className = "",
  style,
}: {
  color: string;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [pos, setPos] = useState({ x: -300, y: -300 });
  const [active, setActive] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  return (
    <motion.div
      ref={ref}
      variants={fade}
      whileHover={{ y: -6 }}
      transition={{ duration: 0.25, ease: EASE }}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (r) setPos({ x: e.clientX - r.left, y: e.clientY - r.top });
      }}
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => setActive(false)}
      className={`group relative overflow-hidden ${className}`}
      style={style}
    >
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          opacity: active ? 1 : 0,
          background: `radial-gradient(240px circle at ${pos.x}px ${pos.y}px, ${color}20, transparent 65%)`,
        }}
      />
      {children}
    </motion.div>
  );
}

/* Wraps the hero dashboard preview and tilts it toward the cursor in 3D. */
function TiltPreview({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const rotateX = useSpring(useTransform(py, [0, 1], [7, -7]), {
    stiffness: 150,
    damping: 18,
  });
  const rotateY = useSpring(useTransform(px, [0, 1], [-7, 7]), {
    stiffness: 150,
    damping: 18,
  });

  if (reduced) return <>{children}</>;

  return (
    <motion.div
      ref={ref}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        px.set((e.clientX - r.left) / r.width);
        py.set((e.clientY - r.top) / r.height);
      }}
      onMouseLeave={() => {
        px.set(0.5);
        py.set(0.5);
      }}
      style={{
        rotateX,
        rotateY,
        transformPerspective: 1400,
        transformStyle: "preserve-3d",
      }}
    >
      {children}
    </motion.div>
  );
}

export default function LandingPage() {
  const nav = useNavigate();
  const { scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    restDelta: 0.001,
  });

  return (
    <MotionConfig reducedMotion="user">
      <PublicLayout>
        {/* Scroll progress bar */}
        <motion.div
          className="fixed inset-x-0 top-0 z-[60] h-[3px] origin-left bg-gradient-to-r from-violet-600 via-fuchsia-500 to-sky-500"
          style={{ scaleX: progress }}
        />

        {/* ═══════════════════════════════════════════
            HERO
        ═══════════════════════════════════════════ */}
        <section className="relative overflow-hidden px-4 pt-20 pb-24 md:pt-32 md:pb-36">
          {/* Animated ambient aurora */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="animate-aurora absolute -top-40 -right-32 h-[620px] w-[620px] rounded-full bg-violet-400/40 blur-3xl" />
            <div className="animate-aurora absolute -bottom-48 -left-40 h-[560px] w-[560px] rounded-full bg-fuchsia-400/30 blur-3xl [animation-delay:-7s]" />
            <div className="animate-aurora absolute top-20 left-1/3 h-[440px] w-[440px] rounded-full bg-sky-400/30 blur-3xl [animation-delay:-13s]" />
          </div>
          {/* Faint grid texture */}
          <div className="hero-grid pointer-events-none absolute inset-0" />

          <motion.div
            variants={stagger}
            initial="hidden"
            animate="visible"
            className="relative mx-auto max-w-4xl text-center"
          >
            {/* Pill badge */}
            <motion.div variants={fade}>
              <span className="group inline-flex items-center gap-2 rounded-full border border-violet-200/80 bg-white/70 px-4 py-1.5 text-sm font-medium text-violet-700 shadow-sm backdrop-blur transition-colors hover:border-violet-300">
                <span className="pulse-ring flex h-2 w-2 rounded-full bg-violet-500" />
                Now with AI-powered content generation
                <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5" />
              </span>
            </motion.div>

            {/* Heading — word-by-word blur reveal */}
            <AnimatedHeading
              words={[
                { text: "Marketing" },
                { text: "automation" },
                { text: "that", gradient: true },
                { text: "works", gradient: true },
                { text: "for", gradient: true },
                { text: "you", gradient: true },
              ]}
            />

            {/* Sub */}
            <motion.p
              variants={fade}
              className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed md:text-xl"
              style={{ color: "var(--page-text-secondary)" }}
            >
              Create, schedule, and publish AI-generated content across all your social
              accounts. Built for agencies managing multiple brands.
            </motion.p>

            {/* CTA */}
            <motion.div
              variants={fade}
              className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
            >
              <ShineButton onClick={() => nav("/register")} variant="primary">
                Get started free
                <ArrowRight className="h-4 w-4" />
              </ShineButton>
              <ShineButton onClick={() => {}} variant="secondary">
                <Play className="h-4 w-4" />
                Watch demo
              </ShineButton>
            </motion.div>

            <motion.p
              variants={fade}
              className="mt-5 text-sm"
              style={{ color: "var(--page-text-muted)" }}
            >
              Free 14-day trial &middot; No credit card required
            </motion.p>
          </motion.div>

          {/* ── Dashboard Preview ── */}
          <motion.div
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.4, ease: EASE }}
            className="relative mx-auto mt-16 max-w-5xl"
          >
            {/* Floating glass badges */}
            <motion.div
              className="animate-float absolute -left-4 top-24 z-20 hidden rounded-2xl border border-white/60 bg-white/80 px-4 py-3 shadow-xl shadow-violet-500/10 backdrop-blur-md lg:block"
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 1, ease: EASE }}
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50">
                  <TrendingUp className="h-4 w-4 text-emerald-600" />
                </div>
                <div className="text-left">
                  <div className="text-sm font-bold" style={{ color: "var(--page-heading)" }}>+34%</div>
                  <div className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>engagement</div>
                </div>
              </div>
            </motion.div>

            <motion.div
              className="animate-float absolute -right-4 top-44 z-20 hidden rounded-2xl border border-white/60 bg-white/80 px-4 py-3 shadow-xl shadow-fuchsia-500/10 backdrop-blur-md lg:block [animation-delay:-3s]"
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 1.2, ease: EASE }}
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50">
                  <Bot className="h-4 w-4 text-violet-600" />
                </div>
                <div className="text-left">
                  <div className="text-sm font-bold" style={{ color: "var(--page-heading)" }}>AI draft ready</div>
                  <div className="text-[11px]" style={{ color: "var(--page-text-muted)" }}>in 1.2s</div>
                </div>
              </div>
            </motion.div>

            {/* Animated conic glow ring behind the preview */}
            <div className="pointer-events-none absolute -inset-6 -z-10 rounded-[2rem] opacity-60 blur-2xl [animation:spin_14s_linear_infinite] [background:conic-gradient(from_90deg,rgba(124,58,237,0.35),rgba(236,72,153,0.25),rgba(14,165,233,0.3),rgba(124,58,237,0.35))]" />

            <TiltPreview>
              <div className="rounded-2xl border border-gray-200 bg-white p-2 shadow-2xl shadow-gray-300/40">
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
                      <img src="/marketengine_logo.png" alt="" className="h-7 w-7 rounded-lg object-cover" />
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
                        { label: "Total Followers", value: "12.4K", change: "+12%", border: "border-l-violet-500" },
                        { label: "Engagement Rate", value: "8.2%", change: "+23%", border: "border-l-pink-500" },
                        { label: "Total Reach", value: "143K", change: "+18%", border: "border-l-sky-500" },
                        { label: "Posts This Month", value: "248", change: "+34%", border: "border-l-emerald-500" },
                      ].map((stat) => (
                        <div
                          key={stat.label}
                          className={`rounded-xl border border-gray-100 ${stat.border} border-l-[3px] bg-white p-3 md:p-4`}
                        >
                          <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wide">{stat.label}</div>
                          <div className="mt-1 text-xl font-bold" style={{ color: "var(--page-heading)" }}>{stat.value}</div>
                          <div className="mt-0.5 text-xs font-medium text-emerald-600">{stat.change}</div>
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
                          <motion.path
                            d="M0,90 Q50,80 100,65 T200,50 T300,35 T400,20"
                            fill="none" stroke="#7c3aed" strokeWidth="2"
                            initial={{ pathLength: 0 }}
                            whileInView={{ pathLength: 1 }}
                            viewport={{ once: true }}
                            transition={{ duration: 1.4, ease: EASE }}
                          />
                          <path d="M0,90 Q50,80 100,65 T200,50 T300,35 T400,20 V120 H0Z" fill="url(#gViolet)" />
                          <motion.path
                            d="M0,100 Q50,92 100,82 T200,70 T300,60 T400,45"
                            fill="none" stroke="#ec4899" strokeWidth="2"
                            initial={{ pathLength: 0 }}
                            whileInView={{ pathLength: 1 }}
                            viewport={{ once: true }}
                            transition={{ duration: 1.4, delay: 0.15, ease: EASE }}
                          />
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
            </TiltPreview>
            {/* Shadow glow */}
            <div className="pointer-events-none absolute -inset-4 -z-10 rounded-3xl bg-gradient-to-b from-violet-200/50 via-transparent to-transparent blur-2xl" />
          </motion.div>
        </section>

        {/* ═══════════════════════════════════════════
            SOCIAL PROOF — infinite marquee
        ═══════════════════════════════════════════ */}
        <section className="border-y border-gray-100 bg-gray-50/50 py-10">
          <div className="mx-auto max-w-5xl px-4 text-center">
            <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
              Trusted by 10,000+ marketers worldwide
            </p>
            <div className="marquee-mask relative mt-6 overflow-hidden">
              <div className="animate-marquee flex w-max items-center gap-12">
                {[...Array(2)].flatMap((_, dup) =>
                  ["Stripe", "Vercel", "Linear", "Notion", "Figma", "Webflow", "Slack", "Shopify"].map((name) => (
                    <span
                      key={`${dup}-${name}`}
                      className="shrink-0 text-xl font-bold tracking-tight text-gray-400 grayscale transition-all duration-300 hover:text-gray-900 hover:grayscale-0"
                    >
                      {name}
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════
            FEATURES
        ═══════════════════════════════════════════ */}
        <section id="features" className="py-24 px-4">
          <div className="mx-auto max-w-6xl">
            <motion.div
              variants={fade}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              className="text-center"
            >
              <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
                <Zap className="h-3 w-3" /> Features
              </span>
              <h2 className="mt-4 text-3xl font-extrabold tracking-tight md:text-4xl" style={{ color: "var(--page-heading)" }}>
                Everything you need to grow
              </h2>
              <p className="mx-auto mt-3 max-w-lg text-base" style={{ color: "var(--page-text-secondary)" }}>
                One platform to create, schedule, publish, and analyze your marketing across every channel.
              </p>
            </motion.div>

            <motion.div
              variants={stagger}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-80px" }}
              className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
            >
              {[
                { icon: Bot, title: "AI Content Creation", desc: "Generate posts, captions, and images in seconds with GPT-4o. Your brand voice, amplified by AI.", color: "#7c3aed", bg: "bg-violet-50" },
                { icon: Calendar, title: "Smart Scheduling", desc: "AI picks the best time to post for maximum engagement. Drag, drop, and let automation handle the rest.", color: "#f59e0b", bg: "bg-amber-50" },
                { icon: Globe, title: "Multi-Platform Posting", desc: "Publish to Instagram, TikTok, LinkedIn, X, Facebook, YouTube and more from one dashboard.", color: "#3b82f6", bg: "bg-blue-50" },
                { icon: BarChart3, title: "Real-time Analytics", desc: "Track performance across all accounts with beautiful charts and AI-powered insights.", color: "#10b981", bg: "bg-emerald-50" },
                { icon: Users, title: "Agency-ready Teams", desc: "Manage multiple brands with role-based access, approval workflows, and client collaboration.", color: "#ec4899", bg: "bg-pink-50" },
                { icon: Shield, title: "Enterprise Security", desc: "SOC 2 compliant. Encrypted credentials, audit logs, and granular permissions for every account.", color: "#6366f1", bg: "bg-indigo-50" },
              ].map((feature) => (
                <SpotlightCard
                  key={feature.title}
                  color={feature.color}
                  className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition-shadow duration-300 hover:shadow-xl"
                  style={{ borderTopColor: feature.color, borderTopWidth: "2px" }}
                >
                  <div
                    className={`relative mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${feature.bg} transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6`}
                  >
                    <feature.icon className="h-5 w-5" style={{ color: feature.color }} />
                  </div>
                  <h3 className="relative text-base font-bold" style={{ color: "var(--page-heading)" }}>{feature.title}</h3>
                  <p className="relative mt-2 text-sm leading-relaxed" style={{ color: "var(--page-text-secondary)" }}>{feature.desc}</p>
                </SpotlightCard>
              ))}
            </motion.div>
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

            <div className="relative mt-16">
              {/* connecting line on desktop */}
              <div className="pointer-events-none absolute left-0 right-0 top-7 hidden h-px bg-gradient-to-r from-transparent via-violet-200 to-transparent lg:block" />
              <motion.div
                variants={stagger}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4"
              >
                {[
                  { step: "01", icon: Share2, title: "Connect Platforms", desc: "Add your social accounts and configure API keys.", color: "#7c3aed" },
                  { step: "02", icon: Sparkles, title: "Create with AI", desc: "Generate content, images, and captions in one click.", color: "#ec4899" },
                  { step: "03", icon: MousePointerClick, title: "Preview & Approve", desc: "Preview on mobile, tablet, and web before publishing.", color: "#f59e0b" },
                  { step: "04", icon: Clock, title: "Schedule & Publish", desc: "Post now or schedule for the perfect time. Done.", color: "#10b981" },
                ].map((step) => (
                  <motion.div
                    key={step.step}
                    variants={fade}
                    className="group relative text-center"
                  >
                    <motion.div
                      whileHover={{ scale: 1.08, rotate: 3 }}
                      transition={{ duration: 0.25, ease: EASE }}
                      className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-md ring-1 ring-gray-100"
                      style={{ color: step.color }}
                    >
                      <step.icon className="h-6 w-6" />
                    </motion.div>
                    <div className="mb-2 text-xs font-bold uppercase tracking-wider" style={{ color: step.color }}>
                      Step {step.step}
                    </div>
                    <h3 className="text-lg font-bold" style={{ color: "var(--page-heading)" }}>{step.title}</h3>
                    <p className="mt-1.5 text-sm" style={{ color: "var(--page-text-secondary)" }}>{step.desc}</p>
                  </motion.div>
                ))}
              </motion.div>
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════
            STATS — count up
        ═══════════════════════════════════════════ */}
        <section className="py-20 px-4">
          <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 md:grid-cols-4">
            {[
              { to: 10, decimals: 0, suffix: "K+", label: "Active users", color: "#7c3aed" },
              { to: 500, decimals: 0, suffix: "K+", label: "Posts published", color: "#ec4899" },
              { to: 3.5, decimals: 1, suffix: "x", label: "Avg. engagement boost", color: "#f59e0b" },
              { to: 4.9, decimals: 1, suffix: "/5", label: "User rating", color: "#3b82f6" },
            ].map((stat) => (
              <motion.div
                key={stat.label}
                variants={fade}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="text-center"
              >
                <CountUp
                  to={stat.to}
                  decimals={stat.decimals}
                  suffix={stat.suffix}
                  className="text-4xl font-extrabold md:text-5xl"
                  style={{ color: stat.color }}
                />
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

            <motion.div
              variants={stagger}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-80px" }}
              className="mt-12 grid gap-6 md:grid-cols-3"
            >
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
                  variants={fade}
                  whileHover={{ y: -4 }}
                  transition={{ duration: 0.25, ease: EASE }}
                  className="relative overflow-hidden rounded-2xl border border-gray-100 bg-white p-6 shadow-sm transition-shadow duration-300 hover:shadow-lg"
                  style={{ borderLeftWidth: "3px", borderLeftColor: t.color }}
                >
                  <span
                    className="pointer-events-none absolute -right-2 -top-4 select-none font-serif text-8xl leading-none opacity-10"
                    style={{ color: t.color }}
                  >
                    &rdquo;
                  </span>
                  <div className="mb-4 flex gap-0.5">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className="h-4 w-4 fill-amber-400 text-amber-400" />
                    ))}
                  </div>
                  <p className="relative text-sm leading-relaxed" style={{ color: "var(--page-text)" }}>"{t.quote}"</p>
                  <div className="mt-5 flex items-center gap-3">
                    <div
                      className="flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold text-white ring-2 ring-white"
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
            </motion.div>
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

            <motion.div
              variants={stagger}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-60px" }}
              className="mt-12 grid items-stretch gap-6 md:grid-cols-3"
            >
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
                <motion.div
                  key={plan.name}
                  variants={fade}
                  whileHover={{ y: -6 }}
                  transition={{ duration: 0.25, ease: EASE }}
                  className={`relative ${plan.featured ? "md:-mt-3 md:mb-3" : ""}`}
                >
                  {/* Animated gradient ring for the featured plan */}
                  {plan.featured && (
                    <span
                      aria-hidden
                      className="pointer-events-none absolute -inset-[1.5px] rounded-[17px] opacity-90 [animation:spin_6s_linear_infinite] [background:conic-gradient(from_180deg,#7c3aed,#ec4899,#38bdf8,#7c3aed)]"
                    />
                  )}
                  <div
                    className={`relative h-full rounded-2xl border p-6 shadow-sm transition-shadow duration-300 hover:shadow-xl ${
                      plan.featured
                        ? "border-transparent bg-white shadow-lg shadow-violet-500/10"
                        : "border-gray-100 bg-white"
                    }`}
                  >
                    {plan.featured && (
                      <span className="absolute -top-3 left-1/2 z-10 -translate-x-1/2 rounded-full bg-violet-600 px-3 py-0.5 text-xs font-semibold text-white shadow-md shadow-violet-500/30">
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
                          <Check className="h-4 w-4 shrink-0 text-emerald-500" />
                          {f}
                        </li>
                      ))}
                    </ul>
                    <button
                      onClick={() => nav("/register")}
                      className={`mt-6 w-full cursor-pointer rounded-xl py-2.5 text-sm font-semibold transition-all ${
                        plan.featured
                          ? "bg-violet-600 text-white hover:bg-violet-700"
                          : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {plan.cta}
                    </button>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════
            FINAL CTA
        ═══════════════════════════════════════════ */}
        <section className="relative overflow-hidden bg-[#7c3aed] py-20 px-4">
          <div className="pointer-events-none absolute inset-0">
            <div className="animate-aurora absolute -top-20 -right-20 h-80 w-80 rounded-full bg-white/10" />
            <div className="animate-aurora absolute -bottom-20 -left-20 h-60 w-60 rounded-full bg-white/10 [animation-delay:-9s]" />
          </div>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: EASE }}
            className="relative mx-auto max-w-2xl text-center"
          >
            <h2 className="text-3xl font-extrabold md:text-4xl" style={{ color: "#ffffff" }}>
              Ready to automate your marketing?
            </h2>
            <p className="mt-4 text-lg" style={{ color: "rgba(255,255,255,0.72)" }}>
              Join 10,000+ marketers who save 20+ hours every week.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <ShineButton onClick={() => nav("/register")} variant="light">
                Get started free
                <ArrowRight className="h-4 w-4" />
              </ShineButton>
              <motion.button
                onClick={() => nav("/pricing")}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.97 }}
                transition={{ duration: 0.2, ease: EASE }}
                className="flex h-12 cursor-pointer items-center gap-2 rounded-xl px-8 text-[15px] font-semibold hover:bg-white/10"
                style={{ color: "#ffffff", border: "1px solid rgba(255,255,255,0.25)" }}
              >
                View pricing
              </motion.button>
            </div>
          </motion.div>
        </section>
      </PublicLayout>
    </MotionConfig>
  );
}
