"use server";

import { revalidatePath } from "next/cache";

import type { BusinessClosureInput, BusinessHourInput } from "@/lib/dashboard-types";

const API_BASE_URL = (
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export type BusinessHoursActionResult = { ok: true } | { ok: false; error: string };

async function mutate(path: string, method: "POST" | "PUT" | "DELETE", body?: unknown) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      cache: "no-store",
      headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { detail?: string | Array<{ msg?: string }> }
        | null;
      const detail = Array.isArray(payload?.detail)
        ? payload.detail.map((item) => item.msg).filter(Boolean).join("; ")
        : payload?.detail;
      return { ok: false, error: detail || `Unable to update business hours (${response.status})` } as const;
    }
    revalidatePath("/business-hours");
    revalidatePath("/appointments");
    return { ok: true } as const;
  } catch {
    return { ok: false, error: "Unable to connect to the business hours API." } as const;
  }
}

export async function saveBusinessHours(hours: BusinessHourInput[]) {
  return await mutate("/dashboard/business-hours", "PUT", { hours });
}

export async function createBusinessClosure(input: BusinessClosureInput) {
  return await mutate("/dashboard/business-closures", "POST", input);
}

export async function updateBusinessClosure(id: number, input: BusinessClosureInput) {
  return await mutate(`/dashboard/business-closures/${id}`, "PUT", input);
}

export async function removeBusinessClosure(id: number) {
  return await mutate(`/dashboard/business-closures/${id}`, "DELETE");
}
