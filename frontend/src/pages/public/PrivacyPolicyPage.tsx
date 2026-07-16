import { useNavigate } from "react-router-dom";
import { motion, type Variants } from "framer-motion";
import {
  ShieldCheck,
  Database,
  Share2,
  Cookie,
  Lock,
  UserCheck,
  Globe,
  Baby,
  RefreshCw,
  Mail,
  ArrowRight,
  Trash2,
} from "lucide-react";
import PublicLayout from "@/components/layout/PublicLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

/* ------------------------------------------------------------------ */
/*  Config                                                             */
/* ------------------------------------------------------------------ */

const COMPANY = "MarketEngine";
const CONTACT_EMAIL = "privacy@marketengine.ai";
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

interface Section {
  id: string;
  icon: React.ElementType;
  title: string;
  body: React.ReactNode;
}

const sections: Section[] = [
  {
    id: "information-we-collect",
    icon: Database,
    title: "1. Information We Collect",
    body: (
      <>
        <p>
          We collect information you provide directly, information generated as
          you use the service, and information from third parties you connect to
          your account.
        </p>
        <ul>
          <li>
            <strong>Account information:</strong> name, email address, password
            (stored hashed), company name, and billing details.
          </li>
          <li>
            <strong>Content you create:</strong> posts, captions, media,
            campaigns, strategies, and comments generated or scheduled through
            the platform.
          </li>
          <li>
            <strong>Connected social accounts:</strong> when you link a platform
            such as Facebook, Instagram, LinkedIn, X, YouTube, TikTok, or
            Pinterest, we receive access tokens and profile, page, and analytics
            data that you authorize.
          </li>
          <li>
            <strong>Usage data:</strong> log data, device and browser
            information, IP address, and interactions with the product.
          </li>
          <li>
            <strong>Cookies and similar technologies:</strong> used to keep you
            signed in and to understand product usage.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "how-we-use-data",
    icon: ShieldCheck,
    title: "2. How We Use Your Information",
    body: (
      <>
        <p>We use the information we collect to:</p>
        <ul>
          <li>Provide, operate, and maintain the platform.</li>
          <li>
            Publish, schedule, and analyze content across the social accounts
            you connect.
          </li>
          <li>
            Generate AI-assisted content, strategies, and recommendations.
          </li>
          <li>Process payments and manage your subscription.</li>
          <li>
            Send transactional messages, security alerts, and, where permitted,
            product updates.
          </li>
          <li>
            Detect, prevent, and address fraud, abuse, and security issues.
          </li>
          <li>Comply with legal obligations.</li>
        </ul>
        <p>
          We do not sell your personal information. AI features process your
          content solely to deliver the service to you and are not used to train
          third-party foundation models on your private data without your
          consent.
        </p>
      </>
    ),
  },
  {
    id: "sharing",
    icon: Share2,
    title: "3. How We Share Information",
    body: (
      <>
        <p>We share information only in the following circumstances:</p>
        <ul>
          <li>
            <strong>Social platforms:</strong> to publish and retrieve data from
            the accounts you connect, per your instructions.
          </li>
          <li>
            <strong>Service providers:</strong> hosting, analytics, payment
            processing, and AI infrastructure providers who process data on our
            behalf under confidentiality obligations.
          </li>
          <li>
            <strong>Legal and safety:</strong> when required by law or to protect
            the rights, property, or safety of our users or the public.
          </li>
          <li>
            <strong>Business transfers:</strong> in connection with a merger,
            acquisition, or sale of assets, subject to this policy.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "cookies",
    icon: Cookie,
    title: "4. Cookies and Tracking",
    body: (
      <p>
        We use strictly necessary cookies to authenticate you and keep your
        session active, and optional analytics cookies to improve the product.
        You can control cookies through your browser settings; disabling
        necessary cookies may prevent you from signing in.
      </p>
    ),
  },
  {
    id: "security",
    icon: Lock,
    title: "5. Data Security",
    body: (
      <p>
        We protect your data using encryption in transit (TLS), encryption at
        rest for sensitive fields such as access tokens, hashed passwords,
        role-based access controls, and regular security reviews. No method of
        transmission or storage is completely secure, but we work continuously
        to safeguard your information.
      </p>
    ),
  },
  {
    id: "retention",
    icon: RefreshCw,
    title: "6. Data Retention",
    body: (
      <p>
        We retain your information for as long as your account is active or as
        needed to provide the service. When you delete content or close your
        account, we delete or anonymize the associated personal data within 30
        days, except where we must retain it to comply with legal, tax, or
        accounting obligations.
      </p>
    ),
  },
  {
    id: "your-rights",
    icon: UserCheck,
    title: "7. Your Rights and Choices",
    body: (
      <>
        <p>
          Depending on your location, you may have the right to access, correct,
          export, restrict, or delete your personal data, and to object to
          certain processing. You can:
        </p>
        <ul>
          <li>Access and update most information from your account settings.</li>
          <li>Disconnect any linked social account at any time.</li>
          <li>
            Request deletion of your account and data via our{" "}
            <a href="/data-deletion">Data Deletion Instructions</a> page.
          </li>
        </ul>
        <p>
          To exercise any of these rights, contact us at{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. We will
          respond within the timeframe required by applicable law.
        </p>
      </>
    ),
  },
  {
    id: "international",
    icon: Globe,
    title: "8. International Data Transfers",
    body: (
      <p>
        We may process and store information in countries other than where you
        live. Where we transfer personal data internationally, we use safeguards
        such as standard contractual clauses to ensure your data receives an
        adequate level of protection.
      </p>
    ),
  },
  {
    id: "children",
    icon: Baby,
    title: "9. Children's Privacy",
    body: (
      <p>
        The service is not directed to children under 16, and we do not
        knowingly collect personal information from them. If you believe a child
        has provided us with personal data, please contact us and we will delete
        it.
      </p>
    ),
  },
  {
    id: "changes",
    icon: RefreshCw,
    title: "10. Changes to This Policy",
    body: (
      <p>
        We may update this Privacy Policy from time to time. When we make
        material changes, we will update the "Last updated" date and, where
        appropriate, notify you by email or through the product.
      </p>
    ),
  },
];

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function PrivacyPolicyPage() {
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
              <ShieldCheck className="mr-1.5 inline h-3.5 w-3.5" />
              Your privacy matters
            </Badge>
            <h1
              className="text-4xl font-extrabold tracking-tight sm:text-5xl"
              style={{ color: "var(--page-heading)" }}
            >
              Privacy Policy
            </h1>
            <p
              className="mx-auto mt-4 max-w-xl text-lg"
              style={{ color: "var(--page-text-secondary)" }}
            >
              How {COMPANY} collects, uses, shares, and protects your
              information when you use our platform.
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

      {/* Body */}
      <section className="relative pb-24">
        <div className="relative mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            custom={1}
          >
            <GlassCard padding="lg" className="mb-8">
              <p
                className="text-sm leading-relaxed"
                style={{ color: "var(--page-text-secondary)" }}
              >
                This policy applies to {COMPANY}, an AI-powered marketing
                automation platform. By creating an account or using the
                service, you agree to the practices described below. If you do
                not agree, please do not use the service.
              </p>
            </GlassCard>
          </motion.div>

          <div className="space-y-4">
            {sections.map((section, i) => {
              const Icon = section.icon;
              return (
                <motion.div
                  key={section.id}
                  id={section.id}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true, margin: "-80px" }}
                  variants={fadeUp}
                  custom={i}
                  className="scroll-mt-24"
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
                          {section.title}
                        </h2>
                        <div className="legal-prose">{section.body}</div>
                      </div>
                    </div>
                  </GlassCard>
                </motion.div>
              );
            })}
          </div>

          {/* Contact / CTA */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
            className="mt-10"
          >
            <GlassCard padding="lg">
              <div className="flex flex-col items-center gap-5 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-purple-500/20 bg-gradient-to-br from-purple-600/20 to-blue-600/20">
                  <Mail className="h-6 w-6 text-purple-400" />
                </div>
                <div>
                  <h2
                    className="text-xl font-semibold"
                    style={{ color: "var(--page-heading)" }}
                  >
                    Questions about your privacy?
                  </h2>
                  <p
                    className="mx-auto mt-2 max-w-md text-sm"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    Contact our privacy team at{" "}
                    <a
                      href={`mailto:${CONTACT_EMAIL}`}
                      className="text-purple-400 hover:underline"
                    >
                      {CONTACT_EMAIL}
                    </a>
                    , or request removal of your data.
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="lg"
                  icon={<Trash2 className="h-4 w-4" />}
                  onClick={() => navigate("/data-deletion")}
                >
                  Data Deletion Instructions
                </Button>
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </section>
    </PublicLayout>
  );
}
