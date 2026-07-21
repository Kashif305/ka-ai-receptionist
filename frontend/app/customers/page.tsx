import { DashboardShell } from "@/components/dashboard-shell";
import { EmptyState } from "@/components/empty-state";
import { getDashboardCustomers } from "@/lib/dashboard-api";
import { formatDate } from "@/lib/formatters";

export default async function CustomersPage() {
  const customers = await getDashboardCustomers();

  return (
    <DashboardShell
      title="Customers"
      description="View customers who interact with Samina Receptionist."
    >
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 p-5">
          <h2 className="font-bold">Customer Directory</h2>
          <p className="mt-1 text-sm text-slate-500">
            Names, phone numbers and appointment activity.
          </p>
        </div>

        {customers.length === 0 ? (
          <EmptyState
            icon="♙"
            title="No customers"
            description="Customers will appear here after their first interaction."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">Customer</th>
                  <th className="px-5 py-3 font-semibold">Phone</th>
                  <th className="px-5 py-3 font-semibold">Visits</th>
                  <th className="px-5 py-3 font-semibold">Upcoming</th>
                  <th className="px-5 py-3 font-semibold">Last Visit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((customer) => (
                  <tr key={customer.id}>
                    <td className="px-5 py-4 font-medium">{customer.name}</td>
                    <td className="px-5 py-4 text-slate-600">{customer.phone}</td>
                    <td className="px-5 py-4 text-slate-600">
                      {customer.appointment_count}
                    </td>
                    <td className="px-5 py-4 text-slate-600">
                      {customer.upcoming_appointment_count}
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                      {customer.last_appointment_at
                        ? formatDate(customer.last_appointment_at)
                        : "No visits yet"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </DashboardShell>
  );
}
