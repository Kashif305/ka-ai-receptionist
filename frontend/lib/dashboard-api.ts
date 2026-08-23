import type {
  DashboardAppointment,
  DashboardCustomer,
  DashboardStaff,
  DashboardSummary,
  ServiceOption,
  BusinessClosure,
  BusinessHour,
  DashboardConversation,
  DashboardClient,
  ClientDetail,
  PromotionCampaign,
  AnalyticsDashboard,
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

export function getBusinessHours() {
  return dashboardFetch<BusinessHour[]>("/dashboard/business-hours");
}

export function getBusinessClosures() {
  return dashboardFetch<BusinessClosure[]>("/dashboard/business-closures");
}

export function getDashboardConversations() {
  return dashboardFetch<DashboardConversation[]>("/dashboard/conversations");
}

export function getDashboardClients(search = "", status = "all") {
  const query = new URLSearchParams({ status });
  if (search) query.set("search", search);
  return dashboardFetch<DashboardClient[]>(`/dashboard/clients?${query}`);
}

export function getDashboardClient(clientId: number) {
  return dashboardFetch<ClientDetail>(`/dashboard/clients/${clientId}`);
}

export function getPromotions(search = "", status = "") {
  const query = new URLSearchParams();
  if (search) query.set("search", search);
  if (status) query.set("status", status);
  return dashboardFetch<PromotionCampaign[]>(`/dashboard/promotions?${query}`);
}

export function getPromotion(campaignId: number) {
  return dashboardFetch<PromotionCampaign>(`/dashboard/promotions/${campaignId}`);
}

export function getAnalytics(period = "last_30_days") {
  const query = new URLSearchParams({ period });
  return dashboardFetch<AnalyticsDashboard>(`/dashboard/analytics?${query}`);
}
