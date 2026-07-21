import { DashboardShell } from "@/components/dashboard-shell";
import { StaffManager } from "@/components/staff-manager";
import { getDashboardStaff, getServices } from "@/lib/dashboard-api";

export default async function StaffPage() {
  const [staffMembers, services] = await Promise.all([
    getDashboardStaff(),
    getServices(),
  ]);

  return (
    <DashboardShell
      title="Staff"
      description="Manage staff members, services and working hours."
    >
      <StaffManager
        initialStaff={staffMembers}
        services={services.filter((service) => service.active)}
      />
    </DashboardShell>
  );
}
