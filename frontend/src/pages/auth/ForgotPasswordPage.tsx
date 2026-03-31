import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, ArrowLeft, CheckCircle2 } from "lucide-react";
import AuthLayout from "@/components/layout/AuthLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import api from "@/lib/api";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSent, setIsSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Enter a valid email address");
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      await api.post("/auth/forgot-password", { email });
      setIsSent(true);
    } catch {
      // Always show success to avoid email enumeration
      setIsSent(true);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthLayout title="" subtitle="">
      <GlassCard className="w-full !bg-white/[0.03] border-white/[0.06]" padding="lg">
        <AnimatePresence mode="wait">
          {!isSent ? (
            <motion.div
              key="form"
              initial="hidden"
              animate="visible"
              exit={{ opacity: 0, y: -10 }}
              variants={{
                hidden: { opacity: 0 },
                visible: {
                  opacity: 1,
                  transition: { staggerChildren: 0.08, delayChildren: 0.1 },
                },
              }}
            >
              <motion.form onSubmit={handleSubmit} className="space-y-6">
                {/* Icon */}
                <motion.div variants={fadeUp} className="flex justify-center">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center">
                    <Lock className="w-7 h-7 text-purple-400" />
                  </div>
                </motion.div>

                {/* Heading */}
                <motion.div variants={fadeUp} className="text-center">
                  <h1 className="text-2xl font-bold text-white">Reset Password</h1>
                  <p className="mt-2 text-sm text-slate-400">
                    Enter your email and we'll send you a reset link
                  </p>
                </motion.div>

                {/* Email */}
                <motion.div variants={fadeUp}>
                  <Input
                    label="Email address"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    icon={<Mail className="w-4 h-4" />}
                    error={error}
                    placeholder="you@company.com"
                    autoComplete="email"
                  />
                </motion.div>

                {/* Submit */}
                <motion.div variants={fadeUp}>
                  <Button type="submit" fullWidth size="lg" loading={isLoading}>
                    Send Reset Link
                  </Button>
                </motion.div>

                {/* Back to login */}
                <motion.div variants={fadeUp} className="text-center">
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-purple-400 transition-colors"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Login
                  </Link>
                </motion.div>
              </motion.form>
            </motion.div>
          ) : (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="space-y-6 text-center py-4"
            >
              {/* Success icon */}
              <div className="flex justify-center">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.15, type: "spring", stiffness: 200, damping: 12 }}
                  className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center"
                >
                  <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                </motion.div>
              </div>

              <div>
                <h2 className="text-2xl font-bold text-white">Check Your Email</h2>
                <p className="mt-2 text-sm text-slate-400 max-w-xs mx-auto">
                  We've sent a password reset link to{" "}
                  <span className="text-white font-medium">{email}</span>. Check your inbox and
                  follow the instructions.
                </p>
              </div>

              <div className="pt-2 space-y-3">
                <Button
                  type="button"
                  variant="secondary"
                  fullWidth
                  size="lg"
                  onClick={() => {
                    setIsSent(false);
                    setEmail("");
                  }}
                >
                  Try a different email
                </Button>

                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-purple-400 transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Login
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>
    </AuthLayout>
  );
}
