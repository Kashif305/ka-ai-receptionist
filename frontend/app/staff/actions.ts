"use server";

import { revalidatePath } from "next/cache";

import type { StaffInput } from "@/lib/dashboard-types";

const API_BASE_URL = (
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000"
).replace(/\/$/, "");

export type StaffActionResult = { ok: true } | { ok: false; error: string };

async function mutateStaff(
  path: string,
  method: "POST" | "PUT" | "PATCH",
  body: unknown,
): Promise<StaffActionResult> {
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
      return {
        ok: false,
        error: detail || `Unable to save staff (${response.status})`,
      };
    }
    revalidatePath("/staff");
    revalidatePath("/");
    return { ok: true };
  } catch {
    return { ok: false, error: "Unable to connect to the staff API." };
  }
}

export async function createStaff(input: StaffInput) {
  return mutateStaff("/dashboard/staff", "POST", input);
}

export async function updateStaff(staffId: number, input: StaffInput) {
  return mutateStaff(`/dashboard/staff/${staffId}`, "PUT", input);
}

export async function setStaffActive(staffId: number, active: boolean) {
  return mutateStaff(`/dashboard/staff/${staffId}/active`, "PATCH", { active });
}
