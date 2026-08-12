import { useState, useMemo, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, Eye, EyeOff, User, Sparkles, UserPlus, AlertCircle } from "lucide-react";
import AuthLayout from "@/components/layout/AuthLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuthStore, syncUserPreferences } from "@/stores/authStore";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";
import { signInWithGooglePopup } from "@/lib/firebase";

const stagger = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.05 },
  },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" as const } },
};

interface PasswordStrength {
  score: number;
  label: string;
  color: string;
  bgColor: string;
}

function getPasswordStrength(pw: string): PasswordStrength {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[a-z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 2) return { score, label: "Weak", color: "text-red-400", bgColor: "bg-red-500" };
  if (score <= 3) return { score, label: "Medium", color: "text-amber-400", bgColor: "bg-amber-500" };
  return { score, label: "Strong", color: "text-emerald-400", bgColor: "bg-emerald-500" };
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register, isLoading } = useAuthStore();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const handleGoogleSignIn = async () => {
    try {
      setGoogleLoading(true);
      const firebaseUser = await signInWithGooglePopup();
      if (!firebaseUser?.email) {
        showError("No email returned from Google authentication.");
        setGoogleLoading(false);
        return;
      }

      // Exchange with MarketEngine backend
      const { data } = await api.post("/auth/google/firebase", {
        id_token: firebaseUser.idToken,
        email: firebaseUser.email,
        full_name: firebaseUser.displayName,
        avatar_url: firebaseUser.photoURL,
      });

      const { access_token, refresh_token, user } = data;
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);

      try {
        const accountsResponse: any = await api.get("/accounts");
        let accountId = null;
        if (accountsResponse.items?.[0]?.id) {
          accountId = accountsResponse.items[0].id;
        } else if (accountsResponse.data?.items?.[0]?.id) {
          accountId = accountsResponse.data.items[0].id;
        } else if (Array.isArray(accountsResponse) && accountsResponse[0]?.id) {
          accountId = accountsResponse[0].id;
        }
        if (accountId) {
          localStorage.setItem("account_id", accountId);
        }
      } catch (err) {
        console.warn("Could not fetch accounts:", err);
      }

      syncUserPreferences(user);

      useAuthStore.setState({
        user,
        accessToken: access_token,
        refreshToken: refresh_token,
        isAuthenticated: true,
        isLoading: false,
      });

      showSuccess(`Account created! Welcome, ${user.full_name || "there"}!`);
      navigate("/dashboard");
    } catch (err: any) {
      console.error("Firebase Google Auth error:", err);
      if (err?.code === "auth/popup-closed-by-user" || err?.code === "auth/cancelled-popup-request") {
        setGoogleLoading(false);
        return;
      }
      const msg = err?.response?.data?.detail || err?.message || "Google Sign-In failed. Please try again.";
      showError(msg);
    } finally {
      setGoogleLoading(false);
    }
  };

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const strength = useMemo(() => getPasswordStrength(password), [password]);

  const validateEmail = (val: string): string | undefined => {
    if (!val.trim()) return "Email address is required";
    if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(val.trim())) {
      return "Please enter a valid email format (e.g. name@company.com)";
    }
    return undefined;
  };

  const validatePassword = (val: string): string | undefined => {
    if (!val) return "Password is required";
    if (val.length < 6) return "Password must be at least 6 characters / digits";
    return undefined;
  };

  const validateFullName = (val: string): string | undefined => {
    if (!val.trim()) return "Full name is required";
    return undefined;
  };

  const validateConfirmPassword = (val: string, pass: string): string | undefined => {
    if (!val) return "Please confirm your password";
    if (val !== pass) return "Passwords do not match";
    return undefined;
  };

  const handleFullNameChange = (val: string) => {
    setFullName(val);
    if (touched.fullName || errors.fullName) {
      const err = validateFullName(val);
      setErrors((prev) => ({ ...prev, fullName: err || "" }));
    }
  };

  const handleEmailChange = (val: string) => {
    setEmail(val);
    if (touched.email || errors.email) {
      const err = validateEmail(val);
      setErrors((prev) => ({ ...prev, email: err || "" }));
    }
  };

  const handlePasswordChange = (val: string) => {
    setPassword(val);
    if (touched.password || errors.password) {
      const err = validatePassword(val);
      setErrors((prev) => ({ ...prev, password: err || "" }));
    }
    if (confirmPassword && (touched.confirmPassword || errors.confirmPassword)) {
      const err = validateConfirmPassword(confirmPassword, val);
      setErrors((prev) => ({ ...prev, confirmPassword: err || "" }));
    }
  };

  const handleConfirmPasswordChange = (val: string) => {
    setConfirmPassword(val);
    if (touched.confirmPassword || errors.confirmPassword) {
      const err = validateConfirmPassword(val, password);
      setErrors((prev) => ({ ...prev, confirmPassword: err || "" }));
    }
  };

  function validate(): boolean {
    const next: Record<string, string> = {};
    const fnErr = validateFullName(fullName);
    if (fnErr) next.fullName = fnErr;

    const emailErr = validateEmail(email);
    if (emailErr) next.email = emailErr;

    const passErr = validatePassword(password);
    if (passErr) next.password = passErr;

    const confirmErr = validateConfirmPassword(confirmPassword, password);
    if (confirmErr) next.confirmPassword = confirmErr;

    if (!agreedToTerms) next.terms = "You must agree to the terms";

    setErrors(next);
    setTouched({ fullName: true, email: true, password: true, confirmPassword: true });
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    try {
      setErrors({});
      await register(email, password, fullName);
      showSuccess("Account created successfully!");
      navigate("/onboarding");
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Registration failed. Please try again.";
      setErrors({ general: message });
      showError(message);
    }
  }

  return (
    <AuthLayout title="" subtitle="">
      <GlassCard className="w-full" padding="lg">
        <motion.form
          onSubmit={handleSubmit}
          variants={stagger}
          initial="hidden"
          animate="visible"
          className="space-y-5"
        >
          {/* Heading */}
          <motion.div variants={fadeUp} className="text-center mb-1">
            <h1 className="text-3xl font-bold">
              <span className="bg-gradient-to-r from-purple-400 via-violet-400 to-blue-400 bg-clip-text text-transparent">
                Create Your Account
              </span>
            </h1>
            <p className="mt-2 text-sm flex items-center justify-center gap-1.5" style={{ color: "var(--page-text-secondary)" }}>
              <Sparkles className="w-4 h-4 text-amber-400" />
              Start your 14-day free trial
            </p>
          </motion.div>

          {/* General error Alert Banner */}
          <AnimatePresence>
            {errors.general && (
              <motion.div
                initial={{ opacity: 0, y: -6, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.98 }}
                transition={{ duration: 0.2 }}
                className="rounded-2xl p-4 flex items-start gap-3 border shadow-sm"
                style={{
                  background: "rgba(239, 68, 68, 0.08)",
                  borderColor: "rgba(239, 68, 68, 0.3)",
                }}
              >
                <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                <div className="text-left flex-1">
                  <p className="text-xs font-bold text-red-500">Registration Error</p>
                  <p className="text-xs font-medium text-red-400 mt-0.5 leading-relaxed">
                    {errors.general}
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Full name */}
          <motion.div variants={fadeUp}>
            <Input
              label="Full name"
              value={fullName}
              onChange={(e) => handleFullNameChange(e.target.value)}
              onBlur={() => {
                setTouched((t) => ({ ...t, fullName: true }));
                const err = validateFullName(fullName);
                setErrors((prev) => ({ ...prev, fullName: err || "" }));
              }}
              icon={<User className="w-4 h-4" />}
              error={errors.fullName}
              placeholder="John Doe"
              autoComplete="name"
            />
          </motion.div>

          {/* Email */}
          <motion.div variants={fadeUp}>
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
              onBlur={() => {
                setTouched((t) => ({ ...t, email: true }));
                const err = validateEmail(email);
                setErrors((prev) => ({ ...prev, email: err || "" }));
              }}
              icon={<Mail className="w-4 h-4" />}
              error={errors.email}
              placeholder="you@company.com"
              autoComplete="email"
            />
          </motion.div>

          {/* Password + strength */}
          <motion.div variants={fadeUp}>
            <Input
              label="Password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => handlePasswordChange(e.target.value)}
              onBlur={() => {
                setTouched((t) => ({ ...t, password: true }));
                const err = validatePassword(password);
                setErrors((prev) => ({ ...prev, password: err || "" }));
              }}
              icon={<Lock className="w-4 h-4" />}
              error={errors.password}
              placeholder="Create a strong password (min 6 characters)"
              autoComplete="new-password"
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="transition-colors cursor-pointer hover:text-purple-400 p-1"
                  style={{ color: "var(--page-text-muted)" }}
                  tabIndex={-1}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
            />

            {/* Strength indicator */}
            {password.length > 0 && (
              <div className="mt-2.5 space-y-1.5">
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div
                      key={i}
                      className={cn(
                        "h-1 flex-1 rounded-full transition-all duration-300",
                        i <= strength.score && strength.bgColor
                      )}
                      style={i <= strength.score ? undefined : { backgroundColor: "var(--sidebar-hover-bg)" }}
                    />
                  ))}
                </div>
                <p className={cn("text-[11px] font-medium", strength.color)}>
                  {strength.label}
                </p>
              </div>
            )}
          </motion.div>

          {/* Confirm password */}
          <motion.div variants={fadeUp}>
            <Input
              label="Confirm password"
              type={showConfirm ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => handleConfirmPasswordChange(e.target.value)}
              onBlur={() => {
                setTouched((t) => ({ ...t, confirmPassword: true }));
                const err = validateConfirmPassword(confirmPassword, password);
                setErrors((prev) => ({ ...prev, confirmPassword: err || "" }));
              }}
              icon={<Lock className="w-4 h-4" />}
              error={errors.confirmPassword}
              placeholder="Confirm your password"
              autoComplete="new-password"
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowConfirm((p) => !p)}
                  className="transition-colors cursor-pointer hover:text-purple-400 p-1"
                  style={{ color: "var(--page-text-muted)" }}
                  tabIndex={-1}
                  title={showConfirm ? "Hide password" : "Show password"}
                >
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
            />
          </motion.div>

          {/* Terms */}
          <motion.div variants={fadeUp}>
            <label className="flex items-start gap-2.5 cursor-pointer group">
              <div
                className={cn(
                  "mt-0.5 w-4 h-4 rounded border transition-all duration-200 flex items-center justify-center flex-shrink-0",
                  agreedToTerms
                    ? "bg-gradient-to-r from-purple-600 to-blue-600 border-transparent"
                    : "border-white/20 bg-white/5 group-hover:border-white/30",
                  errors.terms && !agreedToTerms && "border-red-500/50"
                )}
                onClick={() => setAgreedToTerms((p) => !p)}
              >
                {agreedToTerms && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <span className="text-xs leading-relaxed" style={{ color: "var(--page-text-secondary)" }}>
                I agree to the{" "}
                <Link
                  to="/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-purple-400 hover:text-purple-300 underline underline-offset-2 font-medium"
                >
                  Terms of Service
                </Link>{" "}
                and{" "}
                <Link
                  to="/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-purple-400 hover:text-purple-300 underline underline-offset-2 font-medium"
                >
                  Privacy Policy
                </Link>
              </span>
            </label>
            {errors.terms && (
              <p className="mt-1.5 text-xs text-red-400 pl-6">{errors.terms}</p>
            )}
          </motion.div>

          {/* Submit */}
          <motion.div variants={fadeUp}>
            <Button
              type="submit"
              fullWidth
              size="lg"
              loading={isLoading}
              icon={<UserPlus className="w-4 h-4" />}
            >
              Create Account
            </Button>
          </motion.div>

          {/* Divider */}
          <motion.div variants={fadeUp} className="relative flex items-center gap-4">
            <div className="flex-1 h-px" style={{ backgroundColor: "var(--surface-border)" }} />
            <span className="text-xs uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>or continue with</span>
            <div className="flex-1 h-px" style={{ backgroundColor: "var(--surface-border)" }} />
          </motion.div>

          {/* Google OAuth */}
          <motion.div variants={fadeUp}>
            <Button
              type="button"
              variant="secondary"
              fullWidth
              size="lg"
              onClick={handleGoogleSignIn}
              loading={googleLoading}
              icon={
                !googleLoading && (
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                  </svg>
                )
              }
            >
              {googleLoading ? "Connecting to Google..." : "Continue with Google"}
            </Button>
          </motion.div>

          {/* Sign in link */}
          <motion.p variants={fadeUp} className="text-center text-sm" style={{ color: "var(--page-text-secondary)" }}>
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-purple-400 hover:text-purple-300 transition-colors"
            >
              Sign in
            </Link>
          </motion.p>
        </motion.form>
      </GlassCard>
    </AuthLayout>
  );
}
