type DashboardCardProps = {
  label: string;
  value: number;
  detail: string;
};

export function DashboardCard({ label, value, detail }: DashboardCardProps) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-4 text-3xl font-bold tracking-tight">
        {value.toLocaleString("en-US")}
      </p>
      <p className="mt-2 text-sm text-slate-500">{detail}</p>
    </article>
  );
}
