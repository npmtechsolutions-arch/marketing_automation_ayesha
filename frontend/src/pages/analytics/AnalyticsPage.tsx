/**
 * Analytics.
 *
 * Four views over the same window: what happened overall, where it happened,
 * which posts did it, and how the audience moved. The window is chosen once,
 * at the top, with the shared DateRangeFilter -- the same component and the
 * same range vocabulary the dashboard uses, so "last 30 days" is one thing in
 * this product rather than four.
 *
 * Each tab fetches only when it is opened, and each has its own CSV export
 * that streams the identical query with `format=csv`.
 *
 * The previous version of this page drew a posting-time heatmap from
 * `Math.random()` and captioned it with a fixed "boost reach by up to 22%"
 * claim. Both are gone: fabricated numbers in an analytics product are worse
 * than an empty state, because a user cannot tell them from measurements.
 */
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FileText, Layers, RefreshCw, TrendingUp, Users } from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import DateRangeFilter, { type DateRangeValue } from "@/components/shared/DateRangeFilter";
import { showError } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";
import { getAccountId } from "@/lib/api";
import {
  fetchAnalytics,
  type AnalyticsView,
  type AudiencePayload,
  type OverviewPayload,
  type PlatformRow,
  type PostRow,
} from "@/lib/analytics";
import ExportButton from "./ExportButton";
import OverviewTab from "./tabs/OverviewTab";
import PlatformsTab from "./tabs/PlatformsTab";
import ContentTab, { type PostSort, type SortOrder } from "./tabs/ContentTab";
import AudienceTab from "./tabs/AudienceTab";

type TabKey = "overview" | "platforms" | "content" | "audience";

const TABS: { key: TabKey; view: AnalyticsView; label: string; icon: React.ReactNode }[] = [
  { key: "overview", view: "summary", label: "Overview", icon: <TrendingUp className="h-4 w-4" /> },
  { key: "platforms", view: "platforms", label: "Platforms", icon: <Layers className="h-4 w-4" /> },
  { key: "content", view: "posts", label: "Content", icon: <FileText className="h-4 w-4" /> },
  { key: "audience", view: "audience", label: "Audience", icon: <Users className="h-4 w-4" /> },
];

export default function AnalyticsPage() {
  const [accountId, setAccountId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [range, setRange] = useState<DateRangeValue>({ key: "30d" });

  const [sort, setSort] = useState<PostSort>("engagement");
  const [order, setOrder] = useState<SortOrder>("desc");

  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [platforms, setPlatforms] = useState<PlatformRow[]>([]);
  const [posts, setPosts] = useState<PostRow[]>([]);
  const [audience, setAudience] = useState<AudiencePayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAccountId().then(setAccountId);
  }, []);

  const active = TABS.find((t) => t.key === tab)!;
  // Sort belongs to the query, so the CSV and the table agree on ordering.
  const postParams = { sort, order, limit: "100" };

  const load = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      if (tab === "overview") {
        setOverview(await fetchAnalytics<OverviewPayload>(accountId, "summary", range));
      } else if (tab === "platforms") {
        const data = await fetchAnalytics<{ platforms: PlatformRow[] }>(
          accountId,
          "platforms",
          range
        );
        setPlatforms(data.platforms ?? []);
      } else if (tab === "content") {
        const data = await fetchAnalytics<{ posts: PostRow[] }>(
          accountId,
          "posts",
          range,
          postParams
        );
        setPosts(data.posts ?? []);
      } else {
        setAudience(await fetchAnalytics<AudiencePayload>(accountId, "audience", range));
      }
    } catch {
      showError("Could not load analytics — the request failed.");
    } finally {
      setLoading(false);
    }
    // postParams is derived from sort/order, which are in the dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, tab, range, sort, order]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--page-heading)" }}>
              Analytics
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--page-text-secondary)" }}>
              Measured nightly from each connected platform.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <DateRangeFilter value={range} onChange={setRange} />
            <button
              onClick={load}
              disabled={loading}
              title="Refresh"
              className="rounded-xl p-2 transition-colors disabled:opacity-50"
              style={{
                backgroundColor: "var(--sidebar-hover-bg)",
                color: "var(--page-text-secondary)",
              }}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </button>
            <ExportButton
              accountId={accountId}
              view={active.view}
              range={range}
              extra={tab === "content" ? postParams : undefined}
              disabled={loading}
            />
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-1 rounded-xl p-1"
          style={{
            backgroundColor: "var(--sidebar-hover-bg)",
            border: "1px solid var(--surface-border)",
          }}
        >
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all",
                tab === t.key
                  ? "bg-[rgba(109,94,246,0.14)] border border-[rgba(109,94,246,0.28)] shadow-sm"
                  : "hover:opacity-80"
              )}
              style={{
                color: tab === t.key ? "var(--page-heading)" : "var(--page-text-secondary)",
              }}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </motion.div>

        {tab === "overview" && <OverviewTab data={overview} loading={loading} />}
        {tab === "platforms" && <PlatformsTab rows={platforms} loading={loading} />}
        {tab === "content" && (
          <ContentTab
            rows={posts}
            loading={loading}
            sort={sort}
            order={order}
            onSortChange={(nextSort, nextOrder) => {
              setSort(nextSort);
              setOrder(nextOrder);
            }}
          />
        )}
        {tab === "audience" && <AudienceTab data={audience} loading={loading} />}
      </div>
    </DashboardLayout>
  );
}
