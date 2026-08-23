import { DashboardShell } from "@/components/dashboard-shell";
import { PromotionDetail } from "@/components/promotion-detail";
import { getPromotion } from "@/lib/dashboard-api";
export default async function PromotionPage({ params }: { params: Promise<{campaignId:string}> }) { const {campaignId}=await params; const campaign=await getPromotion(Number(campaignId)); return <DashboardShell title={campaign.name} description="Campaign configuration, coupon, audience, and delivery outcomes."><PromotionDetail campaign={campaign}/></DashboardShell>; }
