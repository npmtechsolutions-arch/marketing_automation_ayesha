import { useNavigate } from "react-router-dom";
import { motion, type Variants } from "framer-motion";
import {
  Trash2,
  Settings,
  Mail,
  Unplug,
  Clock,
  ShieldCheck,
  FileWarning,
  ArrowRight,
} from "lucide-react";
import PublicLayout from "@/components/layout/PublicLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

/* ------------------------------------------------------------------ */
/*  Config                                                             */
/* ------------------------------------------------------------------ */

const COMPANY = "MarketEngine";
const DELETION_EMAIL = "privacy@marketengine.ai";
const LAST_UPDATED = "July 13, 2026";

/* ------------------------------------------------------------------ */
/*  Animation helpers                                                  */
/* ------------------------------------------------------------------ */

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.06, ease: "easeOut" },
  }),
};

/* ------------------------------------------------------------------ */
/*  Content                                                            */
/* ------------------------------------------------------------------ */

interface Method {
  icon: React.ElementType;
  title: string;
  body: React.ReactNode;
}

const methods: Method[] = [
  {
    icon: Settings,
    title: "Option 1 — Delete from your account settings",
    body: (
      <>
        <p>
          The fastest way to delete your data is directly from within the app:
        </p>
        <ol>
          <li>Log in to your {COMPANY} account.</li>
          <li>
            Go to <strong>Settings → Account</strong>.
          </li>
          <li>
            Select <strong>Delete Account</strong>.
          </li>
          <li>
            Confirm your choice. This permanently removes your profile, content,
            connected-account tokens, and analytics data.
          </li>
        </ol>
      </>
    ),
  },
  {
    icon: Mail,
    title: "Option 2 — Request deletion by email",
    body: (
      <>
        <p>
          If you cannot access your account, email us and we will process the
          deletion on your behalf:
        </p>
        <ol>
          <li>
            Send an email to{" "}
            <a href={`mailto:${DELETION_EMAIL}?subject=Data%20Deletion%20Request`}>
              {DELETION_EMAIL}
            </a>{" "}
            from the address associated with your account.
          </li>
          <li>
            Use the subject line <strong>"Data Deletion Request"</strong>.
          </li>
          <li>
            Include the email address and, if applicable, the connected social
            account(s) tied to your profile so we can verify your identity.
          </li>
        </ol>
        <p>
          We verify every request before acting on it to protect your account
          from unauthorized deletion.
        </p>
      </>
    ),
  },
  {
    icon: Unplug,
    title: "Option 3 — Disconnect a single social platform",
    body: (
      <>
        <p>
          To remove only the data associated with one connected platform (for
          example, revoking access we received from Facebook or Instagram)
          without deleting your whole account:
        </p>
        <ol>
          <li>
            Go to <strong>Platforms → Social Accounts</strong> in the app.
          </li>
          <li>
            Select the platform you want to remove and click{" "}
            <strong>Disconnect</strong>.
          </li>
          <li>
            We immediately revoke the stored access token and delete the profile
            and analytics data we retrieved from that platform.
          </li>
        </ol>
        <p>
          You can also revoke access from the platform's own app settings (e.g.
          Facebook → Settings → Business Integrations).
        </p>
      </>
    ),
  },
];

const whatGetsDeleted = [
  "Your profile and account information",
  "All posts, drafts, campaigns, and strategies you created",
  "Access tokens for every connected social account",
  "Analytics and usage data tied to your account",
  "Team and billing records, subject to legal retention requirements",
];

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function DataDeletionPage() {
  const navigate = useNavigate();

  return (
    <PublicLayout>
      {/* Hero */}
      <section className="relative overflow-hidden pt-32 pb-16">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-1/4 left-1/3 h-[500px] w-[500px] rounded-full bg-purple-700/20 blur-[160px]" />
          <div className="absolute -top-1/4 right-1/3 h-[400px] w-[400px] rounded-full bg-blue-700/15 blur-[140px]" />
        </div>

        <div className="relative mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div initial="hidden" animate="visible" variants={fadeUp}>
            <Badge variant="info" className="mb-6 px-4 py-1.5 text-sm">
              <Trash2 className="mr-1.5 inline h-3.5 w-3.5" />
              You are in control of your data
            </Badge>
            <h1
              className="text-4xl font-extrabold tracking-tight sm:text-5xl"
              style={{ color: "var(--page-heading)" }}
            >
              Data Deletion Instructions
            </h1>
            <p
              className="mx-auto mt-4 max-w-xl text-lg"
              style={{ color: "var(--page-text-secondary)" }}
            >
              You can request the deletion of your personal data from {COMPANY}{" "}
              at any time. Choose the method that works best for you below.
            </p>
            <p
              className="mt-3 text-sm"
              style={{ color: "var(--page-text-muted)" }}
            >
              Last updated: {LAST_UPDATED}
            </p>
          </motion.div>
        </div>
      </section>

      {/* Methods */}
      <section className="relative pb-8">
        <div className="relative mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <div className="space-y-4">
            {methods.map((method, i) => {
              const Icon = method.icon;
              return (
                <motion.div
                  key={method.title}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true, margin: "-80px" }}
                  variants={fadeUp}
                  custom={i}
                >
                  <GlassCard padding="lg">
                    <div className="flex items-start gap-4">
                      <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl border border-purple-500/20 bg-gradient-to-br from-purple-600/20 to-blue-600/20">
                        <Icon className="h-5 w-5 text-purple-400" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h2
                          className="mb-3 text-xl font-semibold"
                          style={{ color: "var(--page-heading)" }}
                        >
                          {method.title}
                        </h2>
                        <div className="legal-prose">{method.body}</div>
                      </div>
                    </div>
                  </GlassCard>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* What gets deleted + timeline */}
      <section className="relative pb-8">
        <div className="relative mx-auto grid max-w-3xl gap-4 px-4 sm:px-6 md:grid-cols-2 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
          >
            <GlassCard padding="lg" className="h-full">
              <div className="mb-3 flex items-center gap-3">
                <FileWarning className="h-5 w-5 text-purple-400" />
                <h2
                  className="text-lg font-semibold"
                  style={{ color: "var(--page-heading)" }}
                >
                  What gets deleted
                </h2>
              </div>
              <ul className="legal-prose">
                {whatGetsDeleted.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </GlassCard>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
            custom={1}
          >
            <GlassCard padding="lg" className="h-full">
              <div className="mb-3 flex items-center gap-3">
                <Clock className="h-5 w-5 text-purple-400" />
                <h2
                  className="text-lg font-semibold"
                  style={{ color: "var(--page-heading)" }}
                >
                  How long it takes
                </h2>
              </div>
              <div className="legal-prose">
                <p>
                  Deletions started from your account settings take effect
                  immediately. Email requests are completed within{" "}
                  <strong>30 days</strong> of verification.
                </p>
                <p>
                  Some records may be retained for a limited period where
                  required by law (for example, tax and billing records), after
                  which they are permanently removed.
                </p>
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </section>

      {/* Note + CTA */}
      <section className="relative pb-24">
        <div className="relative mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
          >
            <GlassCard padding="lg">
              <div className="flex flex-col items-center gap-5 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-purple-500/20 bg-gradient-to-br from-purple-600/20 to-blue-600/20">
                  <ShieldCheck className="h-6 w-6 text-purple-400" />
                </div>
                <div>
                  <h2
                    className="text-xl font-semibold"
                    style={{ color: "var(--page-heading)" }}
                  >
                    Ready to request deletion?
                  </h2>
                  <p
                    className="mx-auto mt-2 max-w-md text-sm"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    Email us at{" "}
                    <a
                      href={`mailto:${DELETION_EMAIL}?subject=Data%20Deletion%20Request`}
                      className="text-purple-400 hover:underline"
                    >
                      {DELETION_EMAIL}
                    </a>{" "}
                    or manage everything from your account settings.
                  </p>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button
                    variant="primary"
                    size="lg"
                    icon={<Settings className="h-4 w-4" />}
                    onClick={() => navigate("/settings")}
                  >
                    Go to Settings
                  </Button>
                  <Button
                    variant="secondary"
                    size="lg"
                    icon={<ArrowRight className="h-4 w-4" />}
                    iconPosition="right"
                    onClick={() => navigate("/privacy")}
                  >
                    Read Privacy Policy
                  </Button>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </section>
    </PublicLayout>
  );
}
