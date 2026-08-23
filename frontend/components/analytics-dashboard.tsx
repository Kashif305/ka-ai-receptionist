import Link from "next/link";
import type { AnalyticsDashboard as AnalyticsData } from "@/lib/dashboard-types";

const periods = [
  ["today", "Today"], ["last_7_days", "Last 7 Days"],
  ["last_30_days", "Last 30 Days"], ["this_month", "This Month"],
] as const;

function number(value: number) { return value.toLocaleString("en-US"); }
function rate(value: number | null) { return value === null ? "—" : `${value.toFixed(1)}%`; }
function money(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function Empty({ children }: { children: string }) {
  return <p className="rounded-xl bg-slate-50 p-5 text-sm text-slate-500">{children}</p>;
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <h2 className="text-lg font-bold">{title}</h2><p className="mt-1 text-sm text-slate-500">{description}</p>
    <div className="mt-5">{children}</div>
  </section>;
}

function RankedRows({ rows }: { rows: Array<{ key: string | number; name: string; total: number; completed: number; note?: string }> }) {
  if (!rows.length) return <Empty>No appointment activity in this period.</Empty>;
  const max = Math.max(...rows.map((row) => row.total), 1);
  return <div className="space-y-4">{rows.map((row) => <article key={row.key}>
    <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
      <p className="font-semibold">{row.name} {row.note && <span className="font-normal text-slate-500">({row.note})</span>}</p>
      <p><strong>{number(row.total)}</strong> appointments · {number(row.completed)} completed</p>
    </div>
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" aria-hidden="true"><div className="h-full rounded-full bg-slate-800" style={{ width: `${row.total / max * 100}%` }} /></div>
  </article>)}</div>;
}

export function AnalyticsDashboard({ data }: { data: AnalyticsData }) {
  const cards = [
    ["Total appointments", number(data.overview.total_appointments)], ["Confirmed", number(data.overview.confirmed_appointments)],
    ["Completed", number(data.overview.completed_appointments)], ["Cancelled", number(data.overview.cancelled_appointments)],
    ["Cancellation rate", rate(data.overview.cancellation_rate)], ["New clients", number(data.overview.new_clients)],
    ["Returning clients", number(data.overview.returning_clients)], ["Completed service value", money(data.value.completed_service_value)],
  ];
  const promotionCards = [
    ["Campaigns", data.promotions.campaigns_created], ["Recipients", data.promotions.campaign_recipients],
    ["Submitted", data.promotions.submitted], ["Sent", data.promotions.sent], ["Delivered", data.promotions.delivered],
    ["Read", data.promotions.read], ["Replied", data.promotions.replied], ["Failed", data.promotions.failed],
  ];
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <nav aria-label="Analytics period" className="flex flex-wrap gap-2">{periods.map(([key, label]) => <Link key={key} href={`/analytics?period=${key}`} aria-current={data.period.key === key ? "page" : undefined} className={`rounded-lg px-4 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-slate-500 ${data.period.key === key ? "bg-slate-950 text-white" : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}>{label}</Link>)}</nav>
      <p className="text-sm text-slate-500">{data.period.start_date} – {data.period.end_date} · {data.period.timezone}</p>
    </div>
    <section aria-labelledby="overview-heading"><h2 id="overview-heading" className="sr-only">Overview</h2><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([label, value]) => <article key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-3 text-2xl font-bold">{value}</p></article>)}</div></section>
    <div className="grid gap-6 xl:grid-cols-2">
      <Section title="Services" description={data.services.most_booked_service ? `Most booked: ${data.services.most_booked_service.service_name}` : "No most-booked service for this period."}><RankedRows rows={data.services.rows.map((row) => ({ key: row.service_id, name: row.service_name, total: row.appointment_count, completed: row.completed_count, note: row.active ? undefined : "inactive" }))} /></Section>
      <Section title="Staff coverage" description="Scheduling volume only; this is not a performance score."><RankedRows rows={data.staff.map((row) => ({ key: row.staff_id ?? "unassigned", name: row.staff_name, total: row.appointment_count, completed: row.completed_count, note: `${row.upcoming_count} upcoming${row.active === false ? ", inactive" : ""}` }))} /></Section>
      <Section title="Clients" description="Canonical client records are used where available, with historical customer links retained."><div className="grid grid-cols-2 gap-3">{[["New", data.clients.new_clients], ["Returning", data.clients.returning_clients], ["Unique active", data.clients.unique_clients], ["Repeat clients", data.clients.repeat_clients]].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-4"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold">{number(value as number)}</p></div>)}</div>{data.clients.unique_clients === 0 && <p className="mt-4 text-sm text-slate-500">No non-cancelled client activity in this period.</p>}</Section>
      <Section title="Promotions" description="Provider submission and delivery are reported separately.">{data.promotions.campaigns_created === 0 ? <Empty>No campaigns were created in this period.</Empty> : <><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{promotionCards.map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-bold">{number(value as number)}</p></div>)}</div><p className="mt-4 text-sm text-slate-600">Delivery {rate(data.promotions.delivery_rate)} · Read {rate(data.promotions.read_rate)} · Reply {rate(data.promotions.reply_rate)}</p></>}</Section>
      <Section title="Coupons" description={`${number(data.coupons.active_coupons)} coupons are currently usable.`}>{data.coupons.rows.length === 0 ? <Empty>No coupon redemptions in this period.</Empty> : <div className="space-y-3">{data.coupons.rows.map((row) => <div key={row.coupon_id} className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="font-mono font-semibold">{row.code}</span><span>{number(row.redemption_count)} redemptions</span></div>)}</div>}</Section>
      <Section title="Metric definitions" description="How the dashboard calculates each number."><dl className="space-y-4">{Object.entries(data.definitions).map(([key, definition]) => <div key={key}><dt className="text-sm font-semibold capitalize">{key.replaceAll("_", " ")}</dt><dd className="mt-1 text-sm leading-6 text-slate-600">{definition}</dd></div>)}</dl></Section>
    </div>
  </div>;
}
