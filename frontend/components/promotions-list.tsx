/* eslint-disable @next/next/no-img-element -- campaign media hosts are runtime-configurable */
import Link from "next/link";
import type { PromotionCampaign } from "@/lib/dashboard-types";

const statuses = ["", "draft", "scheduled", "sending", "completed", "partially_completed", "failed", "cancelled"];
export function PromotionsList({ campaigns, search, status }: { campaigns: PromotionCampaign[]; search: string; status: string }) {
  return <div className="space-y-5">
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
      <form className="flex flex-1 gap-2"><input name="search" defaultValue={search} placeholder="Search promotions" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2"/><select name="status" defaultValue={status} className="rounded-lg border border-slate-300 px-3 py-2">{statuses.map((value) => <option key={value} value={value}>{value ? value.replaceAll("_", " ") : "All statuses"}</option>)}</select><button className="rounded-lg bg-slate-900 px-4 py-2 text-white">Filter</button></form>
      <Link href="/promotions/new" className="rounded-lg bg-emerald-600 px-4 py-2 text-center font-semibold text-white">Create Promotion</Link>
    </div>
    {campaigns.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center"><p className="font-semibold">No promotions yet</p><p className="mt-1 text-sm text-slate-500">Create a consent-based WhatsApp offer when you are ready.</p></div> :
      <div className="grid gap-4 xl:grid-cols-2">{campaigns.map((campaign) => <Link href={`/promotions/${campaign.id}`} key={campaign.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white transition hover:border-slate-400">
        <div className="flex gap-4 p-5">{campaign.flyer_url ? <img src={campaign.flyer_url} alt="" className="h-20 w-20 rounded-xl object-cover"/> : <div className="flex h-20 w-20 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">No flyer</div>}<div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">{campaign.name}</h2><p className="mt-1 truncate text-sm text-slate-500">{campaign.headline || campaign.body_text}</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize">{campaign.status.replaceAll("_", " ")}</span></div><p className="mt-3 text-xs text-slate-500">{campaign.audience_type.replaceAll("_", " ")} · {campaign.scheduled_at ? new Date(campaign.scheduled_at).toLocaleString() : campaign.completed_at ? `Sent ${new Date(campaign.completed_at).toLocaleString()}` : "Not scheduled"}</p></div></div>
        <div className="grid grid-cols-4 border-t border-slate-100 bg-slate-50 px-5 py-3 text-center text-xs"><span><b className="block text-base">{Object.values(campaign.recipient_counts).reduce((a,b)=>a+b,0)}</b>Recipients</span><span><b className="block text-base">{campaign.recipient_counts.submitted || 0}</b>Submitted</span><span><b className="block text-base">{campaign.recipient_counts.delivered || 0}</b>Delivered</span><span><b className="block text-base text-red-600">{campaign.recipient_counts.failed || 0}</b>Failed</span></div>
      </Link>)}</div>}
  </div>;
}
