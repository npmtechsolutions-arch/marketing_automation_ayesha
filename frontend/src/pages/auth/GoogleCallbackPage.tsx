import { useEffect, useState, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import api from "@/lib/api";
import { useAuthStore, syncUserPreferences } from "@/stores/authStore";
import { showSuccess, showError } from "@/components/ui/Toast";

export default function GoogleCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const executedRef = useRef(false);

  useEffect(() => {
    if (executedRef.current) return;
    executedRef.current = true;

    const code = searchParams.get("code");
    const error = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");

    if (error) {
      setStatus("error");
      setErrorMessage(errorDescription || error || "Google authentication was cancelled or failed.");
      showError(errorDescription || "Google sign-in was cancelled.");
      setTimeout(() => navigate("/login"), 3000);
      return;
    }

    if (!code) {
      setStatus("error");
      setErrorMessage("No authorization code received from Google.");
      showError("Invalid Google callback. Missing authorization code.");
      setTimeout(() => navigate("/login"), 3000);
      return;
    }

    const exchangeCode = async () => {
      try {
        const redirectUri = window.location.origin + "/auth/callback/google";
        const { data } = await api.post("/auth/google/callback", {
          code,
          redirect_uri: redirectUri,
        });

        const { access_token, refresh_token, user } = data;

        localStorage.setItem("access_token", access_token);
        localStorage.setItem("refresh_token", refresh_token);

        // Fetch user's first account workspace
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

        setStatus("success");
        showSuccess(`Welcome back, ${user.full_name || "there"}!`);
        setTimeout(() => {
          navigate("/dashboard", { replace: true });
        }, 800);
      } catch (err: any) {
        console.error("Google OAuth error:", err);
        setStatus("error");
        const msg =
          err?.response?.data?.detail ||
          "Failed to complete Google Sign-In. Please try again.";
        setErrorMessage(msg);
        showError(msg);
        setTimeout(() => navigate("/login"), 3500);
      }
    };

    exchangeCode();
  }, [searchParams, navigate]);

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 select-none"
      style={{ background: "var(--page-bg)" }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{
          background: "var(--surface-bg)",
          border: "1px solid var(--surface-border)",
          boxShadow: "var(--surface-shadow-lg)",
        }}
        className="w-full max-w-md rounded-2xl p-8 text-center"
      >
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-purple-500/20 shadow-md">
          {status === "loading" && (
            <Loader2 className="h-8 w-8 text-purple-500 animate-spin" />
          )}
          {status === "success" && (
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
          )}
          {status === "error" && (
            <AlertCircle className="h-8 w-8 text-red-500" />
          )}
        </div>

        <h2 className="text-xl font-bold mb-2" style={{ color: "var(--page-heading)" }}>
          {status === "loading" && "Signing in with Google..."}
          {status === "success" && "Authentication Successful!"}
          {status === "error" && "Authentication Failed"}
        </h2>

        <p className="text-sm mb-6" style={{ color: "var(--page-text-secondary)" }}>
          {status === "loading" && "Verifying your Google account credentials..."}
          {status === "success" && "Redirecting to your marketing command center..."}
          {status === "error" && (errorMessage || "An error occurred during Google Sign-In.")}
        </p>

        {status === "error" && (
          <button
            onClick={() => navigate("/login")}
            className="w-full py-2.5 px-4 rounded-xl text-sm font-semibold text-white shadow-md transition-all duration-200 cursor-pointer"
            style={{ background: "var(--gradient-primary)" }}
          >
            Back to Sign In
          </button>
        )}
      </motion.div>
    </div>
  );
}
