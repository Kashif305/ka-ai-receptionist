import { BusinessHoursManager } from "@/components/business-hours-manager";
import { DashboardShell } from "@/components/dashboard-shell";
import { getBusinessClosures, getBusinessHours } from "@/lib/dashboard-api";

export default async function BusinessHoursPage() {
  const [hours, closures] = await Promise.all([
    getBusinessHours(),
    getBusinessClosures(),
  ]);

  return (
    <DashboardShell
      title="Business Hours"
      description="Manage weekly opening hours and temporary closures."
    >
      <BusinessHoursManager initialHours={hours} initialClosures={closures} />
    </DashboardShell>
  );
}
