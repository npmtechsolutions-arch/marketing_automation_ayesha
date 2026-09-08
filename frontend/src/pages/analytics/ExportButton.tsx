import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { showError } from "@/components/ui/Toast";
import { downloadAnalyticsCsv, type AnalyticsView } from "@/lib/analytics";
import { type DateRangeValue } from "@/components/shared/DateRangeFilter";

/**
 * CSV export for one view.
 *
 * It exports *this* view with *this* window and *these* sort options -- the
 * same query the table above it was drawn from, plus `format=csv`. An export
 * button that quietly widened the range or dropped the sort would produce a
 * spreadsheet that disagrees with the screen it came from.
 */
export function ExportButton({
  accountId,
  view,
  range,
  extra,
  disabled,
}: {
  accountId: string | null;
  view: AnalyticsView;
  range: DateRangeValue;
  extra?: Record<string, string>;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);

  return (
    <Button
      variant="secondary"
      size="sm"
      loading={busy}
      disabled={disabled || !accountId}
      icon={<Download className="h-3.5 w-3.5" />}
      onClick={async () => {
        if (!accountId) return;
        setBusy(true);
        try {
          await downloadAnalyticsCsv(accountId, view, range, extra);
        } catch {
          showError("Export failed — could not download the CSV.");
        } finally {
          setBusy(false);
        }
      }}
    >
      CSV
    </Button>
  );
}

export default ExportButton;
