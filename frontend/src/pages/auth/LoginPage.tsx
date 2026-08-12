import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Mail, Lock, Eye, EyeOff, LogIn, ShieldCheck, AlertCircle } from "lucide-react";
import AuthLayout from "@/components/layout/AuthLayout";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuthStore, syncUserPreferences } from "@/stores/authStore";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";
import { signInWithGooglePopup } from "@/lib/firebase";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, complete2faLogin, isLoading } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
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

      showSuccess(`Welcome back, ${user.full_name || "there"}!`);
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

  // Two-factor challenge state
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [twoFaCode, setTwoFaCode] = useState("");

  const [errors, setErrors] = useState<{ email?: string; password?: string; general?: string }>({});
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean }>({});

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

  const handleEmailChange = (val: string) => {
    setEmail(val);
    if (errors.general) setErrors((prev) => ({ ...prev, general: undefined }));
    if (touched.email || errors.email) {
      setErrors((prev) => ({ ...prev, email: validateEmail(val) }));
    }
  };

  const handlePasswordChange = (val: string) => {
    setPassword(val);
    if (errors.general) setErrors((prev) => ({ ...prev, general: undefined }));
    if (touched.password || errors.password) {
      setErrors((prev) => ({ ...prev, password: validatePassword(val) }));
    }
  };

  function validate(): boolean {
    const emailErr = validateEmail(email);
    const passErr = validatePassword(password);
    const next: typeof errors = {};
    if (emailErr) next.email = emailErr;
    if (passErr) next.password = passErr;
    setErrors(next);
    setTouched({ email: true, password: true });
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    try {
      setErrors({});
      const result = await login(email, password);
      if (result.requires2fa && result.challengeToken) {
        setChallengeToken(result.challengeToken);
        return;
      }
      showSuccess("Welcome back!");
      navigate("/dashboard");
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "User ID or password was incorrect. Please check your credentials.";
      setErrors({ general: message });
      showError(message);
    }
  }

  async function handle2faSubmit(e: FormEvent) {
    e.preventDefault();
    if (!challengeToken) return;
    if (twoFaCode.trim().length < 6) {
      setErrors({ general: "Enter the 6-digit code from your authenticator app." });
      showError("Enter the 6-digit verification code.");
      return;
    }
    try {
      setErrors({});
      await complete2faLogin(challengeToken, twoFaCode.trim());
      showSuccess("Verification successful!");
      navigate("/dashboard");
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Invalid verification code. Please try again.";
      setErrors({ general: message });
      showError(message);
    }
  }

  if (challengeToken) {
    return (
      <AuthLayout title="" subtitle="">
        <div
          className="w-full rounded-2xl p-8"
          style={{
            background: "var(--surface-bg)",
            border: "1px solid var(--surface-border)",
            boxShadow: "var(--surface-shadow)",
          }}
        >
          <form onSubmit={handle2faSubmit} className="space-y-6">
            <div className="text-center mb-2">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl" style={{ background: "var(--gradient-primary)" }}>
                <ShieldCheck className="h-6 w-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold" style={{ color: "var(--page-text)" }}>
                Two-Factor Verification
              </h1>
              <p className="mt-2 text-sm" style={{ color: "var(--page-text-secondary)" }}>
                Enter the 6-digit code from your authenticator app, or a recovery code.
              </p>
            </div>

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
                    <p className="text-xs font-bold text-red-500">Verification Error</p>
                    <p className="text-xs font-medium text-red-400 mt-0.5 leading-relaxed">
                      {errors.general}
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <Input
              label="Verification code"
              value={twoFaCode}
              onChange={(e) => setTwoFaCode(e.target.value)}
              placeholder="123456"
              autoComplete="one-time-code"
              autoFocus
            />

            <Button type="submit" fullWidth size="lg" loading={isLoading} icon={<ShieldCheck className="w-4 h-4" />}>
              Verify & Sign In
            </Button>

            <button
              type="button"
              onClick={() => { setChallengeToken(null); setTwoFaCode(""); setErrors({}); }}
              className="w-full text-center text-xs font-medium"
              style={{ color: "var(--page-text-secondary)" }}
            >
              ← Back to login
            </button>
          </form>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="" subtitle="">
      <div
        className="w-full rounded-2xl p-8"
        style={{
          background: "var(--surface-bg)",
          border: "1px solid var(--surface-border)",
          boxShadow: "var(--surface-shadow)",
        }}
      >
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Heading */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-center mb-2"
          >
            <h1 className="text-3xl font-bold">
              <span
                style={{
                  background: "var(--gradient-primary)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Welcome Back
              </span>
            </h1>
            <p className="mt-2 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Sign in to your marketing command center
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
                  <p className="text-xs font-bold text-red-500">Authentication Error</p>
                  <p className="text-xs font-medium text-red-400 mt-0.5 leading-relaxed">
                    {errors.general}
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Email */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.05 }}
          >
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
              onBlur={() => {
                setTouched((t) => ({ ...t, email: true }));
                setErrors((prev) => ({ ...prev, email: validateEmail(email) }));
              }}
              icon={<Mail className="w-4 h-4" />}
              error={errors.email}
              placeholder="you@company.com"
              autoComplete="email"
            />
          </motion.div>

          {/* Password */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <Input
              label="Password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => handlePasswordChange(e.target.value)}
              onBlur={() => {
                setTouched((t) => ({ ...t, password: true }));
                setErrors((prev) => ({ ...prev, password: validatePassword(password) }));
              }}
              icon={<Lock className="w-4 h-4" />}
              error={errors.password}
              placeholder="Enter your password (min 6 characters)"
              autoComplete="current-password"
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
          </motion.div>

          {/* Remember me + Forgot */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="flex items-center justify-between"
          >
            <label className="flex items-center gap-2 cursor-pointer group">
              <div
                className={cn(
                  "w-4 h-4 rounded border transition-all duration-200 flex items-center justify-center",
                  rememberMe
                    ? "border-transparent"
                    : "group-hover:border-opacity-50"
                )}
                style={{
                  background: rememberMe ? "var(--gradient-primary)" : "var(--input-bg)",
                  borderColor: rememberMe ? "transparent" : "var(--input-border)",
                }}
                onClick={() => setRememberMe((p) => !p)}
              >
                {rememberMe && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3} style={{ color: "#fff" }}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <span className="text-xs select-none" style={{ color: "var(--page-text-secondary)" }}>
                Remember me
              </span>
            </label>
            <Link
              to="/forgot-password"
              className="text-xs font-medium transition-colors"
              style={{ color: "var(--accent-purple)" }}
            >
              Forgot password?
            </Link>
          </motion.div>

          {/* Submit */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Button
              type="submit"
              fullWidth
              size="lg"
              loading={isLoading}
              icon={<LogIn className="w-4 h-4" />}
            >
              Sign In
            </Button>
          </motion.div>

          {/* Divider */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.25 }}
            className="relative flex items-center gap-4"
          >
            <div className="flex-1 h-px" style={{ background: "var(--surface-border)" }} />
            <span className="text-xs uppercase tracking-wider" style={{ color: "var(--page-text-muted)" }}>
              or continue with
            </span>
            <div className="flex-1 h-px" style={{ background: "var(--surface-border)" }} />
          </motion.div>

          {/* Google OAuth */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={googleLoading}
              className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl text-sm font-semibold transition-all duration-200 hover:shadow-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: "var(--surface-bg)",
                border: "1.5px solid var(--surface-border)",
                color: "var(--page-text)",
              }}
            >
              {googleLoading ? (
                <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    fill="#EA4335"
                  />
                </svg>
              )}
              {googleLoading ? "Connecting to Google..." : "Continue with Google"}
            </button>
          </motion.div>

          {/* Sign up link */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.35 }}
            className="text-center text-sm"
            style={{ color: "var(--page-text-secondary)" }}
          >
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
              className="font-semibold transition-colors"
              style={{ color: "var(--accent-purple)" }}
            >
              Sign up
            </Link>
          </motion.p>
        </form>
      </div>
    </AuthLayout>
  );
}
