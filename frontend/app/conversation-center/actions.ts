"use server";

import { revalidatePath } from "next/cache";
import type { ConversationDetail, ConversationMessage } from "@/lib/dashboard-types";

const API_BASE_URL = (
  process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

type Result<T> = { ok: true; data: T } | { ok: false; error: string };

async function request<T>(path: string, init?: RequestInit): Promise<Result<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
      },
    });
    if (!response.ok) {
      return { ok: false, error: response.status === 404 ? "Conversation not found." : `Conversation request failed (${response.status}).` };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, error: "Unable to connect to the conversation API." };
  }
}

export async function getConversation(conversationId: number) {
  const [detail, messages] = await Promise.all([
    request<ConversationDetail>(`/dashboard/conversations/${conversationId}`),
    request<ConversationMessage[]>(`/dashboard/conversations/${conversationId}/messages`),
  ]);
  if (!detail.ok) return detail;
  if (!messages.ok) return messages;
  return { ok: true as const, data: { detail: detail.data, messages: messages.data } };
}

export async function saveConversationNotes(conversationId: number, notes: string) {
  const result = await request<{ conversation_id: number; notes: string | null }>(
    `/dashboard/conversations/${conversationId}/notes`,
    { method: "PATCH", body: JSON.stringify({ notes }) },
  );
  if (result.ok) revalidatePath("/conversation-center");
  return result;
}
