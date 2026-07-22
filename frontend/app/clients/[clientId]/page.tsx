import { ClientProfile } from "@/components/client-profile";
import { DashboardShell } from "@/components/dashboard-shell";
import { getDashboardClient } from "@/lib/dashboard-api";
export default async function ClientPage({ params }: { params: Promise<{ clientId: string }> }) { const { clientId } = await params; const client = await getDashboardClient(Number(clientId)); return <DashboardShell title={client.name} description="Client profile, activity, consent, and private notes."><ClientProfile initial={client}/></DashboardShell>; }
