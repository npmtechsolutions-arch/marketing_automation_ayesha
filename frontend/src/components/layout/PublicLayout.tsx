import { useState, useEffect, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Menu, X, Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";

interface PublicLayoutProps {
  children: ReactNode;
}

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "Pricing", href: "/pricing" },
  { label: "About", href: "/about" },
];

const footerColumns = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "#features" },
      { label: "Pricing", href: "/pricing" },
      { label: "Integrations", href: "#integrations" },
      { label: "Changelog", href: "/changelog" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Blog", href: "/blog" },
      { label: "Careers", href: "/careers" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Documentation", href: "/docs" },
      { label: "Help Center", href: "/help" },
      { label: "API Reference", href: "/api" },
      { label: "Community", href: "/community" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", href: "/privacy" },
      { label: "Data Deletion", href: "/data-deletion" },
      { label: "Terms", href: "/terms" },
      { label: "Cookie Policy", href: "/cookies" },
    ],
  },
];

export default function PublicLayout({ children }: PublicLayoutProps) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const { theme, toggleTheme } = useUIStore();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className={cn(theme === "dark" ? "public-dark" : "public-light", "min-h-screen")}>
      {/* Navbar */}
      <motion.nav
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="fixed inset-x-0 top-0 z-50 transition-all duration-300"
        style={{
          backgroundColor: scrolled ? "var(--topbar-bg)" : "transparent",
          borderBottom: scrolled ? "1px solid var(--surface-border)" : "none",
          backdropFilter: scrolled ? "blur(16px)" : "none",
          WebkitBackdropFilter: scrolled ? "blur(16px)" : "none",
        }}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5">
            <img
              src="/marketengine_logo.png"
              alt="MarketEngine AI"
              className="h-9 w-9 rounded-lg object-cover shadow-lg shadow-purple-500/20"
            />
            <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-lg font-bold text-transparent">
              MarketEngine
            </span>
          </Link>

          {/* Desktop nav links */}
          <div className="hidden items-center gap-8 md:flex">
            {navLinks.map((link) =>
              link.href.startsWith("#") ? (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-sm transition-colors font-medium"
                  style={{ color: "var(--page-text-secondary)" }}
                  onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                  onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-secondary)"}
                >
                  {link.label}
                </a>
              ) : (
                <Link
                  key={link.label}
                  to={link.href}
                  className="text-sm transition-colors font-medium"
                  style={{ color: "var(--page-text-secondary)" }}
                  onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                  onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-secondary)"}
                >
                  {link.label}
                </Link>
              )
            )}
          </div>

          {/* Right buttons */}
          <div className="hidden items-center gap-3 md:flex">
            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              className="flex h-9 w-9 items-center justify-center rounded-lg transition-colors cursor-pointer"
              style={{ color: "var(--page-text-secondary)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = "rgba(124, 58, 237, 0.08)";
                e.currentTarget.style.color = "var(--page-heading)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = "transparent";
                e.currentTarget.style.color = "var(--page-text-secondary)";
              }}
            >
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>

            <button
              onClick={() => navigate("/login")}
              className="rounded-lg px-4 py-2 text-sm font-medium transition-colors"
              style={{ color: "var(--page-text-secondary)" }}
              onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
              onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-secondary)"}
            >
              Login
            </button>
            <button
              onClick={() => navigate("/register")}
              className="rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-purple-500/20 transition-all hover:shadow-purple-500/30 hover:brightness-110 active:scale-95"
            >
              Get Started Free
            </button>
          </div>

          {/* Mobile menu toggle & Theme toggle */}
          <div className="flex items-center gap-1 md:hidden">
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="flex h-9 w-9 items-center justify-center rounded-lg"
              style={{ color: "var(--page-text-secondary)" }}
            >
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            <button
              className="rounded-lg p-2"
              style={{ color: "var(--page-text-secondary)" }}
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? (
                <X className="h-5 w-5" style={{ color: "var(--page-heading)" }} />
              ) : (
                <Menu className="h-5 w-5" style={{ color: "var(--page-heading)" }} />
              )}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="border-t backdrop-blur-xl md:hidden"
            style={{
              backgroundColor: "var(--dropdown-bg)",
              borderColor: "var(--surface-border)",
            }}
          >
            <div className="space-y-1 px-4 py-4">
              {navLinks.map((link) =>
                link.href.startsWith("#") ? (
                  <a
                    key={link.label}
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-lg px-3 py-2 text-sm transition-colors"
                    style={{ color: "var(--page-text-secondary)" }}
                    onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                    onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-secondary)"}
                  >
                    {link.label}
                  </a>
                ) : (
                  <Link
                    key={link.label}
                    to={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-lg px-3 py-2 text-sm transition-colors"
                    style={{ color: "var(--page-text-secondary)" }}
                    onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                    onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-secondary)"}
                  >
                    {link.label}
                  </Link>
                )
              )}
              <div className="mt-4 flex flex-col gap-2 pt-4 border-t" style={{ borderColor: "var(--surface-border)" }}>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    navigate("/login");
                  }}
                  className="rounded-lg px-3 py-2 text-left text-sm transition-colors"
                  style={{ color: "var(--page-text-secondary)" }}
                  onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                  onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-secondary)"}
                >
                  Login
                </button>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    navigate("/register");
                  }}
                  className="rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 px-4 py-2 text-sm font-medium text-white"
                >
                  Get Started Free
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </motion.nav>

      {/* Main content */}
      <main>{children}</main>

      {/* Footer */}
      <footer className="border-t" style={{ backgroundColor: "var(--sidebar-bg)", borderColor: "var(--surface-border)" }}>
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4 lg:grid-cols-5">
            {/* Brand column */}
            <div className="col-span-2 md:col-span-4 lg:col-span-1">
              <div className="flex items-center gap-2.5">
                <img
                  src="/marketengine_logo.png"
                  alt="MarketEngine AI"
                  className="h-8 w-8 rounded-lg object-cover"
                />
                <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-lg font-bold text-transparent">
                  MarketEngine
                </span>
              </div>
              <p className="mt-4 max-w-xs text-sm leading-relaxed" style={{ color: "var(--page-text-muted)" }}>
                AI-powered marketing automation that helps teams create, schedule, and optimize content across all platforms.
              </p>
            </div>

            {/* Link columns */}
            {footerColumns.map((col) => (
              <div key={col.title}>
                <h3 className="mb-4 text-sm font-semibold" style={{ color: "var(--page-heading)" }}>
                  {col.title}
                </h3>
                <ul className="space-y-2.5">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      {link.href.startsWith("#") ? (
                        <a
                          href={link.href}
                          className="text-sm transition-colors"
                          style={{ color: "var(--page-text-muted)" }}
                          onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                          onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-muted)"}
                        >
                          {link.label}
                        </a>
                      ) : (
                        <Link
                          to={link.href}
                          className="text-sm transition-colors"
                          style={{ color: "var(--page-text-muted)" }}
                          onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                          onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-muted)"}
                        >
                          {link.label}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t pt-8 md:flex-row" style={{ borderColor: "var(--surface-border)" }}>
            <p className="text-sm" style={{ color: "var(--page-text-muted)" }}>
              &copy; {new Date().getFullYear()} MarketEngine. All rights reserved.
            </p>
            <div className="flex gap-6">
              <a
                href="#"
                className="text-sm transition-colors"
                style={{ color: "var(--page-text-muted)" }}
                onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-muted)"}
              >
                Twitter
              </a>
              <a
                href="#"
                className="text-sm transition-colors"
                style={{ color: "var(--page-text-muted)" }}
                onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-muted)"}
              >
                LinkedIn
              </a>
              <a
                href="#"
                className="text-sm transition-colors"
                style={{ color: "var(--page-text-muted)" }}
                onMouseEnter={(e) => e.currentTarget.style.color = "var(--page-heading)"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--page-text-muted)"}
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
