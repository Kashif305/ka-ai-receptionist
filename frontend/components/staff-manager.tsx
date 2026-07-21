"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { FormEvent } from "react";

import {
  createStaff,
  setStaffActive,
  updateStaff,
} from "@/app/staff/actions";
import { EmptyState } from "@/components/empty-state";
import { formatTimeRange } from "@/lib/formatters";
import type {
  DashboardStaff,
  ServiceOption,
  StaffAvailabilityInput,
  StaffInput,
} from "@/lib/dashboard-types";

const weekdays = [
  "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
];

const emptyForm: StaffInput = {
  name: "",
  phone: null,
  email: null,
  active: true,
  service_ids: [],
  availability: [],
};

type Props = {
  initialStaff: DashboardStaff[];
  services: ServiceOption[];
};

export function StaffManager({ initialStaff, services }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [editing, setEditing] = useState<DashboardStaff | null | undefined>(undefined);
  const [form, setForm] = useState<StaffInput>(emptyForm);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm, service_ids: [], availability: [] });
    setError("");
  }

  function openEdit(staff: DashboardStaff) {
    setEditing(staff);
    setForm({
      name: staff.name,
      phone: staff.phone,
      email: staff.email,
      active: staff.active,
      service_ids: staff.services.map((service) => service.id),
      availability: staff.availability.map((item) => ({
        weekday: item.weekday,
        start_time: item.start_time.slice(0, 5),
        end_time: item.end_time.slice(0, 5),
        slot_duration_minutes: item.slot_duration_minutes,
        active: item.active,
      })),
    });
    setError("");
  }

  function addAvailability() {
    setForm((current) => ({
      ...current,
      availability: [...current.availability, {
        weekday: 0,
        start_time: "09:00",
        end_time: "17:00",
        slot_duration_minutes: 30,
        active: true,
      }],
    }));
  }

  function updateAvailability(index: number, patch: Partial<StaffAvailabilityInput>) {
    setForm((current) => ({
      ...current,
      availability: current.availability.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function validate(): string | null {
    if (!form.name.trim()) return "Name is required.";
    for (const item of form.availability) {
      if (item.weekday < 0 || item.weekday > 6) return "Choose a valid weekday.";
      if (item.start_time >= item.end_time) return "Availability start time must be before end time.";
      if (item.slot_duration_minutes <= 0) return "Slot duration must be greater than zero.";
    }
    return null;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError("");
    startTransition(async () => {
      const payload = {
        ...form,
        name: form.name.trim(),
        phone: form.phone?.trim() || null,
        email: form.email?.trim() || null,
      };
      const result = editing
        ? await updateStaff(editing.id, payload)
        : await createStaff(payload);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setEditing(undefined);
      setSuccess(editing ? "Staff member updated." : "Staff member added.");
      router.refresh();
    });
  }

  function toggleActive(staff: DashboardStaff) {
    if (staff.active && !window.confirm(`Deactivate ${staff.name}? Existing history will be preserved.`)) return;
    setError("");
    startTransition(async () => {
      const result = await setStaffActive(staff.id, !staff.active);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setSuccess(`${staff.name} ${staff.active ? "deactivated" : "reactivated"}.`);
      router.refresh();
    });
  }

  return (
    <>
      {(success || error) && (
        <div role="status" className={`mb-4 rounded-xl border px-4 py-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
          {error || success}
        </div>
      )}
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-bold">Staff Members</h2>
            <p className="mt-1 text-sm text-slate-500">Active staff, assigned services and availability.</p>
          </div>
          <button type="button" onClick={openCreate} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={isPending}>
            Add Staff
          </button>
        </div>

        {initialStaff.length === 0 ? (
          <EmptyState icon="♢" title="No staff members" description="Add a staff member to configure services and working hours." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1120px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 font-semibold">Staff</th><th className="px-5 py-3 font-semibold">Services</th><th className="px-5 py-3 font-semibold">Availability</th><th className="px-5 py-3 font-semibold">Today</th><th className="px-5 py-3 font-semibold">Upcoming</th><th className="px-5 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 align-top">
                {initialStaff.map((staff) => (
                  <tr key={staff.id} className={!staff.active ? "bg-slate-50/70" : undefined}>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-950 font-bold text-white">{staff.name.charAt(0).toUpperCase()}</div><div><p className="font-medium">{staff.name}</p><p className="text-xs text-slate-500">{staff.phone || staff.email || "No contact details"}</p><span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${staff.active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600"}`}>{staff.active ? "Active" : "Inactive"}</span></div></div>
                    </td>
                    <td className="px-5 py-4 text-slate-600">{staff.services.length ? staff.services.map((service) => `${service.name} (${service.duration_minutes} min)`).join(", ") : "No services assigned"}</td>
                    <td className="px-5 py-4 text-slate-600">{staff.availability.length ? <ul className="space-y-1">{staff.availability.map((slot) => <li key={slot.id} className={!slot.active ? "text-slate-400 line-through" : undefined}>{weekdays[slot.weekday]}: {formatTimeRange(slot.start_time, slot.end_time)} · {slot.slot_duration_minutes} min{!slot.active && " (disabled)"}</li>)}</ul> : "Not configured"}</td>
                    <td className="px-5 py-4 font-medium">{staff.today_appointment_count}</td><td className="px-5 py-4 font-medium">{staff.upcoming_appointment_count}</td>
                    <td className="px-5 py-4"><div className="flex max-w-52 flex-wrap gap-2"><button type="button" onClick={() => openEdit(staff)} className="rounded-lg border border-slate-300 px-2.5 py-1.5 font-medium">Edit Staff</button><button type="button" onClick={() => openEdit(staff)} className="rounded-lg border border-slate-300 px-2.5 py-1.5 font-medium">Manage Services</button><button type="button" onClick={() => openEdit(staff)} className="rounded-lg border border-slate-300 px-2.5 py-1.5 font-medium">Manage Availability</button><button type="button" disabled={isPending} onClick={() => toggleActive(staff)} className={`rounded-lg px-2.5 py-1.5 font-medium ${staff.active ? "border border-red-200 text-red-700" : "border border-emerald-200 text-emerald-700"}`}>{staff.active ? "Deactivate" : "Activate"}</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {editing !== undefined && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4" role="presentation">
          <div role="dialog" aria-modal="true" aria-labelledby="staff-form-title" className="mx-auto my-4 max-w-3xl rounded-2xl bg-white shadow-xl sm:my-10">
            <form onSubmit={submit}>
              <div className="flex items-center justify-between border-b border-slate-200 p-5"><div><h2 id="staff-form-title" className="text-lg font-bold">{editing ? "Edit Staff" : "Add Staff"}</h2><p className="text-sm text-slate-500">Profile, services and weekly availability</p></div><button type="button" onClick={() => setEditing(undefined)} aria-label="Close staff form" className="rounded-lg px-3 py-2 text-xl text-slate-500">×</button></div>
              <div className="max-h-[70vh] space-y-6 overflow-y-auto p-5">
                {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
                <fieldset className="grid gap-4 sm:grid-cols-2"><legend className="mb-3 font-semibold">Profile</legend><label className="text-sm font-medium">Name <span className="text-red-600">*</span><input required maxLength={120} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium">Phone<input maxLength={32} value={form.phone ?? ""} onChange={(event) => setForm({ ...form, phone: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium">Email<input type="email" maxLength={255} value={form.email ?? ""} onChange={(event) => setForm({ ...form, email: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="flex items-center gap-2 self-end py-2 text-sm font-medium"><input type="checkbox" checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} /> Active</label></fieldset>
                <fieldset><legend className="font-semibold">Services</legend><p className="mb-3 text-sm text-slate-500">Select the services this staff member can perform.</p>{services.length === 0 ? <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No active services are available.</p> : <div className="grid gap-2 sm:grid-cols-2">{services.map((service) => <label key={service.id} className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm"><input type="checkbox" checked={form.service_ids.includes(service.id)} onChange={(event) => setForm((current) => ({ ...current, service_ids: event.target.checked ? [...current.service_ids, service.id] : current.service_ids.filter((id) => id !== service.id) }))} /><span><span className="font-medium">{service.name}</span><span className="block text-slate-500">{service.duration_minutes} minutes</span></span></label>)}</div>}</fieldset>
                <fieldset><div className="mb-3 flex items-center justify-between"><div><legend className="font-semibold">Weekly Availability</legend><p className="text-sm text-slate-500">Add only the periods this staff member works.</p></div><button type="button" onClick={addAvailability} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium">Add Period</button></div>{form.availability.length === 0 ? <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No availability periods selected.</p> : <div className="space-y-3">{form.availability.map((item, index) => <div key={index} className="grid gap-3 rounded-xl border border-slate-200 p-3 sm:grid-cols-6"><label className="text-xs font-medium sm:col-span-2">Day<select value={item.weekday} onChange={(event) => updateAvailability(index, { weekday: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm">{weekdays.map((day, dayIndex) => <option key={day} value={dayIndex}>{day}</option>)}</select></label><label className="text-xs font-medium">Start<input type="time" required value={item.start_time} onChange={(event) => updateAvailability(index, { start_time: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm" /></label><label className="text-xs font-medium">End<input type="time" required value={item.end_time} onChange={(event) => updateAvailability(index, { end_time: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm" /></label><label className="text-xs font-medium">Slot minutes<input type="number" required min={1} value={item.slot_duration_minutes} onChange={(event) => updateAvailability(index, { slot_duration_minutes: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2 text-sm" /></label><div className="flex items-end justify-between gap-2"><label className="flex items-center gap-1 py-2 text-xs font-medium"><input type="checkbox" checked={item.active} onChange={(event) => updateAvailability(index, { active: event.target.checked })} /> Active</label><button type="button" aria-label={`Remove ${weekdays[item.weekday]} period`} onClick={() => setForm((current) => ({ ...current, availability: current.availability.filter((_, itemIndex) => itemIndex !== index) }))} className="py-2 text-xs font-medium text-red-700">Remove</button></div></div>)}</div>}</fieldset>
              </div>
              <div className="flex justify-end gap-3 border-t border-slate-200 p-5"><button type="button" onClick={() => setEditing(undefined)} disabled={isPending} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold">Cancel</button><button type="submit" disabled={isPending} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{isPending ? "Saving…" : "Save Staff"}</button></div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
