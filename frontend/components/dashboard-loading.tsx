import { DashboardShell } from "@/components/dashboard-shell";

type DashboardLoadingProps = {
  title: string;
  description: string;
};

export function DashboardLoading({ title, description }: DashboardLoadingProps) {
  return (
    <DashboardShell title={title} description={description}>
      <div className="space-y-4" aria-busy="true" aria-label="Loading dashboard data">
        <div className="h-28 rounded-2xl border border-slate-200 bg-white shadow-sm" />
        <div className="h-80 rounded-2xl border border-slate-200 bg-white shadow-sm" />
      </div>
    </DashboardShell>
  );
}
