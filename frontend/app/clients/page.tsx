import { ClientsManager } from "@/components/clients-manager";
import { DashboardShell } from "@/components/dashboard-shell";
import { getDashboardClients } from "@/lib/dashboard-api";

export default async function ClientsPage({ searchParams }: { searchParams: Promise<{ search?: string; status?: string }> }) {
  const params = await searchParams; const search = params.search || ""; const status = params.status || "all";
  const clients = await getDashboardClients(search, status);
  return <DashboardShell title="Clients" description="Your central customer directory and activity history."><ClientsManager clients={clients} search={search} status={status} /></DashboardShell>;
}
