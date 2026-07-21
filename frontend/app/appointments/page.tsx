import { AppointmentsManager } from "@/components/appointments-manager";
import { DashboardShell } from "@/components/dashboard-shell";
import { getDashboardAppointments } from "@/lib/dashboard-api";

export default async function AppointmentsPage() {
  const appointments = await getDashboardAppointments();

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
        <AppointmentsManager appointments={appointments} />
      </section>
    </DashboardShell>
  );
}
