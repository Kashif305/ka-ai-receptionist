"use server";

import { revalidatePath } from "next/cache";

import type { ServiceInput } from "@/lib/dashboard-types";

const API_BASE_URL = (
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

export type ServiceActionResult = { ok: true } | { ok: false; error: string };

async function mutateService(
  path: string,
  method: "POST" | "PUT" | "PATCH",
  body: unknown,
): Promise<ServiceActionResult> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { detail?: string | Array<{ msg?: string }> }
        | null;
      const detail = Array.isArray(payload?.detail)
        ? payload.detail.map((item) => item.msg).filter(Boolean).join("; ")
        : payload?.detail;
      return { ok: false, error: detail || `Unable to save service (${response.status})` };
    }
    revalidatePath("/services");
    revalidatePath("/staff");
    return { ok: true };
  } catch {
    return { ok: false, error: "Unable to connect to the services API." };
  }
}

export async function createService(input: ServiceInput) {
  return mutateService("/dashboard/services", "POST", input);
}

export async function updateService(serviceId: number, input: ServiceInput) {
  return mutateService(`/dashboard/services/${serviceId}`, "PUT", input);
}

export async function setServiceActive(serviceId: number, active: boolean) {
  return mutateService(`/dashboard/services/${serviceId}/active`, "PATCH", { active });
}
