import { useNavigate } from "react-router-dom";
import { motion, type Variants } from "framer-motion";
import {
  Lightbulb,
  Eye,
  Heart,
  ShieldCheck,
  Mail,
  ArrowRight,
  Sparkles,
  Target,
  Globe,
} from "lucide-react";
import { Twitter, Linkedin, Github } from "@/components/shared/SocialIcons";
import PublicLayout from "@/components/layout/PublicLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Animation helpers                                                  */
/* ------------------------------------------------------------------ */

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 40 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: i * 0.1, ease: "easeOut" },
  }),
};

const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } },
};

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const team = [
  {
    name: "Alex Chen",
    role: "Founder & CEO",
    bio: "Former Head of Product at a leading social media management platform. 10+ years in marketing technology.",
    gradient: "from-purple-500 to-violet-600",
  },
  {
    name: "Priya Sharma",
    role: "CTO",
    bio: "AI/ML researcher turned entrepreneur. Previously built recommendation systems at a top-tier tech company.",
    gradient: "from-blue-500 to-cyan-500",
  },
  {
    name: "Jordan Taylor",
    role: "Head of Design",
    bio: "Award-winning product designer passionate about creating intuitive, delightful user experiences.",
    gradient: "from-pink-500 to-rose-500",
  },
  {
    name: "Sam Okafor",
    role: "Head of AI",
    bio: "PhD in Natural Language Processing. Leads the team building our content generation and strategy engines.",
    gradient: "from-emerald-500 to-green-500",
  },
];

const values = [
  {
    icon: Lightbulb,
    title: "Innovation",
    description:
      "We push the boundaries of what AI can do for marketing. Every feature is designed to be smarter, faster, and more effective than the status quo.",
    color: "from-amber-500 to-orange-500",
  },
  {
    icon: Eye,
    title: "Transparency",
    description:
      "No hidden fees, no black-box algorithms. We believe in clear communication with our customers and open, honest business practices.",
    color: "from-blue-500 to-cyan-500",
  },
  {
    icon: Heart,
    title: "Customer First",
    description:
      "Every decision we make starts with the question: does this help our customers succeed? Your growth is our north star.",
    color: "from-pink-500 to-rose-500",
  },
  {
    icon: ShieldCheck,
    title: "AI Ethics",
    description:
      "We build responsible AI. Our models are designed to be helpful, honest, and safe. We never generate misleading or harmful content.",
    color: "from-emerald-500 to-green-500",
  },
];

const milestones = [
  { year: "2023", title: "Founded", description: "MarketEngine was born from a simple idea: marketing should be intelligent." },
  { year: "2024", title: "Public Launch", description: "Launched to the public with AI content generation and multi-platform publishing." },
  { year: "2025", title: "2,000+ Users", description: "Reached 2,000 active businesses and 500K+ posts published through our platform." },
  { year: "2026", title: "AI Strategy Engine", description: "Released our groundbreaking AI Strategy Engine for fully automated marketing plans." },
];

/* ------------------------------------------------------------------ */
/*  About page                                                         */
/* ------------------------------------------------------------------ */

export default function AboutPage() {
  const navigate = useNavigate();

  return (
    <PublicLayout>
      {/* ============================================================ */}
      {/*  HERO                                                        */}
      {/* ============================================================ */}
      <section className="relative overflow-hidden pt-32 pb-20">
        {/* Gradient mesh */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-1/4 left-1/3 h-[500px] w-[500px] rounded-full bg-purple-700/20 blur-[160px]" />
          <div className="absolute -top-1/4 right-1/3 h-[400px] w-[400px] rounded-full bg-blue-700/15 blur-[140px]" />
        </div>

        <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <Badge variant="info" className="mb-6 px-4 py-1.5 text-sm">
              <Sparkles className="mr-1.5 inline h-3.5 w-3.5" />
              Our Story
            </Badge>
            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl">
              About{" "}
              <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                MarketEngine
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-400">
              We're on a mission to democratize marketing intelligence. Every
              business -- from solo founders to enterprise teams -- deserves
              access to AI-powered strategies that drive real growth.
            </p>
          </motion.div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  OUR MISSION                                                 */}
      {/* ============================================================ */}
      <section className="relative py-24">
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, x: -40 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <Badge variant="info" className="mb-4">
                <Target className="mr-1.5 inline h-3 w-3" />
                Our Mission
              </Badge>
              <h2 className="text-3xl font-bold text-white sm:text-4xl">
                Making World-Class Marketing{" "}
                <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                  Accessible to Everyone
                </span>
              </h2>
              <p className="mt-4 text-base leading-relaxed text-slate-400">
                Great marketing shouldn't require a massive team or a six-figure
                budget. We built MarketEngine to level the playing field --
                giving every business the same AI-powered tools that the biggest
                brands use.
              </p>
              <p className="mt-4 text-base leading-relaxed text-slate-400">
                Our platform combines cutting-edge natural language processing,
                audience intelligence, and cross-platform automation into one
                seamless experience. The result? Marketing that's smarter,
                faster, and more effective than ever before.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 40 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="grid grid-cols-2 gap-4"
            >
              {[
                { label: "Founded", value: "2023" },
                { label: "Team Members", value: "35+" },
                { label: "Countries", value: "12" },
                { label: "Posts Published", value: "500K+" },
              ].map((stat) => (
                <GlassCard key={stat.label} padding="lg" hover>
                  <p className="text-2xl font-bold text-white sm:text-3xl">
                    {stat.value}
                  </p>
                  <p className="mt-1 text-sm text-slate-400">{stat.label}</p>
                </GlassCard>
              ))}
            </motion.div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  TIMELINE                                                    */}
      {/* ============================================================ */}
      <section className="relative py-24">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-1/2 h-[400px] w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-purple-700/10 blur-[140px]" />
        </div>

        <div className="relative mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <div className="mb-16 text-center">
            <Badge variant="info" className="mb-4">
              <Globe className="mr-1.5 inline h-3 w-3" />
              Our Journey
            </Badge>
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              The MarketEngine Story
            </h2>
          </div>

          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-purple-600/50 via-blue-600/50 to-transparent sm:left-1/2" />

            {milestones.map((m, i) => (
              <motion.div
                key={m.year}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className={cn(
                  "relative mb-12 flex items-start gap-6 last:mb-0",
                  "sm:gap-0",
                  i % 2 === 0 ? "sm:flex-row" : "sm:flex-row-reverse"
                )}
              >
                {/* Dot */}
                <div className="absolute left-6 top-2 z-10 h-3 w-3 -translate-x-1/2 rounded-full border-2 border-purple-500 bg-slate-950 sm:left-1/2" />

                {/* Content */}
                <div className={cn("ml-12 sm:ml-0 sm:w-1/2", i % 2 === 0 ? "sm:pr-12 sm:text-right" : "sm:pl-12")}>
                  <span className="text-sm font-bold text-purple-400">
                    {m.year}
                  </span>
                  <h3 className="mt-1 text-lg font-semibold text-white">
                    {m.title}
                  </h3>
                  <p className="mt-1 text-sm text-slate-400">
                    {m.description}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  TEAM                                                        */}
      {/* ============================================================ */}
      <section className="relative py-24">
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-16 text-center">
            <Badge variant="info" className="mb-4">
              Our Team
            </Badge>
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Meet the People Behind{" "}
              <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                MarketEngine
              </span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
              A passionate team of marketers, engineers, and AI researchers
              building the future of marketing.
            </p>
          </div>

          <motion.div
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4"
          >
            {team.map((member, i) => (
              <motion.div key={member.name} variants={fadeUp} custom={i}>
                <GlassCard hover padding="lg" className="text-center">
                  {/* Gradient avatar */}
                  <div
                    className={cn(
                      "mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br text-2xl font-bold text-white",
                      member.gradient
                    )}
                  >
                    {member.name
                      .split(" ")
                      .map((w) => w[0])
                      .join("")}
                  </div>
                  <h3 className="text-base font-semibold text-white">
                    {member.name}
                  </h3>
                  <p className="mt-0.5 text-sm font-medium text-purple-400">
                    {member.role}
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-slate-400">
                    {member.bio}
                  </p>

                  {/* Social links */}
                  <div className="mt-4 flex items-center justify-center gap-3">
                    <a
                      href="#"
                      className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-white/5 hover:text-white"
                    >
                      <Twitter className="h-4 w-4" />
                    </a>
                    <a
                      href="#"
                      className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-white/5 hover:text-white"
                    >
                      <Linkedin className="h-4 w-4" />
                    </a>
                  </div>
                </GlassCard>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  VALUES                                                      */}
      {/* ============================================================ */}
      <section className="relative py-24">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-[500px] w-[500px] -translate-x-1/2 rounded-full bg-blue-700/10 blur-[160px]" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-16 text-center">
            <Badge variant="info" className="mb-4">
              Our Values
            </Badge>
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              What We Stand For
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
              The principles that guide every decision we make.
            </p>
          </div>

          <motion.div
            variants={staggerContainer}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4"
          >
            {values.map((value, i) => (
              <motion.div key={value.title} variants={fadeUp} custom={i}>
                <GlassCard hover padding="lg" className="h-full">
                  <div
                    className={cn(
                      "mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br",
                      value.color
                    )}
                  >
                    <value.icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="mb-2 text-lg font-semibold text-white">
                    {value.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-slate-400">
                    {value.description}
                  </p>
                </GlassCard>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  CONTACT                                                     */}
      {/* ============================================================ */}
      <section className="relative py-24">
        <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Get in Touch
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-lg text-slate-400">
              Have questions, feedback, or partnership ideas? We would love to
              hear from you.
            </p>

            {/* Email */}
            <div className="mt-8 flex items-center justify-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/5 border border-white/10">
                <Mail className="h-5 w-5 text-purple-400" />
              </div>
              <a
                href="mailto:hello@marketengine.ai"
                className="text-lg font-medium text-white transition-colors hover:text-purple-400"
              >
                hello@marketengine.ai
              </a>
            </div>

            {/* Social links */}
            <div className="mt-8 flex items-center justify-center gap-4">
              {[
                { icon: Twitter, label: "Twitter", href: "#" },
                { icon: Linkedin, label: "LinkedIn", href: "#" },
                { icon: Github, label: "GitHub", href: "#" },
              ].map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-slate-400 transition-all hover:border-white/20 hover:bg-white/10 hover:text-white"
                  aria-label={social.label}
                >
                  <social.icon className="h-5 w-5" />
                </a>
              ))}
            </div>

            <div className="mt-12">
              <Button
                size="xl"
                variant="primary"
                icon={<ArrowRight className="h-5 w-5" />}
                iconPosition="right"
                onClick={() => navigate("/register")}
              >
                Join MarketEngine Today
              </Button>
            </div>
          </motion.div>
        </div>
      </section>
    </PublicLayout>
  );
}
