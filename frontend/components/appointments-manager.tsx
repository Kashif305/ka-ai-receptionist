"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import type { FormEvent } from "react";

import {
  cancelAppointment,
  completeAppointment,
  getAppointmentDetails,
  getRescheduleAvailability,
  rescheduleAppointment,
} from "@/app/appointments/actions";
import { AppointmentsTable } from "@/components/appointments-table";
import type {
  AppointmentDetail,
  AppointmentSlot,
  DashboardAppointment,
} from "@/lib/dashboard-types";
import { formatDate, formatDateTime, formatLabel, formatTime } from "@/lib/formatters";

type Flow = "view" | "reschedule" | "cancel" | "complete";

function newYorkDate(value: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function AppointmentsManager({ appointments }: { appointments: DashboardAppointment[] }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [flow, setFlow] = useState<Flow | null>(null);
  const [selected, setSelected] = useState<DashboardAppointment | null>(null);
  const [details, setDetails] = useState<AppointmentDetail | null>(null);
  const [date, setDate] = useState("");
  const [slots, setSlots] = useState<AppointmentSlot[]>([]);
  const [selectedStart, setSelectedStart] = useState("");
  const [staffId, setStaffId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const availabilityRequest = useRef(0);

  async function loadAvailability(appointmentId: number, selectedDate: string) {
    const requestId = ++availabilityRequest.current;
    setLoading(true);
    setError("");
    setSelectedStart("");
    const result = await getRescheduleAvailability(appointmentId, selectedDate);
    if (requestId !== availabilityRequest.current) return;
    setLoading(false);
    if (!result.ok) {
      setSlots([]);
      setError(result.error);
      return;
    }
    setSlots(result.data.slots);
  }

  function close() {
    setFlow(null);
    setSelected(null);
    setDetails(null);
    setSlots([]);
    setError("");
  }

  function open(action: Flow, appointment: DashboardAppointment) {
    setFlow(action);
    setSelected(appointment);
    setDetails(null);
    setError("");
    setNote("");
    setDate(newYorkDate(appointment.start_at));
    setSlots([]);
    setSelectedStart("");
    setStaffId(null);
    setLoading(true);
    startTransition(async () => {
      const result = await getAppointmentDetails(appointment.id);
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setDetails(result.data);
      setStaffId(result.data.assigned_staff_id);
      if (action === "reschedule") {
        await loadAvailability(appointment.id, newYorkDate(appointment.start_at));
      }
    });
  }

  const chosenSlot = slots.find((slot) => slot.start_at === selectedStart);

  function finish(message: string) {
    close();
    setSuccess(message);
    router.refresh();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !flow) return;
    setError("");
    startTransition(async () => {
      if (flow === "cancel") {
        const result = await cancelAppointment(selected.id, note);
        if (!result.ok) return setError(result.error);
        finish("Appointment cancelled. The record and notes were preserved.");
      } else if (flow === "complete") {
        const result = await completeAppointment(selected.id);
        if (!result.ok) return setError(result.error);
        finish("Appointment marked completed.");
      } else if (flow === "reschedule") {
        if (!selectedStart || !staffId) return setError("Choose a time and staff member.");
        const result = await rescheduleAppointment(selected.id, selectedStart, staffId, note);
        if (!result.ok) return setError(result.error);
        finish("Appointment rescheduled successfully.");
      }
    });
  }

  return (
    <>
      {(success || (!flow && error)) && (
        <div role="status" className={`mb-4 rounded-xl border px-4 py-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
          {error || success}
        </div>
      )}
      <AppointmentsTable appointments={appointments} onAction={open} />

      {flow && selected && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4" role="presentation" onKeyDown={(event) => { if (event.key === "Escape" && !isPending) close(); }} onMouseDown={(event) => { if (event.target === event.currentTarget && !isPending) close(); }}>
          <div role="dialog" aria-modal="true" aria-labelledby="appointment-dialog-title" className="mx-auto my-4 max-w-2xl rounded-2xl bg-white shadow-xl sm:my-10">
            <div className="flex items-start justify-between border-b border-slate-200 p-5">
              <div><h2 id="appointment-dialog-title" className="text-lg font-bold">{flow === "view" ? "Appointment Details" : flow === "reschedule" ? "Reschedule Appointment" : flow === "cancel" ? "Cancel Appointment" : "Complete Appointment"}</h2><p className="mt-1 text-sm text-slate-500">{selected.customer_name} · {selected.service_name}</p></div>
              <button type="button" autoFocus onClick={close} disabled={isPending} aria-label="Close appointment dialog" className="rounded-lg px-3 py-2 text-xl text-slate-500">×</button>
            </div>

            <form onSubmit={submit}>
              <div className="max-h-[70vh] overflow-y-auto p-5">
                {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                {loading && !details ? <p role="status" className="py-8 text-center text-sm text-slate-500">Loading appointment…</p> : details && flow === "view" ? (
                  <dl className="grid gap-4 text-sm sm:grid-cols-2">
                    <div><dt className="text-slate-500">Customer</dt><dd className="font-medium">{details.customer_name}</dd></div>
                    <div><dt className="text-slate-500">Phone</dt><dd><a className="font-medium hover:underline" href={`tel:${details.customer_phone}`}>{details.customer_phone}</a></dd></div>
                    {details.customer_email && <div><dt className="text-slate-500">Email</dt><dd>{details.customer_email}</dd></div>}
                    <div><dt className="text-slate-500">Service</dt><dd>{details.service_name} · {details.service_duration_minutes} min</dd></div>
                    <div><dt className="text-slate-500">Staff</dt><dd>{details.assigned_staff_name ?? "Unassigned"}</dd></div>
                    <div><dt className="text-slate-500">Date</dt><dd>{formatDate(details.start_at)}</dd></div>
                    <div><dt className="text-slate-500">Time</dt><dd>{formatTime(details.start_at)}–{formatTime(details.end_at)}</dd></div>
                    <div><dt className="text-slate-500">Status</dt><dd>{formatLabel(details.status)}</dd></div>
                    <div><dt className="text-slate-500">Source</dt><dd>{formatLabel(details.source)}</dd></div>
                    <div><dt className="text-slate-500">Created</dt><dd>{formatDateTime(details.created_at)}</dd></div>
                    <div className="sm:col-span-2"><dt className="text-slate-500">Notes</dt><dd className="mt-1 whitespace-pre-wrap rounded-lg bg-slate-50 p-3">{details.notes || "No notes"}</dd></div>
                  </dl>
                ) : details && flow === "reschedule" ? (
                  <div className="space-y-5">
                    <p className="rounded-lg bg-slate-50 p-3 text-sm"><span className="text-slate-500">Current appointment:</span> <strong>{formatDateTime(details.start_at)}</strong> with {details.assigned_staff_name ?? "unassigned staff"}</p>
                    <label className="block text-sm font-medium">New date<input type="date" required value={date} min={newYorkDate(new Date().toISOString())} onChange={(event) => { const nextDate = event.target.value; setDate(nextDate); if (nextDate) void loadAvailability(selected.id, nextDate); }} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
                    <fieldset><legend className="text-sm font-medium">Available time</legend>{loading ? <p className="mt-2 text-sm text-slate-500">Loading valid slots…</p> : slots.length === 0 ? <p className="mt-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No valid slots are available for this date.</p> : <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">{slots.map((slot) => <label key={slot.start_at} className={`cursor-pointer rounded-lg border p-2 text-center text-sm ${selectedStart === slot.start_at ? "border-slate-950 bg-slate-950 text-white" : "border-slate-300"}`}><input className="sr-only" type="radio" name="slot" value={slot.start_at} checked={selectedStart === slot.start_at} onChange={() => { setSelectedStart(slot.start_at); setStaffId(slot.available_staff.find((staff) => staff.id === details.assigned_staff_id)?.id ?? slot.available_staff[0].id); }} />{formatTime(slot.start_at)}</label>)}</div>}</fieldset>
                    {chosenSlot && <label className="block text-sm font-medium">Staff<select required value={staffId ?? ""} onChange={(event) => setStaffId(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2">{chosenSlot.available_staff.map((staff) => <option key={staff.id} value={staff.id}>{staff.name}</option>)}</select></label>}
                    <label className="block text-sm font-medium">Owner note <span className="font-normal text-slate-500">(optional)</span><textarea maxLength={1000} rows={3} value={note} onChange={(event) => setNote(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
                  </div>
                ) : details ? (
                  <div className="space-y-4 text-sm">
                    <p>Confirm {flow === "cancel" ? "cancellation of" : "completion for"} <strong>{details.customer_name}</strong>&apos;s <strong>{details.service_name}</strong> appointment on <strong>{formatDateTime(details.start_at)}</strong>.</p>
                    {flow === "cancel" && <label className="block font-medium">Cancellation reason <span className="font-normal text-slate-500">(optional)</span><textarea maxLength={1000} rows={3} value={note} onChange={(event) => setNote(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label>}
                  </div>
                ) : null}
              </div>
              <div className="flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end">
                <button type="button" onClick={close} disabled={isPending} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold">Close</button>
                {flow !== "view" && <button type="submit" disabled={isPending || loading || !details || (flow === "reschedule" && (!selectedStart || !staffId))} className={`rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 ${flow === "cancel" ? "bg-red-700" : "bg-slate-950"}`}>{isPending ? "Saving…" : flow === "cancel" ? "Cancel Appointment" : flow === "complete" ? "Mark Completed" : "Save New Schedule"}</button>}
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
