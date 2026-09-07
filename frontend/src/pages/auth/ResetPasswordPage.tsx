import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
} from "lucide-react";
import AuthLayout from "@/components/layout/AuthLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import api from "@/lib/api";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

// Mirrors the backend's rule in POST /auth/reset-password. Kept in sync
// deliberately: the check here is a convenience, the server's is the one that
// counts.
const MIN_PASSWORD_LENGTH = 8;

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});
  const [formError, setFormError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDone, setIsDone] = useState(false);

  // The link is unusable without a token, so say so immediately rather than
  // letting someone type a new password and only then fail.
  const isTokenMissing = !token;

  function validate(): boolean {
    const next: { password?: string; confirm?: string } = {};
    if (password.length < MIN_PASSWORD_LENGTH) {
      next.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
    }
    if (confirmPassword !== password) {
      next.confirm = "Passwords do not match";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!validate()) return;

    setIsLoading(true);
    try {
      await api.post("/auth/reset-password", {
        token,
        new_password: password,
      });
      setIsDone(true);
      // Give the confirmation a moment to register before moving on.
      setTimeout(() => navigate("/login"), 2500);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Something went wrong. Please try again.";
      setFormError(detail);
    } finally {
      setIsLoading(false);
    }
  }

  // A rejected token is the common failure here -- reset links expire after an
  // hour and are single-use in effect once the password changes. Offer the way
  // forward rather than leaving the user at a dead end.
  const tokenRejected =
    isTokenMissing || /invalid|expired/i.test(formError);

  const requestNewLink = (
    <Link
      to="/forgot-password"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-purple-400 hover:text-purple-300 transition-colors"
    >
      Request a new reset link
    </Link>
  );

  return (
    <AuthLayout title="" subtitle="">
      <GlassCard className="w-full" padding="lg">
        <AnimatePresence mode="wait">
          {isTokenMissing ? (
            <motion.div
              key="no-token"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="space-y-6 text-center py-4"
            >
              <div className="flex justify-center">
                <div className="w-16 h-16 rounded-full bg-amber-500/15 border border-amber-500/20 flex items-center justify-center">
                  <AlertCircle className="w-8 h-8 text-amber-400" />
                </div>
              </div>
              <div>
                <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
                  Link Not Valid
                </h1>
                <p className="mt-2 text-sm max-w-xs mx-auto" style={{ color: "var(--page-text-secondary)" }}>
                  This password reset link is missing its token. It may have been
                  copied incompletely from your email.
                </p>
              </div>
              <div className="pt-2 space-y-3">
                {requestNewLink}
                <div>
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-1.5 text-sm hover:text-purple-400 transition-colors"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Login
                  </Link>
                </div>
              </div>
            </motion.div>
          ) : !isDone ? (
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
                <motion.div variants={fadeUp} className="flex justify-center">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-600/20 to-blue-600/20 border border-purple-500/20 flex items-center justify-center">
                    <Lock className="w-7 h-7 text-purple-400" />
                  </div>
                </motion.div>

                <motion.div variants={fadeUp} className="text-center">
                  <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
                    Choose a New Password
                  </h1>
                  <p className="mt-2 text-sm" style={{ color: "var(--page-text-secondary)" }}>
                    Pick something you haven't used before
                  </p>
                </motion.div>

                {formError && (
                  <motion.div
                    variants={fadeUp}
                    className="rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-300"
                  >
                    <p>{formError}</p>
                    {tokenRejected && <p className="mt-2">{requestNewLink}</p>}
                  </motion.div>
                )}

                <motion.div variants={fadeUp}>
                  <Input
                    label="New password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    icon={<Lock className="w-4 h-4" />}
                    error={errors.password}
                    placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
                    autoComplete="new-password"
                    rightElement={
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        className="text-slate-400 hover:text-slate-200 transition-colors"
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    }
                  />
                </motion.div>

                <motion.div variants={fadeUp}>
                  <Input
                    label="Confirm new password"
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    icon={<Lock className="w-4 h-4" />}
                    error={errors.confirm}
                    placeholder="Re-enter your new password"
                    autoComplete="new-password"
                  />
                </motion.div>

                <motion.div variants={fadeUp}>
                  <Button type="submit" fullWidth size="lg" loading={isLoading}>
                    Reset Password
                  </Button>
                </motion.div>

                <motion.div variants={fadeUp} className="text-center">
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-1.5 text-sm hover:text-purple-400 transition-colors"
                    style={{ color: "var(--page-text-secondary)" }}
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
                <h2 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
                  Password Updated
                </h2>
                <p className="mt-2 text-sm max-w-xs mx-auto" style={{ color: "var(--page-text-secondary)" }}>
                  You can now sign in with your new password. Taking you to the
                  login page.
                </p>
              </div>

              <div className="pt-2">
                <Button type="button" fullWidth size="lg" onClick={() => navigate("/login")}>
                  Go to Login
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCard>
    </AuthLayout>
  );
}
