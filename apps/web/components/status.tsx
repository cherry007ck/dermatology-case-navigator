import { cn } from "@/lib/utils";

export type ChipTone = "neutral" | "info" | "warning" | "error" | "ok";

const tones: Record<ChipTone, string> = {
  neutral: "border-border bg-muted text-foreground",
  info: "border-primary/30 bg-secondary text-secondary-foreground",
  warning: "border-warning/40 bg-warning-surface text-warning-foreground",
  error: "border-destructive/40 bg-destructive/10 text-destructive",
  ok: "border-primary/40 bg-secondary text-secondary-foreground",
};

/** Accessible status chip: the text carries the meaning; colour only reinforces it. */
export function StatusChip({ tone = "neutral", children }: { tone?: ChipTone; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-sm border px-2.5 py-0.5 text-sm font-medium", tones[tone])}>
      {children}
    </span>
  );
}

/** Mono uppercase label with a navy marker, used to name a module ("Doctor workspace", "Case report"). */
export function ModuleLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("dcn-label", className)}>{children}</span>;
}

/** A grid module: bordered white surface with navy corner markers and a heading. */
export function Panel({
  title,
  children,
  className,
  headingLevel = 2,
  testId,
  action,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
  headingLevel?: 2 | 3;
  testId?: string;
  /** Optional element shown on the heading row, e.g. a count or a small control. */
  action?: React.ReactNode;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <section data-testid={testId} className={cn("dcn-module min-w-0 rounded-md border bg-card p-4 sm:p-6", className)}>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
        <Heading className="text-lg font-semibold">{title}</Heading>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Notice({ tone = "info", children }: { tone?: ChipTone; children: React.ReactNode }) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("rounded-md border px-4 py-3", tones[tone])}>
      {children}
    </div>
  );
}
