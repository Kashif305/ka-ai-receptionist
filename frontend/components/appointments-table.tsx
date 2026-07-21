import type { DashboardAppointment } from "@/lib/dashboard-types";
import { formatDate, formatLabel, formatTime } from "@/lib/formatters";
import { EmptyState } from "@/components/empty-state";

type AppointmentsTableProps = {
  appointments: DashboardAppointment[];
  emptyDescription?: string;
};

export function AppointmentsTable({
  appointments,
  emptyDescription = "Appointments will appear here when bookings are created.",
}: AppointmentsTableProps) {
  if (appointments.length === 0) {
    return (
      <EmptyState
        icon="◷"
        title="No appointments"
        description={emptyDescription}
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-5 py-3 font-semibold">Date</th>
            <th className="px-5 py-3 font-semibold">Time</th>
            <th className="px-5 py-3 font-semibold">Customer</th>
            <th className="px-5 py-3 font-semibold">Service</th>
            <th className="px-5 py-3 font-semibold">Staff</th>
            <th className="px-5 py-3 font-semibold">Status</th>
            <th className="px-5 py-3 font-semibold">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {appointments.map((appointment) => (
            <tr key={appointment.id}>
              <td className="whitespace-nowrap px-5 py-4 font-medium">
                {formatDate(appointment.start_at)}
              </td>
              <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                {formatTime(appointment.start_at)}
              </td>
              <td className="px-5 py-4">
                <p className="font-medium">{appointment.customer_name}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {appointment.customer_phone}
                </p>
              </td>
              <td className="px-5 py-4 text-slate-600">
                {appointment.service_name}
              </td>
              <td className="px-5 py-4 text-slate-600">
                {appointment.assigned_staff_name ?? "Unassigned"}
              </td>
              <td className="px-5 py-4">
                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                  {formatLabel(appointment.status)}
                </span>
              </td>
              <td className="px-5 py-4 text-slate-600">
                {formatLabel(appointment.source)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
