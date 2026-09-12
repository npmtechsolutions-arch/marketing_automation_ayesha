/**
 * A table on a white card.
 *
 * New in the redesign's foundation slice, and deliberately additive: the app
 * has fifteen hand-rolled `<table>` blocks (admin, billing, analytics tabs,
 * team, reports) which each style their own header row, and they migrate in
 * the page slices rather than here. Nothing is forced to adopt it today.
 *
 * The pieces are plain wrappers over the native elements, so sorting,
 * selection and keyboard behaviour stay wherever the page already implements
 * them — this is a skin, not a data grid.
 */
import { type ReactNode, type ThHTMLAttributes, type TdHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { metricText } from "@/lib/stats";

export function Table({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    // The scroll container is the card edge, so a wide table clips to the
    // radius instead of spilling past it.
    <div
      className="w-full overflow-x-auto"
      style={{
        border: "1px solid var(--surface-border)",
        borderRadius: "var(--surface-radius)",
        backgroundColor: "var(--surface-bg)",
      }}
    >
      <table className={cn("w-full border-collapse text-sm", className)}>
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead
      style={{
        backgroundColor: "var(--sidebar-hover-bg)",
        borderBottom: "1px solid var(--surface-border)",
      }}
    >
      {children}
    </thead>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TR({
  children,
  className,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "transition-colors",
        // Hairlines between rows rather than zebra striping: on a white card
        // the stripe is another surface colour competing with the canvas.
        "[&:not(:last-child)]:border-b [&:not(:last-child)]:border-[color:var(--surface-border)]",
        onClick && "cursor-pointer hover:bg-[color:var(--accent-soft)]",
        className
      )}
    >
      {children}
    </tr>
  );
}

export function TH({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn(
        // The small uppercase marker, used as a column label.
        "px-5 py-3.5 text-left text-eyebrow font-semibold uppercase",
        className
      )}
      style={{ color: "var(--page-text-muted)" }}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TD({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn("px-5 py-4 align-middle", className)}
      style={{ color: "var(--page-text)" }}
      {...rest}
    >
      {children}
    </td>
  );
}

/**
 * A cell for a measurement, rendering absence as an em dash.
 *
 * Not decoration: null means "not measured" everywhere in this product, and a
 * table that prints 0 for it is the defect Walk B found on the dashboard. The
 * dash lives here so a page cannot forget it while laying out a new column.
 */
export function TDMetric({
  value,
  format,
  className,
  ...rest
}: {
  value: number | null | undefined;
  format?: (n: number) => string;
  className?: string;
} & TdHTMLAttributes<HTMLTableCellElement>) {
  // The rule itself lives in src/lib/stats.ts and is pinned by tests; this
  // only decides how the dash looks. Two copies of "what counts as measured"
  // is how one of them drifts.
  const text = metricText(value, format);
  const measured = text !== "—";
  return (
    <TD className={cn("tabular-nums", className)} {...rest}>
      {measured ? (
        text
      ) : (
        <span style={{ color: "var(--page-text-muted)" }} title="Not measured">
          {text}
        </span>
      )}
    </TD>
  );
}
