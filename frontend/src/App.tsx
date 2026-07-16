import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/Toast';
import { useAuthStore } from '@/stores/authStore';

// Auth pages
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage';
import OnboardingPage from '@/pages/onboarding/OnboardingPage';

// Dashboard pages
import DashboardPage from '@/pages/dashboard/DashboardPage';
import CalendarPage from '@/pages/content/CalendarPage';
import CreatePostPage from '@/pages/content/CreatePostPage';
import AnalyticsPage from '@/pages/analytics/AnalyticsPage';
import StrategyPage from '@/pages/strategy/StrategyPage';
import CampaignsPage from '@/pages/campaigns/CampaignsPage';
import PlatformsPage from '@/pages/platforms/PlatformsPage';
import SocialAccountsPage from '@/pages/platforms/SocialAccountsPage';
import ActivityPage from '@/pages/activity/ActivityPage';
import TeamPage from '@/pages/team/TeamPage';
import SettingsPage from '@/pages/settings/SettingsPage';
import BillingPage from '@/pages/billing/BillingPage';
import NotificationsPage from '@/pages/notifications/NotificationsPage';
import ProfilePage from '@/pages/profile/ProfilePage';

// Public pages
import LandingPage from '@/pages/public/LandingPage';
import PricingPage from '@/pages/public/PricingPage';
import AboutPage from '@/pages/public/AboutPage';
import PrivacyPolicyPage from '@/pages/public/PrivacyPolicyPage';
import DataDeletionPage from '@/pages/public/DataDeletionPage';

// Admin pages
import AdminDashboard from '@/pages/admin/AdminDashboard';
import AdminUsersPage from '@/pages/admin/AdminUsersPage';
import AuditLogsPage from '@/pages/admin/AuditLogsPage';
import ApiDocsPage from '@/pages/admin/ApiDocsPage';

// Help pages
import HelpCenterPage from '@/pages/help/HelpCenterPage';
import ArticlePage from '@/pages/help/ArticlePage';

/* ------------------------------------------------------------------ */
/*  Route guard components                                            */
/* ------------------------------------------------------------------ */

/** Redirects unauthenticated users to /login */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** Redirects already-authenticated users to /dashboard (login/register) */
function ProtectedPublicRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}

/** Requires authentication AND admin role */
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}

/* ------------------------------------------------------------------ */
/*  404 Page                                                          */
/* ------------------------------------------------------------------ */

function NotFoundPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--page-bg-gradient)',
        padding: '2rem',
      }}
    >
      <div
        style={{
          background: 'var(--surface-bg)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid var(--surface-border)',
          boxShadow: 'var(--surface-shadow-lg)',
          borderRadius: '1.5rem',
          padding: '3rem',
          textAlign: 'center',
          maxWidth: '420px',
          width: '100%',
        }}
      >
        <h1
          style={{
            fontSize: '5rem',
            fontWeight: 800,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            margin: 0,
            lineHeight: 1.1,
          }}
        >
          404
        </h1>
        <p
          style={{
            color: 'var(--page-text-secondary)',
            fontSize: '1.125rem',
            margin: '1rem 0 2rem',
          }}
        >
          The page you're looking for doesn't exist or has been moved.
        </p>
        <a
          href="/dashboard"
          style={{
            display: 'inline-block',
            padding: '0.75rem 2rem',
            borderRadius: '0.75rem',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: '#fff',
            fontWeight: 600,
            textDecoration: 'none',
            transition: 'opacity 0.2s',
          }}
        >
          Go to Dashboard
        </a>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Query client                                                      */
/* ------------------------------------------------------------------ */

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

/* ------------------------------------------------------------------ */
/*  App                                                               */
/* ------------------------------------------------------------------ */

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ScrollToTop />
        <Routes>
          {/* Public */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/data-deletion" element={<DataDeletionPage />} />

          {/* Auth */}
          <Route
            path="/login"
            element={
              <ProtectedPublicRoute>
                <LoginPage />
              </ProtectedPublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <ProtectedPublicRoute>
                <RegisterPage />
              </ProtectedPublicRoute>
            }
          />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route
            path="/onboarding"
            element={
              <ProtectedRoute>
                <OnboardingPage />
              </ProtectedRoute>
            }
          />

          {/* App */}
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/calendar" element={<ProtectedRoute><CalendarPage /></ProtectedRoute>} />
          <Route path="/create-post" element={<ProtectedRoute><CreatePostPage /></ProtectedRoute>} />
          <Route path="/create" element={<ProtectedRoute><CreatePostPage /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
          <Route path="/strategy" element={<ProtectedRoute><StrategyPage /></ProtectedRoute>} />
          <Route path="/campaigns" element={<ProtectedRoute><CampaignsPage /></ProtectedRoute>} />
          <Route path="/platforms" element={<ProtectedRoute><PlatformsPage /></ProtectedRoute>} />
          <Route path="/social-accounts" element={<ProtectedRoute><SocialAccountsPage /></ProtectedRoute>} />
          <Route path="/activity" element={<ProtectedRoute><ActivityPage /></ProtectedRoute>} />
          <Route path="/team" element={<ProtectedRoute><TeamPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/billing" element={<ProtectedRoute><BillingPage /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />

          {/* Admin */}
          <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
          <Route path="/admin/users" element={<AdminRoute><AdminUsersPage /></AdminRoute>} />
          <Route path="/admin/audit-logs" element={<AdminRoute><AuditLogsPage /></AdminRoute>} />
          <Route path="/admin/api-docs" element={<AdminRoute><ApiDocsPage /></AdminRoute>} />

          {/* Help */}
          <Route path="/help" element={<HelpCenterPage />} />
          <Route path="/help/article/:id" element={<ArticlePage />} />

          {/* 404 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
