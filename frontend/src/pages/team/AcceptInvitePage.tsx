import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Shield,
  Building2,
  Mail,
  Loader2,
  LogIn,
  Sparkles,
} from "lucide-react";
import AuthLayout from "@/components/layout/AuthLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useAuthStore, syncUserPreferences } from "@/stores/authStore";
import { showSuccess, showError } from "@/components/ui/Toast";
import api from "@/lib/api";
import { signInWithGooglePopup } from "@/lib/firebase";

interface InviteInfo {
  account_id: string;
  workspace_name: string;
  invitation_email?: string;
  role: string;
  invitation_status: string;
}

export default function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();

  const accountId = searchParams.get("account") || searchParams.get("account_id");
  const token = searchParams.get("token");

  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [inviteInfo, setInviteInfo] = useState<InviteInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    if (!accountId || !token) {
      setError("Missing account or invitation token in link. Please verify the invitation URL.");
      setLoading(false);
      return;
    }

    async function fetchInvite() {
      try {
        setLoading(true);
        setError(null);
        const { data } = await api.get(`/accounts/${accountId}/team/invite-info?token=${encodeURIComponent(token!)}`);
        setInviteInfo(data);
        if (data.invitation_status === "accepted") {
          setAccepted(true);
        }
      } catch (err: any) {
        console.error("Fetch invite error:", err);
        setError(
          err?.response?.data?.detail ||
          "This invitation link is invalid, expired, or has already been used."
        );
      } finally {
        setLoading(false);
      }
    }

    fetchInvite();
  }, [accountId, token]);

  const handleAcceptInvite = async () => {
    if (!accountId || !token) return;
    try {
      setAccepting(true);
      setError(null);

      await api.post(`/accounts/${accountId}/team/accept-invite?token=${encodeURIComponent(token)}`);

      // Switch active workspace in localStorage to the accepted account
      localStorage.setItem("account_id", accountId);

      setAccepted(true);
      showSuccess(`Welcome to ${inviteInfo?.workspace_name || "the team"}!`);

      setTimeout(() => {
        navigate("/dashboard");
      }, 1500);
    } catch (err: any) {
      console.error("Accept invite error:", err);
      const msg = err?.response?.data?.detail || "Could not accept invitation. Please try again.";
      setError(msg);
      showError(msg);
    } finally {
      setAccepting(false);
    }
  };

  const handleGoogleSignInAndAccept = async () => {
    try {
      setGoogleLoading(true);
      setError(null);
      const firebaseUser = await signInWithGooglePopup();
      if (!firebaseUser?.email) {
        showError("No email returned from Google.");
        setGoogleLoading(false);
        return;
      }

      // Authenticate with backend
      const { data } = await api.post("/auth/google/firebase", {
        id_token: firebaseUser.idToken,
        email: firebaseUser.email,
        full_name: firebaseUser.displayName,
        avatar_url: firebaseUser.photoURL,
      });

      const { access_token, refresh_token, user: loggedUser } = data;
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);
      localStorage.setItem("account_id", accountId!);

      syncUserPreferences(loggedUser);

      useAuthStore.setState({
        user: loggedUser,
        accessToken: access_token,
        refreshToken: refresh_token,
        isAuthenticated: true,
        isLoading: false,
      });

      // Now accept the invitation
      await api.post(`/accounts/${accountId}/team/accept-invite?token=${encodeURIComponent(token!)}`);

      setAccepted(true);
      showSuccess(`Welcome to ${inviteInfo?.workspace_name || "the team"}!`);

      setTimeout(() => {
        navigate("/dashboard");
      }, 1500);
    } catch (err: any) {
      console.error("Google accept invite error:", err);
      if (err?.code === "auth/popup-closed-by-user" || err?.code === "auth/cancelled-popup-request") {
        setGoogleLoading(false);
        return;
      }
      const msg = err?.response?.data?.detail || err?.message || "Authentication failed.";
      setError(msg);
      showError(msg);
    } finally {
      setGoogleLoading(false);
    }
  };

  const isEmailMismatch =
    isAuthenticated &&
    user?.email &&
    inviteInfo?.invitation_email &&
    user.email.toLowerCase() !== inviteInfo.invitation_email.toLowerCase();

  return (
    <AuthLayout title="" subtitle="">
      <GlassCard className="w-full max-w-lg mx-auto" padding="lg">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Loader2 className="h-10 w-10 animate-spin text-purple-400 mb-4" />
            <h2 className="text-lg font-semibold" style={{ color: "var(--page-heading)" }}>
              Loading Invitation...
            </h2>
            <p className="text-xs mt-1" style={{ color: "var(--page-text-muted)" }}>
              Verifying team security tokens
            </p>
          </div>
        ) : accepted ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-center py-6 space-y-5"
          >
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 shadow-lg shadow-green-500/20 text-white">
              <CheckCircle2 className="h-9 w-9" />
            </div>
            <div>
              <h2 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
                Invitation Accepted!
              </h2>
              <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
                You are now a member of <strong className="text-purple-400">{inviteInfo?.workspace_name || "the workspace"}</strong>.
              </p>
            </div>
            <div className="pt-2">
              <Button
                variant="primary"
                fullWidth
                size="lg"
                onClick={() => navigate("/dashboard")}
                icon={<ArrowRight className="h-4 w-4" />}
              >
                Go to Workspace Dashboard
              </Button>
            </div>
          </motion.div>
        ) : error ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-6 space-y-5"
          >
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400">
              <AlertCircle className="h-8 w-8" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-red-400">
                Invalid or Expired Invitation
              </h2>
              <p className="mt-2 text-xs leading-relaxed max-w-sm mx-auto" style={{ color: "var(--page-text-secondary)" }}>
                {error}
              </p>
            </div>
            <div className="pt-3 flex flex-col gap-2.5">
              <Button
                variant="primary"
                fullWidth
                onClick={() => navigate("/dashboard")}
              >
                Go to Dashboard
              </Button>
              <Button
                variant="ghost"
                fullWidth
                onClick={() => navigate("/login")}
              >
                Sign in with another account
              </Button>
            </div>
          </motion.div>
        ) : (
          <div className="space-y-6">
            {/* Header */}
            <div className="text-center">
              <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-500 to-indigo-600 text-white shadow-xl shadow-purple-500/20">
                <Users className="h-7 w-7" />
              </div>
              <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
                Team Invitation
              </h1>
              <p className="mt-1 text-xs" style={{ color: "var(--page-text-secondary)" }}>
                You have been invited to collaborate on MarketEngine
              </p>
            </div>

            {/* Workspace Card */}
            <div
              className="rounded-2xl p-4 border space-y-3.5"
              style={{
                background: "var(--surface-border-subtle, rgba(255, 255, 255, 0.03))",
                borderColor: "var(--surface-border)",
              }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-xs" style={{ color: "var(--page-text-muted)" }}>Workspace</p>
                    <p className="text-sm font-bold" style={{ color: "var(--page-heading)" }}>
                      {inviteInfo?.workspace_name}
                    </p>
                  </div>
                </div>
                <Badge variant="info" size="sm" className="capitalize">
                  <Shield className="h-3 w-3 mr-1" />
                  {inviteInfo?.role || "Member"}
                </Badge>
              </div>

              {inviteInfo?.invitation_email && (
                <div className="flex items-center gap-2 pt-2 border-t text-xs" style={{ borderColor: "var(--surface-border)" }}>
                  <Mail className="h-3.5 w-3.5 text-purple-400" />
                  <span style={{ color: "var(--page-text-muted)" }}>Invited Email:</span>
                  <span className="font-semibold text-purple-400">{inviteInfo.invitation_email}</span>
                </div>
              )}
            </div>

            {/* Email Mismatch Warning */}
            {isEmailMismatch && (
              <div className="rounded-xl p-3.5 bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-amber-300 text-xs leading-relaxed">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
                <div>
                  <strong className="block font-semibold">Account Email Mismatch</strong>
                  You are logged in as <span className="underline">{user?.email}</span>, but this invite was sent to <span className="underline font-semibold">{inviteInfo?.invitation_email}</span>.
                </div>
              </div>
            )}

            {/* Action Buttons */}
            {isAuthenticated ? (
              <div className="space-y-3">
                <Button
                  variant="primary"
                  fullWidth
                  size="lg"
                  loading={accepting}
                  onClick={handleAcceptInvite}
                  icon={<CheckCircle2 className="h-4 w-4" />}
                >
                  Accept Invitation & Join Team
                </Button>
                {isEmailMismatch && (
                  <Button
                    variant="secondary"
                    fullWidth
                    onClick={() => {
                      useAuthStore.getState().logout();
                      navigate(`/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`);
                    }}
                  >
                    Switch to Invited Account
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <Button
                  variant="primary"
                  fullWidth
                  size="lg"
                  onClick={() =>
                    navigate(
                      `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
                    )
                  }
                  icon={<LogIn className="h-4 w-4" />}
                >
                  Sign In to Accept
                </Button>

                <Button
                  type="button"
                  variant="secondary"
                  fullWidth
                  size="lg"
                  loading={googleLoading}
                  onClick={handleGoogleSignInAndAccept}
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
                  Continue with Google
                </Button>

                <p className="text-center text-xs pt-1" style={{ color: "var(--page-text-secondary)" }}>
                  New to MarketEngine?{" "}
                  <Link
                    to={`/register?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`}
                    className="font-semibold text-purple-400 hover:text-purple-300 underline underline-offset-2"
                  >
                    Create an account
                  </Link>
                </p>
              </div>
            )}
          </div>
        )}
      </GlassCard>
    </AuthLayout>
  );
}
