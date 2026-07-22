import { DashboardShell } from "@/components/dashboard-shell";
import { ServicesManager } from "@/components/services-manager";
import { getDashboardServices } from "@/lib/dashboard-api";

export default async function ServicesPage() {
  const services = await getDashboardServices();

  return (
    <DashboardShell title="Services" description="Manage the services customers can book.">
      <ServicesManager initialServices={services} />
    </DashboardShell>
  );
}
