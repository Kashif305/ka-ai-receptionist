"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import type { FormEvent } from "react";

import {
  createBusinessClosure,
  removeBusinessClosure,
  saveBusinessHours,
  updateBusinessClosure,
} from "@/app/business-hours/actions";
import { EmptyState } from "@/components/empty-state";
import type {
  BusinessClosure,
  BusinessClosureInput,
  BusinessHour,
  BusinessHourInput,
} from "@/lib/dashboard-types";

const weekdayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const emptyClosure: BusinessClosureInput = { start_date: "", end_date: "", reason: null };

type Props = { initialHours: BusinessHour[]; initialClosures: BusinessClosure[] };

export function BusinessHoursManager({ initialHours, initialClosures }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [hours, setHours] = useState<BusinessHourInput[]>(() =>
    initialHours.map(({ weekday, is_open, open_time, close_time }) => ({
      weekday,
      is_open,
      open_time: open_time?.slice(0, 5) ?? null,
      close_time: close_time?.slice(0, 5) ?? null,
    })),
  );
  const [editing, setEditing] = useState<BusinessClosure | null | undefined>(undefined);
  const [closureForm, setClosureForm] = useState<BusinessClosureInput>(emptyClosure);
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const pristineHours = useMemo(
    () => initialHours.map(({ weekday, is_open, open_time, close_time }) => ({
      weekday, is_open, open_time: open_time?.slice(0, 5) ?? null, close_time: close_time?.slice(0, 5) ?? null,
    })),
    [initialHours],
  );
  const isDirty = JSON.stringify(hours) !== JSON.stringify(pristineHours);

  function updateHour(weekday: number, changes: Partial<BusinessHourInput>) {
    setHours((current) => current.map((item) => item.weekday === weekday ? { ...item, ...changes } : item));
    setRowErrors((current) => ({ ...current, [weekday]: "" }));
    setSuccess("");
  }

  function validateHours() {
    const errors: Record<number, string> = {};
    for (const item of hours) {
      if (!item.is_open) continue;
      if (!item.open_time || !item.close_time) errors[item.weekday] = "Opening and closing times are required.";
      else if (item.close_time <= item.open_time) errors[item.weekday] = "Closing time must be later than opening time.";
    }
    setRowErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function submitHours() {
    if (!validateHours()) return;
    setError("");
    startTransition(async () => {
      const payload = hours.map((item) => item.is_open ? item : { ...item, open_time: null, close_time: null });
      const result = await saveBusinessHours(payload);
      if (!result.ok) return setError(result.error);
      setSuccess("Weekly business hours saved.");
      router.refresh();
    });
  }

  function openClosure(closure: BusinessClosure | null) {
    setEditing(closure);
    setClosureForm(closure ? { start_date: closure.start_date, end_date: closure.end_date, reason: closure.reason } : { ...emptyClosure });
    setError("");
    setSuccess("");
  }

  function submitClosure(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!closureForm.start_date || !closureForm.end_date) return setError("Start and end dates are required.");
    if (closureForm.end_date < closureForm.start_date) return setError("End date must be on or after start date.");
    setError("");
    startTransition(async () => {
      const payload = { ...closureForm, reason: closureForm.reason?.trim() || null };
      const result = editing
        ? await updateBusinessClosure(editing.id, payload)
        : await createBusinessClosure(payload);
      if (!result.ok) return setError(result.error);
      setEditing(undefined);
      setSuccess(editing ? "Closure updated." : "Closure added.");
      router.refresh();
    });
  }

  function removeClosure(closure: BusinessClosure) {
    if (!window.confirm("Remove this business closure? Booking will become available for these dates if weekly hours are open.")) return;
    setDeletingId(closure.id);
    setError("");
    setSuccess("");
    startTransition(async () => {
      const result = await removeBusinessClosure(closure.id);
      setDeletingId(null);
      if (!result.ok) return setError(result.error);
      setSuccess("Closure removed.");
      router.refresh();
    });
  }

  return (
    <div className="space-y-6">
      {(error || success) && <div role={error ? "alert" : "status"} className={`rounded-xl border px-4 py-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{error || success}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="font-bold">Weekly Hours</h2><p className="mt-1 text-sm text-slate-500">One continuous opening interval per day. Times use America/New_York.</p></div>
          <div className="flex items-center gap-3"><span className={`text-sm ${isDirty ? "font-medium text-amber-700" : "text-slate-500"}`}>{isDirty ? "Unsaved changes" : "All changes saved"}</span><button type="button" onClick={submitHours} disabled={isPending || !isDirty} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{isPending ? "Saving…" : "Save Hours"}</button></div>
        </div>
        <div className="divide-y divide-slate-100">
          {hours.map((item) => (
            <div key={item.weekday} className="grid gap-3 p-5 md:grid-cols-[10rem_8rem_1fr_1fr] md:items-start">
              <p className="pt-2 font-semibold">{weekdayNames[item.weekday]}</p>
              <label className="flex min-h-10 items-center gap-2 text-sm font-medium"><input type="checkbox" role="switch" checked={item.is_open} onChange={(event) => updateHour(item.weekday, { is_open: event.target.checked, ...(event.target.checked ? {} : { open_time: null, close_time: null }) })} />{item.is_open ? "Open" : "Closed"}</label>
              <label className="text-sm font-medium text-slate-700">Opening time<input aria-label={`${weekdayNames[item.weekday]} opening time`} type="time" disabled={!item.is_open} value={item.open_time ?? ""} onChange={(event) => updateHour(item.weekday, { open_time: event.target.value || null })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-100" /></label>
              <label className="text-sm font-medium text-slate-700">Closing time<input aria-label={`${weekdayNames[item.weekday]} closing time`} type="time" disabled={!item.is_open} value={item.close_time ?? ""} onChange={(event) => updateHour(item.weekday, { close_time: event.target.value || null })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-100" />{rowErrors[item.weekday] && <span role="alert" className="mt-1 block text-xs text-red-600">{rowErrors[item.weekday]}</span>}</label>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 p-5"><div><h2 className="font-bold">Special Closures</h2><p className="mt-1 text-sm text-slate-500">One-day holidays and temporary multi-day closures override weekly hours.</p></div><button type="button" onClick={() => openClosure(null)} disabled={isPending} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Add Closure</button></div>
        {initialClosures.length === 0 ? <EmptyState icon="◴" title="No special closures" description="Add a closure for a holiday, vacation, or temporary shutdown." /> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm"><thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Start date</th><th className="px-5 py-3">End date</th><th className="px-5 py-3">Reason</th><th className="px-5 py-3">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{initialClosures.map((closure) => <tr key={closure.id}><td className="px-5 py-4">{closure.start_date}</td><td className="px-5 py-4">{closure.end_date}</td><td className="px-5 py-4 text-slate-600">{closure.reason || "—"}</td><td className="px-5 py-4"><div className="flex gap-2"><button type="button" onClick={() => openClosure(closure)} className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium">Edit</button><button type="button" disabled={isPending} onClick={() => removeClosure(closure)} className="rounded-lg border border-red-200 px-3 py-1.5 font-medium text-red-700 disabled:opacity-50">{deletingId === closure.id ? "Removing…" : "Remove"}</button></div></td></tr>)}</tbody></table></div>
        )}
      </section>

      {editing !== undefined && <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="closure-form-title" className="mx-auto my-10 max-w-lg rounded-2xl bg-white shadow-xl"><form onSubmit={submitClosure}><div className="flex items-center justify-between border-b border-slate-200 p-5"><h2 id="closure-form-title" className="text-lg font-bold">{editing ? "Edit Closure" : "Add Closure"}</h2><button type="button" onClick={() => setEditing(undefined)} aria-label="Close closure form" className="rounded-lg px-3 py-2 text-xl text-slate-500">×</button></div><div className="grid gap-4 p-5 sm:grid-cols-2">{error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 sm:col-span-2">{error}</p>}<label className="text-sm font-medium">Start date<input required type="date" value={closureForm.start_date} onChange={(event) => setClosureForm({ ...closureForm, start_date: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium">End date<input required type="date" min={closureForm.start_date || undefined} value={closureForm.end_date} onChange={(event) => setClosureForm({ ...closureForm, end_date: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium sm:col-span-2">Reason (optional)<textarea maxLength={500} rows={3} value={closureForm.reason ?? ""} onChange={(event) => setClosureForm({ ...closureForm, reason: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label></div><div className="flex justify-end gap-3 border-t border-slate-200 p-5"><button type="button" onClick={() => setEditing(undefined)} disabled={isPending} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold">Cancel</button><button type="submit" disabled={isPending} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{isPending ? "Saving…" : "Save Closure"}</button></div></form></div></div>}
    </div>
  );
}
