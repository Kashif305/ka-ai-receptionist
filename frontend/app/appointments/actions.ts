"use server";

import { revalidatePath } from "next/cache";

import type {
  AppointmentAvailability,
  AppointmentDetail,
} from "@/lib/dashboard-types";

const API_BASE_URL = (
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function request<T>(path: string, init?: RequestInit): Promise<ActionResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { detail?: string | Array<{ msg?: string }> }
        | null;
      const detail = Array.isArray(payload?.detail)
        ? payload.detail.map((item) => item.msg).filter(Boolean).join("; ")
        : payload?.detail;
      return { ok: false, error: detail || `Appointment request failed (${response.status})` };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, error: "Unable to connect to the appointment API." };
  }
}

function refreshDashboard() {
  revalidatePath("/appointments");
  revalidatePath("/");
}

export async function getAppointmentDetails(appointmentId: number) {
  return request<AppointmentDetail>(`/dashboard/appointments/${appointmentId}`);
}

export async function getRescheduleAvailability(appointmentId: number, date: string) {
  const query = new URLSearchParams({ date });
  return request<AppointmentAvailability>(
    `/dashboard/appointments/${appointmentId}/availability?${query}`,
  );
}

export async function cancelAppointment(appointmentId: number, reason: string) {
  const result = await request<AppointmentDetail>(
    `/dashboard/appointments/${appointmentId}/cancel`,
    { method: "POST", body: JSON.stringify({ reason: reason.trim() || null }) },
  );
  if (result.ok) refreshDashboard();
  return result;
}

export async function completeAppointment(appointmentId: number) {
  const result = await request<AppointmentDetail>(
    `/dashboard/appointments/${appointmentId}/complete`,
    { method: "POST" },
  );
  if (result.ok) refreshDashboard();
  return result;
}

export async function rescheduleAppointment(
  appointmentId: number,
  startAt: string,
  staffId: number,
  note: string,
) {
  const result = await request<AppointmentDetail>(
    `/dashboard/appointments/${appointmentId}/reschedule`,
    {
      method: "POST",
      body: JSON.stringify({
        start_at: startAt,
        staff_id: staffId,
        note: note.trim() || null,
      }),
    },
  );
  if (result.ok) refreshDashboard();
  return result;
}
