import { DashboardShell } from "@/components/dashboard-shell";
import { PromotionsList } from "@/components/promotions-list";
import { getPromotions } from "@/lib/dashboard-api";
export default async function PromotionsPage({ searchParams }: { searchParams: Promise<{ search?: string; status?: string }> }) {
  const params = await searchParams; const search = params.search || ""; const status = params.status || "";
  const campaigns = await getPromotions(search, status);
  return <DashboardShell title="Promotions" description="Create targeted, consent-based WhatsApp campaigns and review delivery."><PromotionsList campaigns={campaigns} search={search} status={status}/></DashboardShell>;
}
