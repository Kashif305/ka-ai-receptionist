import { AppointmentsManager } from "@/components/appointments-manager";
import { DashboardShell } from "@/components/dashboard-shell";
import { getDashboardAppointments, getDashboardStaff, getServices } from "@/lib/dashboard-api";

export default async function AppointmentsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const raw = await searchParams;
  const value = (key: string) => typeof raw[key] === "string" ? raw[key] : "";
  const filters = { search: value("search"), date: value("date"), service_id: value("service_id"), staff_id: value("staff_id"), time_of_day: value("time_of_day") };
  const [appointments, services, staff] = await Promise.all([
    getDashboardAppointments(filters), getServices(), getDashboardStaff(),
  ]);

  return (
    <DashboardShell
      title="Appointments"
      description="View salon bookings."
    >
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-5">
          <h2 className="font-bold">All Appointments</h2>
          <p className="mt-1 text-sm text-slate-500">
            Complete appointment records from Samina Receptionist.
          </p>
        </div>
        <AppointmentsManager appointments={appointments} services={services} staff={staff} filters={filters} />
      </section>
    </DashboardShell>
  );
}
