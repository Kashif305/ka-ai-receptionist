import { AnalyticsDashboard } from "@/components/analytics-dashboard";
import { DashboardShell } from "@/components/dashboard-shell";
import { getAnalytics } from "@/lib/dashboard-api";

const allowedPeriods = new Set(["today", "last_7_days", "last_30_days", "this_month"]);

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<{ period?: string }> }) {
  const requested = (await searchParams).period ?? "last_30_days";
  const period = allowedPeriods.has(requested) ? requested : "last_30_days";
  const data = await getAnalytics(period);
  return <DashboardShell title="Analytics" description="A practical view of salon activity and outreach."><AnalyticsDashboard data={data} /></DashboardShell>;
}
