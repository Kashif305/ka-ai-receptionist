"use server";

import { revalidatePath } from "next/cache";

const API = (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export type PromotionActionResult = { ok: true; data: unknown } | { ok: false; error: string };

async function mutate(path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown): Promise<PromotionActionResult> {
  try {
    const response = await fetch(`${API}${path}`, {
      method, cache: "no-store", headers: body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const value = await response.json().catch(() => null) as { detail?: string | Array<{ msg?: string }> } | null;
      const detail = Array.isArray(value?.detail) ? value.detail.map((item) => item.msg).join("; ") : value?.detail;
      return { ok: false, error: detail || `Promotion request failed (${response.status})` };
    }
    const data = response.status === 204 ? null : await response.json();
    revalidatePath("/promotions");
    return { ok: true, data };
  } catch { return { ok: false, error: "Unable to connect to the promotions API." }; }
}

export async function createPromotion(body: unknown) { return mutate("/dashboard/promotions", "POST", body); }
export async function previewAudience(id: number) { return mutate(`/dashboard/promotions/${id}/preview-audience`, "POST"); }
export async function sendPromotion(id: number) { return mutate(`/dashboard/promotions/${id}/send`, "POST"); }
export async function schedulePromotion(id: number, scheduled_at: string) { return mutate(`/dashboard/promotions/${id}/schedule`, "POST", { scheduled_at }); }
export async function cancelPromotion(id: number) { return mutate(`/dashboard/promotions/${id}/cancel`, "POST"); }
export async function deactivateCoupon(id: number) { return mutate(`/dashboard/coupons/${id}/deactivate`, "POST"); }
export async function redeemCoupon(id: number, body: unknown) { return mutate(`/dashboard/coupons/${id}/redeem`, "POST", body); }
