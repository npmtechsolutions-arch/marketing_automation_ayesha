import { useNavigate } from "react-router-dom";
import { motion, type Variants } from "framer-motion";
import {
  FileText,
  UserCheck,
  ShieldCheck,
  DollarSign,
  AlertTriangle,
  RefreshCw,
  XCircle,
  HelpCircle,
  Globe,
  Gavel,
  Mail,
  ExternalLink,
} from "lucide-react";
import PublicLayout from "@/components/layout/PublicLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

/* ------------------------------------------------------------------ */
/*  Config                                                             */
/* ------------------------------------------------------------------ */

const COMPANY = "MarketEngine";
const CONTACT_EMAIL = "legal@marketengine.ai";
const LAST_UPDATED = "July 27, 2026";

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
    id: "acceptance-of-terms",
    icon: UserCheck,
    title: "1. Acceptance of Terms",
    body: (
      <>
        <p>
          By creating an account, accessing, or using {COMPANY} (the "Service"),
          you agree to be bound by these Terms of Service ("Terms"). If you do
          not agree to these Terms, you may not access or use the Service.
        </p>
        <p>
          If you are entering into these Terms on behalf of a company, organization, 
          or other legal entity, you represent and warrant that you have the authority 
          to bind such entity to these Terms.
        </p>
      </>
    ),
  },
  {
    id: "account-terms",
    icon: ShieldCheck,
    title: "2. Account Registration and Security",
    body: (
      <>
        <p>To use most features of the Service, you must register for an account:</p>
        <ul>
          <li>You must provide accurate, current, and complete registration details.</li>
          <li>You are responsible for maintaining the security of your login credentials.</li>
          <li>You are fully responsible for all activities that occur under your account.</li>
          <li>You must notify us immediately of any unauthorized use or security breach.</li>
        </ul>
      </>
    ),
  },
  {
    id: "content-guidelines",
    icon: FileText,
    title: "3. Content and Use Guidelines",
    body: (
      <>
        <p>
          You retain all ownership rights to the content, text, images, and videos 
          you upload, generate, or publish using the Service. However, you grant 
          us a limited, worldwide license to host, store, and process your content 
          solely to provide the Service.
        </p>
        <p>You agree not to use the Service to upload, generate, or publish content that:</p>
        <ul>
          <li>Is unlawful, harmful, threatening, abusive, harassing, or defamatory.</li>
          <li>Infringes upon any third-party intellectual property or privacy rights.</li>
          <li>Contains viruses, malicious code, or software designed to disrupt the Service.</li>
          <li>Violates the terms of service of any connected social media platform.</li>
        </ul>
      </>
    ),
  },
  {
    id: "third-party-integrations",
    icon: Globe,
    title: "4. Third-Party Integrations",
    body: (
      <>
        <p>
          {COMPANY} allows you to connect third-party platforms (including but not limited 
          to Meta/Facebook/Instagram, LinkedIn, X/Twitter, and Google/YouTube) to publish 
          and manage your content.
        </p>
        <p>
          By connecting any third-party platform, you agree to comply with their respective 
          terms and conditions:
        </p>
        <ul>
          <li>
            <strong>YouTube/Google:</strong> By connecting a YouTube channel, you agree to be bound by the{" "}
            <a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:underline inline-flex items-center gap-1">
              YouTube Terms of Service <ExternalLink className="h-3 w-3" />
            </a>.
          </li>
          <li>
            <strong>Other Platforms:</strong> You must comply with Meta's Terms of Service, LinkedIn's User Agreement, and X's Terms of Service.
          </li>
        </ul>
        <p>
          We are not responsible for the availability, features, or policies of any 
          third-party platform. You can disconnect your social media accounts at any 
          time from your settings.
        </p>
      </>
    ),
  },
  {
    id: "ai-features",
    icon: HelpCircle,
    title: "5. AI Features and content",
    body: (
      <>
        <p>
          Our Service includes AI features to help generate marketing strategies, 
          social media posts, and captions.
        </p>
        <ul>
          <li>AI-generated content is provided for informational and draft purposes only.</li>
          <li>You are solely responsible for reviewing and verifying the accuracy and appropriateness of any AI-generated output before publishing it.</li>
          <li>We do not guarantee the uniqueness, accuracy, or suitability of AI-generated content.</li>
        </ul>
      </>
    ),
  },
  {
    id: "billing",
    icon: DollarSign,
    title: "6. Subscription Fees, Billing, and Refunds",
    body: (
      <>
        <p>Some parts of the Service are billed on a subscription basis:</p>
        <ul>
          <li>You will be billed in advance on a recurring monthly or annual basis depending on your plan.</li>
          <li>Payments are processed securely via our payment processor (Stripe).</li>
          <li>You may cancel your subscription at any time. Your access will continue until the end of your billing cycle.</li>
          <li>Except as required by law, subscription fees are non-refundable.</li>
        </ul>
      </>
    ),
  },
  {
    id: "termination",
    icon: XCircle,
    title: "7. Termination and Suspension",
    body: (
      <p>
        We reserve the right to suspend or terminate your account and access to 
        the Service immediately, without prior notice or liability, if you breach 
        these Terms. Upon termination, your right to use the Service will cease immediately, 
        and you may lose access to your data.
      </p>
    ),
  },
  {
    id: "warranty-disclaimer",
    icon: AlertTriangle,
    title: "8. Disclaimer of Warranties",
    body: (
      <p>
        The Service is provided on an "AS IS" and "AS AVAILABLE" basis. {COMPANY} 
        makes no representations or warranties of any kind, express or implied, 
        as to the operation of the Service, the accuracy of content, or that the 
        Service will be uninterrupted, secure, or error-free.
      </p>
    ),
  },
  {
    id: "limitation-of-liability",
    icon: Gavel,
    title: "9. Limitation of Liability",
    body: (
      <p>
        To the maximum extent permitted by law, {COMPANY} shall not be liable 
        for any indirect, incidental, special, consequential, or punitive damages, 
        including loss of profits, data, use, or goodwill, arising out of your 
        access to or use of the Service. Our total liability for any claim under 
        these terms is limited to the amount paid by you to us in the 12 months 
        preceding the claim.
      </p>
    ),
  },
  {
    id: "changes",
    icon: RefreshCw,
    title: "10. Changes to Terms",
    body: (
      <p>
        We reserve the right to modify these Terms at any time. When we make 
        changes, we will update the "Last updated" date at the top. Your continued 
        use of the Service after any changes constitutes acceptance of the new Terms.
      </p>
    ),
  },
];

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function TermsOfServicePage() {
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
              <FileText className="mr-1.5 inline h-3.5 w-3.5" />
              Terms and Conditions
            </Badge>
            <h1
              className="text-4xl font-extrabold tracking-tight sm:text-5xl"
              style={{ color: "var(--page-heading)" }}
            >
              Terms of Service
            </h1>
            <p
              className="mx-auto mt-4 max-w-xl text-lg"
              style={{ color: "var(--page-text-secondary)" }}
            >
              Please read these Terms of Service carefully before using the {COMPANY} platform.
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
                These Terms of Service govern your access to and use of {COMPANY}'s website, 
                services, applications, and APIs. By using our services, you agree to these 
                terms. If you do not agree, please do not access or use the platform.
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
                    Questions about our terms?
                  </h2>
                  <p
                    className="mx-auto mt-2 max-w-md text-sm"
                    style={{ color: "var(--page-text-secondary)" }}
                  >
                    If you have any questions or concerns about these Terms of Service, 
                    please contact us at{" "}
                    <a
                      href={`mailto:${CONTACT_EMAIL}`}
                      className="text-purple-400 hover:underline"
                    >
                      {CONTACT_EMAIL}
                    </a>.
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="lg"
                  onClick={() => navigate("/about")}
                >
                  Learn About Us
                </Button>
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </section>
    </PublicLayout>
  );
}
