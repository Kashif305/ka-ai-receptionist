"use client";

import Link from "next/link";
import { useMemo, useRef, useState, useTransition } from "react";

import { getConversation, saveConversationNotes } from "@/app/conversation-center/actions";
import type {
  ConversationDetail,
  ConversationMessage,
  ConversationStatus,
  DashboardConversation,
} from "@/lib/dashboard-types";
import { formatDate, formatDateTime, formatLabel, formatTime } from "@/lib/formatters";

const filters: Array<"all" | ConversationStatus> = ["all", "active", "waiting", "booked", "completed", "cancelled"];

function relativeTime(value: string) {
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const choices: Array<[number, Intl.RelativeTimeFormatUnit]> = [[86400, "day"], [3600, "hour"], [60, "minute"]];
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [size, unit] of choices) {
    if (Math.abs(seconds) >= size) return formatter.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

function StatusBadge({ status }: { status: string }) {
  const tones: Record<string, string> = {
    active: "bg-blue-50 text-blue-700", waiting: "bg-amber-50 text-amber-700",
    booked: "bg-violet-50 text-violet-700", completed: "bg-emerald-50 text-emerald-700",
    cancelled: "bg-red-50 text-red-700",
  };
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tones[status] ?? "bg-slate-100 text-slate-700"}`}>{formatLabel(status)}</span>;
}

export function ConversationCenter({ conversations }: { conversations: DashboardConversation[] }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<(typeof filters)[number]>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [isSaving, startSaving] = useTransition();
  const requestId = useRef(0);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return conversations.filter((item) => {
      const matchesFilter = filter === "all" || item.status === filter;
      const matchesSearch = !query || [item.customer_name, item.customer_phone, item.last_message_preview]
        .some((value) => value?.toLowerCase().includes(query));
      return matchesFilter && matchesSearch;
    });
  }, [conversations, filter, search]);

  async function selectConversation(id: number) {
    const currentRequest = ++requestId.current;
    setSelectedId(id); setLoading(true); setError(""); setSaved(false); setDetail(null); setMessages([]);
    const result = await getConversation(id);
    if (currentRequest !== requestId.current) return;
    setLoading(false);
    if (!result.ok) return setError(result.error);
    setDetail(result.data.detail); setMessages(result.data.messages); setNotes(result.data.detail.internal_notes ?? "");
  }

  function saveNotes() {
    if (!detail) return;
    setError(""); setSaved(false);
    startSaving(async () => {
      const result = await saveConversationNotes(detail.id, notes);
      if (!result.ok) return setError(result.error);
      setNotes(result.data.notes ?? "");
      setDetail((current) => current ? { ...current, internal_notes: result.data.notes } : current);
      setSaved(true);
    });
  }

  return (
    <div className="grid min-h-[calc(100vh-10rem)] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[23rem_minmax(0,1fr)]">
      <section className="border-b border-slate-200 lg:border-b-0 lg:border-r" aria-label="Conversation list">
        <div className="border-b border-slate-200 p-4">
          <label className="sr-only" htmlFor="conversation-search">Search conversations</label>
          <input id="conversation-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, phone, or message" className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm outline-none focus:border-slate-500" />
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1" aria-label="Status filters">
            {filters.map((item) => <button key={item} type="button" onClick={() => setFilter(item)} className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold ${filter === item ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{formatLabel(item)}</button>)}
          </div>
        </div>
        <div className="max-h-[38rem] overflow-y-auto lg:max-h-[calc(100vh-15rem)]">
          {visible.length === 0 ? (
            <div className="p-8 text-center"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-xl">◌</div><h2 className="mt-4 font-semibold">No conversations found</h2><p className="mt-1 text-sm text-slate-500">{conversations.length ? "Try another search or status filter." : "WhatsApp conversations will appear here after customers contact the receptionist."}</p></div>
          ) : visible.map((item) => (
            <button key={item.id} type="button" onClick={() => void selectConversation(item.id)} className={`w-full border-b border-slate-100 p-4 text-left transition hover:bg-slate-50 ${selectedId === item.id ? "bg-slate-50 ring-1 ring-inset ring-slate-300" : ""}`}>
              <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-bold">{item.customer_name || "Unnamed customer"}</p><p className="mt-0.5 text-xs text-slate-500">{item.customer_phone}</p></div><time suppressHydrationWarning className="shrink-0 text-xs text-slate-400" dateTime={item.last_activity_at}>{relativeTime(item.last_activity_at)}</time></div>
              <p className="mt-2 truncate text-sm text-slate-600">{item.last_message_preview || "No messages yet"}</p><div className="mt-3"><StatusBadge status={item.status} /></div>
            </button>
          ))}
        </div>
      </section>

      <section className="min-w-0 bg-slate-50/50" aria-label="Conversation detail">
        {!selectedId ? <div className="flex min-h-[32rem] items-center justify-center p-8 text-center"><div><div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-white text-2xl shadow-sm">◌</div><h2 className="mt-4 font-bold">Select a conversation</h2><p className="mt-1 text-sm text-slate-500">Choose a customer on the left to review the full timeline.</p></div></div> : loading ? <div role="status" className="animate-pulse p-6"><div className="h-8 w-52 rounded bg-slate-200" /><div className="mt-3 h-4 w-72 rounded bg-slate-200" /><div className="mt-8 h-72 rounded-2xl bg-slate-200" /><span className="sr-only">Loading conversation details</span></div> : error && !detail ? <div role="alert" className="m-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div> : detail && (
          <div>
            <header className="border-b border-slate-200 bg-white p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-bold">{detail.customer.name || "Unnamed customer"}</h2><a href={`tel:${detail.customer.phone}`} className="mt-1 inline-block text-sm text-slate-500 hover:underline">{detail.customer.phone}</a></div><StatusBadge status={detail.status} /></div><dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-slate-500">Created</dt><dd className="font-medium">{formatDateTime(detail.created_at)}</dd></div><div><dt className="text-slate-500">Last activity</dt><dd className="font-medium">{formatDateTime(detail.last_activity_at)}</dd></div></dl></header>
            <div className="space-y-5 p-4 sm:p-6">
              <section className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-bold">Timeline</h3><div className="mt-5 space-y-4">{messages.length === 0 ? <p className="rounded-xl bg-slate-50 p-5 text-center text-sm text-slate-500">No messages have been recorded.</p> : messages.map((message) => <article key={message.id} className={`flex ${message.direction === "outgoing" ? "justify-end" : "justify-start"}`}><div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${message.direction === "outgoing" ? "rounded-br-md bg-slate-950 text-white" : "rounded-bl-md border border-slate-200 bg-white text-slate-800"}`}><div className={`mb-1 flex flex-wrap gap-x-2 text-xs ${message.direction === "outgoing" ? "text-slate-300" : "text-slate-500"}`}><strong>{message.sender}</strong><time dateTime={message.timestamp}>{formatDateTime(message.timestamp)}</time>{message.delivery_status && <span>{formatLabel(message.delivery_status)}</span>}</div><p className="whitespace-pre-wrap break-words">{message.body}</p></div></article>)}</div></section>
              <div className="grid gap-5 xl:grid-cols-2">
                {detail.appointment && <section className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center justify-between gap-3"><h3 className="font-bold">Appointment</h3><StatusBadge status={detail.appointment.status} /></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-500">Service</dt><dd className="font-medium">{detail.appointment.service_name}</dd></div><div><dt className="text-slate-500">Staff</dt><dd className="font-medium">{detail.appointment.staff_name || "Unassigned"}</dd></div><div><dt className="text-slate-500">Date</dt><dd>{formatDate(detail.appointment.start_at)}</dd></div><div><dt className="text-slate-500">Time</dt><dd>{formatTime(detail.appointment.start_at)}–{formatTime(detail.appointment.end_at)}</dd></div></dl><Link href="/appointments" className="mt-5 inline-flex rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white">Open Appointment</Link></section>}
                <section className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-bold">AI Summary</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">{detail.ai_summary || "No AI summary has been stored for this conversation."}</p></section>
              </div>
              <section className="rounded-2xl border border-slate-200 bg-white p-5"><h3 className="font-bold">Internal Notes</h3><p className="mt-1 text-xs text-slate-500">Visible only to dashboard owners. Never sent to customers.</p><textarea aria-label="Internal owner notes" maxLength={5000} rows={5} value={notes} onChange={(event) => { setNotes(event.target.value); setSaved(false); }} className="mt-4 w-full rounded-xl border border-slate-300 p-3 text-sm outline-none focus:border-slate-500" />{error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}<div className="mt-3 flex items-center gap-3"><button type="button" disabled={isSaving || notes === (detail.internal_notes ?? "")} onClick={saveNotes} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{isSaving ? "Saving…" : "Save Notes"}</button>{saved && <span role="status" className="text-sm text-emerald-700">Notes saved.</span>}</div></section>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
