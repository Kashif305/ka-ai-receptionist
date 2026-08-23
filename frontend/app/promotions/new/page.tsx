import { DashboardShell } from "@/components/dashboard-shell";
import { PromotionForm } from "@/components/promotion-form";
import { getDashboardClients, getServices } from "@/lib/dashboard-api";
export default async function NewPromotionPage() { const [clients, services] = await Promise.all([getDashboardClients("", "all"), getServices()]); return <DashboardShell title="Create Promotion" description="Build the offer, audience, and delivery plan."><PromotionForm clients={clients} services={services}/></DashboardShell>; }
