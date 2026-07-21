import Link from "next/link";
import { AppointmentsTable } from "@/components/appointments-table";
import { DashboardCard } from "@/components/dashboard-card";
import { DashboardShell } from "@/components/dashboard-shell";
import {
  getDashboardAppointments,
  getDashboardSummary,
} from "@/lib/dashboard-api";

export default async function DashboardPage() {
  const [summary, appointments] = await Promise.all([
    getDashboardSummary(),
    getDashboardAppointments(),
  ]);

  const summaryCards = [
    {
      label: "Today's Appointments",
      value: summary.today_appointments,
      detail: "Confirmed appointments today",
    },
    {
      label: "Upcoming Appointments",
      value: summary.upcoming_appointments,
      detail: "Confirmed upcoming appointments",
    },
    {
      label: "Customers",
      value: summary.total_customers,
      detail: "Registered customers",
    },
    {
      label: "Active Staff",
      value: summary.active_staff,
      detail: "Currently active staff members",
    },
  ];

  return (
    <DashboardShell
      title="Dashboard"
      description="Welcome back. Here is what is happening at the salon."
    >
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card) => (
          <DashboardCard key={card.label} {...card} />
        ))}
      </section>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 p-5">
          <div>
            <h2 className="font-bold">Recent Appointments</h2>
            <p className="mt-1 text-sm text-slate-500">
              Latest appointment activity
            </p>
          </div>
          <Link
            href="/appointments"
            className="text-sm font-semibold text-slate-900 hover:underline"
          >
            View all
          </Link>
        </div>
        <AppointmentsTable appointments={appointments.slice(0, 5)} />
      </section>
    </DashboardShell>
  );
}
