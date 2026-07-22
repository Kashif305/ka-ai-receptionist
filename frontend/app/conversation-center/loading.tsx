import { DashboardShell } from "@/components/dashboard-shell";

export default function ConversationCenterLoading() {
  return (
    <DashboardShell title="Conversation Center" description="Loading WhatsApp conversations…">
      <div role="status" className="grid min-h-[36rem] animate-pulse gap-4 lg:grid-cols-[22rem_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5"><div className="h-10 rounded-lg bg-slate-100" /><div className="mt-5 space-y-3">{[1,2,3,4].map((item) => <div key={item} className="h-24 rounded-xl bg-slate-100" />)}</div></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6"><div className="h-8 w-52 rounded bg-slate-100" /><div className="mt-8 h-72 rounded-xl bg-slate-100" /></div>
        <span className="sr-only">Loading conversations</span>
      </div>
    </DashboardShell>
  );
}
