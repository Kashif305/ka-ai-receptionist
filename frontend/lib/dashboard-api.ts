import type {
  DashboardAppointment,
  DashboardCustomer,
  DashboardStaff,
  DashboardSummary,
  ServiceOption,
} from "@/lib/dashboard-types";

const API_BASE_URL = (
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

async function dashboardFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(
      `Dashboard API request failed (${response.status} ${response.statusText})`,
    );
  }

  return (await response.json()) as T;
}

export function getDashboardSummary() {
  return dashboardFetch<DashboardSummary>("/dashboard/summary");
}

export function getDashboardAppointments() {
  return dashboardFetch<DashboardAppointment[]>("/dashboard/appointments");
}

export function getDashboardCustomers() {
  return dashboardFetch<DashboardCustomer[]>("/dashboard/customers");
}

export function getDashboardStaff() {
  return dashboardFetch<DashboardStaff[]>("/dashboard/staff");
}

export function getServices() {
  return dashboardFetch<ServiceOption[]>("/services");
}

export function getDashboardServices() {
  return dashboardFetch<ServiceOption[]>("/dashboard/services");
}
