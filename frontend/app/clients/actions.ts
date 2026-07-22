"use server";

import { revalidatePath } from "next/cache";
import type { ClientDetail, ClientInput } from "@/lib/dashboard-types";

const API = (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export type ClientActionResult = { ok: true; data: ClientDetail } | { ok: false; error: string };

async function mutate(path: string, method: "POST" | "PATCH", input: Partial<ClientInput>): Promise<ClientActionResult> {
  try {
    const response = await fetch(`${API}${path}`, { method, cache: "no-store", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(input) });
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { detail?: string | Array<{ msg?: string }> } | null;
      const detail = Array.isArray(body?.detail) ? body.detail.map((item) => item.msg).filter(Boolean).join("; ") : body?.detail;
      return { ok: false, error: detail || `Unable to save client (${response.status})` };
    }
    const data = await response.json() as ClientDetail;
    revalidatePath("/clients"); revalidatePath(`/clients/${data.id}`);
    return { ok: true, data };
  } catch { return { ok: false, error: "Unable to connect to the client API." }; }
}

export async function createClient(input: ClientInput) {
  return mutate("/dashboard/clients", "POST", input);
}
export async function updateClient(id: number, input: Partial<ClientInput>) {
  return mutate(`/dashboard/clients/${id}`, "PATCH", input);
}
