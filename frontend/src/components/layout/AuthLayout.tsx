import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { Megaphone, Star, BarChart3 } from "lucide-react";

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

const testimonial = {
  quote:
    "MarketEngine completely transformed how we manage our social media. Saves us 20+ hours a week and our engagement jumped 300%.",
  author: "Sarah Chen",
  role: "Marketing Director, TechFlow",
  rating: 5,
};

export default function AuthLayout({
  children,
  title,
  subtitle,
}: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen" style={{ background: "var(--page-bg)" }}>
      {/* ── Left branding panel ────────────────────────────────── */}
      <div className="relative hidden w-[52%] flex-col justify-between overflow-hidden p-12 lg:flex">
        {/* Vibrant gradient background */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, #7c3aed 0%, #ec4899 40%, #f97316 80%, #f472b6 100%)",
          }}
        />

        {/* Animated floating shapes */}
        <motion.div
          animate={{ y: [-10, 10, -10], x: [-5, 5, -5] }}
          transition={{ duration: 8, repeat: Infinity }}
          className="absolute top-20 right-20 w-32 h-32 rounded-full"
          style={{ background: "rgba(255,255,255,0.1)" }}
        />
        <motion.div
          animate={{ y: [10, -15, 10], x: [5, -5, 5] }}
          transition={{ duration: 10, repeat: Infinity }}
          className="absolute top-40 left-16 w-20 h-20 rounded-full"
          style={{ background: "rgba(255,255,255,0.08)" }}
        />
        <motion.div
          animate={{ y: [-8, 12, -8] }}
          transition={{ duration: 7, repeat: Infinity }}
          className="absolute bottom-40 right-32 w-24 h-24 rounded-full"
          style={{ background: "rgba(255,255,255,0.12)" }}
        />
        <motion.div
          animate={{ y: [5, -10, 5], x: [-3, 8, -3] }}
          transition={{ duration: 9, repeat: Infinity }}
          className="absolute bottom-20 left-24 w-16 h-16 rounded-full"
          style={{ background: "rgba(255,255,255,0.07)" }}
        />
        <motion.div
          animate={{ y: [-12, 8, -12] }}
          transition={{ duration: 11, repeat: Infinity }}
          className="absolute top-[60%] right-12 w-10 h-10 rounded-full"
          style={{ background: "rgba(255,255,255,0.15)" }}
        />

        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="relative z-10 flex items-center gap-3"
        >
          <div
            className="flex h-11 w-11 items-center justify-center rounded-xl shadow-lg"
            style={{ background: "rgba(255,255,255,0.2)", backdropFilter: "blur(10px)" }}
          >
            <Megaphone className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white tracking-tight">
            MarketEngine
          </span>
        </motion.div>

        {/* Center content */}
        <div className="relative z-10 space-y-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-extrabold leading-tight !text-white drop-shadow-lg" style={{ color: "#ffffff" }}>
              AI-Powered
              <br />
              Marketing Automation
            </h1>
            <p className="mt-4 max-w-md text-lg font-medium" style={{ color: "rgba(255,255,255,0.85)" }}>
              Create, schedule, and analyze your marketing content across all
              platforms with the power of AI.
            </p>
          </motion.div>

          {/* Floating mini dashboard card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="rounded-2xl p-5 max-w-sm shadow-2xl"
            style={{
              background: "rgba(255,255,255,0.15)",
              backdropFilter: "blur(20px)",
              border: "1px solid rgba(255,255,255,0.2)",
            }}
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-semibold text-white">Dashboard Preview</span>
              <BarChart3 className="w-4 h-4 text-white opacity-70" />
            </div>

            {/* Mini stat bars */}
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-white/70">Reach</span>
                  <span className="text-xs font-bold text-white">143K</span>
                </div>
                <div className="h-2 rounded-full" style={{ background: "rgba(255,255,255,0.15)" }}>
                  <div className="h-full rounded-full w-[85%]" style={{ background: "linear-gradient(90deg, #fbbf24, #f97316)" }} />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-white/70">Engagement</span>
                  <span className="text-xs font-bold text-white">75K</span>
                </div>
                <div className="h-2 rounded-full" style={{ background: "rgba(255,255,255,0.15)" }}>
                  <div className="h-full rounded-full w-[68%]" style={{ background: "linear-gradient(90deg, #a78bfa, #ec4899)" }} />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-white/70">Growth</span>
                  <span className="text-xs font-bold text-white">+24%</span>
                </div>
                <div className="h-2 rounded-full" style={{ background: "rgba(255,255,255,0.15)" }}>
                  <div className="h-full rounded-full w-[72%]" style={{ background: "linear-gradient(90deg, #34d399, #3b82f6)" }} />
                </div>
              </div>
            </div>

            {/* Mini chart dots */}
            <div className="flex items-end gap-1.5 mt-4 h-10">
              {[40, 55, 45, 70, 60, 80, 65, 90, 75, 85].map((h, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-sm"
                  style={{
                    height: `${h}%`,
                    background: `rgba(255,255,255,${0.2 + (i / 10) * 0.3})`,
                  }}
                />
              ))}
            </div>
          </motion.div>
        </div>

        {/* Testimonial */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="relative z-10 rounded-2xl p-5 max-w-md"
          style={{
            background: "rgba(255,255,255,0.1)",
            backdropFilter: "blur(12px)",
            border: "1px solid rgba(255,255,255,0.15)",
          }}
        >
          <div className="mb-2 flex gap-0.5">
            {Array.from({ length: testimonial.rating }).map((_, j) => (
              <Star
                key={j}
                className="h-4 w-4"
                style={{ fill: "#fbbf24", color: "#fbbf24" }}
              />
            ))}
          </div>
          <p className="mb-3 text-sm leading-relaxed text-white/90">
            &ldquo;{testimonial.quote}&rdquo;
          </p>
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white"
              style={{ background: "rgba(255,255,255,0.2)" }}
            >
              {testimonial.author.charAt(0)}
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{testimonial.author}</p>
              <p className="text-xs text-white/60">{testimonial.role}</p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* ── Right form panel ───────────────────────────────────── */}
      <div
        className="relative flex flex-1 flex-col items-center justify-center px-6 py-12"
        style={{ background: "var(--page-bg)" }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Mobile logo */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ background: "var(--gradient-primary)" }}
            >
              <Megaphone className="h-5 w-5 text-white" style={{ color: "#fff" }} />
            </div>
            <span
              className="text-xl font-bold"
              style={{ background: "var(--gradient-primary)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}
            >
              MarketEngine
            </span>
          </div>

          {title && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>{title}</h2>
              {subtitle && (
                <p className="mt-2 text-sm" style={{ color: "var(--page-text-secondary)" }}>{subtitle}</p>
              )}
            </div>
          )}

          {children}
        </motion.div>
      </div>
    </div>
  );
}
