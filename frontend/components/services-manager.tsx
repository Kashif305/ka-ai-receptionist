"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { FormEvent } from "react";

import {
  createService,
  setServiceActive,
  updateService,
} from "@/app/services/actions";
import { EmptyState } from "@/components/empty-state";
import type { ServiceInput, ServiceOption } from "@/lib/dashboard-types";

const emptyForm: ServiceInput = {
  name: "",
  description: null,
  duration_minutes: 30,
  price: 0,
  active: true,
};

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

type Props = { initialServices: ServiceOption[] };

export function ServicesManager({ initialServices }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [editing, setEditing] = useState<ServiceOption | null | undefined>(undefined);
  const [viewing, setViewing] = useState<ServiceOption | null>(null);
  const [form, setForm] = useState<ServiceInput>(emptyForm);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function openCreate() {
    setEditing(null);
    setForm({ ...emptyForm });
    setError("");
    setSuccess("");
  }

  function openEdit(service: ServiceOption) {
    setEditing(service);
    setForm({
      name: service.name,
      description: service.description,
      duration_minutes: service.duration_minutes,
      price: service.price ?? 0,
      active: service.active,
    });
    setError("");
    setSuccess("");
  }

  function validate(): string | null {
    if (!form.name.trim()) return "Name is required.";
    if (!Number.isInteger(form.duration_minutes) || form.duration_minutes <= 0) {
      return "Duration must be a positive whole number.";
    }
    if (!Number.isFinite(form.price) || form.price < 0) {
      return "Price must be zero or greater.";
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
        description: form.description?.trim() || null,
      };
      const result = editing
        ? await updateService(editing.id, payload)
        : await createService(payload);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setEditing(undefined);
      setSuccess(editing ? "Service updated." : "Service added.");
      router.refresh();
    });
  }

  function toggleActive(service: ServiceOption) {
    if (service.active && !window.confirm(`Disable ${service.name}? Customers will no longer be able to book it.`)) return;
    setError("");
    setSuccess("");
    startTransition(async () => {
      const result = await setServiceActive(service.id, !service.active);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setSuccess(`${service.name} ${service.active ? "disabled" : "enabled"}.`);
      router.refresh();
    });
  }

  return (
    <>
      {(success || error) && (
        <div role={error ? "alert" : "status"} className={`mb-4 rounded-xl border px-4 py-3 text-sm ${error ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
          {error || success}
        </div>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="font-bold">Salon Services</h2><p className="mt-1 text-sm text-slate-500">Inactive services remain in appointment history but cannot be booked.</p></div>
          <button type="button" onClick={openCreate} disabled={isPending} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Add Service</button>
        </div>

        {initialServices.length === 0 ? (
          <EmptyState icon="✦" title="No services" description="Add a service to make it available for booking." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-semibold">Name</th><th className="px-5 py-3 font-semibold">Duration</th><th className="px-5 py-3 font-semibold">Price</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 font-semibold">Actions</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {initialServices.map((service) => (
                  <tr key={service.id} className={!service.active ? "bg-slate-50/70" : undefined}>
                    <td className="px-5 py-4"><p className="font-medium">{service.name}</p><p className="max-w-sm truncate text-xs text-slate-500">{service.description || "No description"}</p></td>
                    <td className="px-5 py-4 text-slate-600">{service.duration_minutes} min</td>
                    <td className="px-5 py-4 text-slate-600">{money.format(service.price ?? 0)}</td>
                    <td className="px-5 py-4"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${service.active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600"}`}>{service.active ? "Active" : "Inactive"}</span></td>
                    <td className="px-5 py-4"><div className="flex flex-wrap gap-2"><button type="button" onClick={() => setViewing(service)} className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium">View</button><button type="button" onClick={() => openEdit(service)} className="rounded-lg border border-slate-300 px-3 py-1.5 font-medium">Edit</button><button type="button" disabled={isPending} onClick={() => toggleActive(service)} className={`rounded-lg border px-3 py-1.5 font-medium disabled:opacity-50 ${service.active ? "border-red-200 text-red-700" : "border-emerald-200 text-emerald-700"}`}>{service.active ? "Disable" : "Enable"}</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {viewing && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="service-details-title" className="mx-auto my-10 max-w-lg rounded-2xl bg-white shadow-xl"><div className="flex items-center justify-between border-b border-slate-200 p-5"><h2 id="service-details-title" className="text-lg font-bold">Service Details</h2><button type="button" onClick={() => setViewing(null)} aria-label="Close service details" className="rounded-lg px-3 py-2 text-xl text-slate-500">×</button></div><dl className="grid gap-4 p-5 sm:grid-cols-2"><div className="sm:col-span-2"><dt className="text-xs font-semibold uppercase text-slate-500">Name</dt><dd className="mt-1 font-medium">{viewing.name}</dd></div><div><dt className="text-xs font-semibold uppercase text-slate-500">Duration</dt><dd className="mt-1">{viewing.duration_minutes} minutes</dd></div><div><dt className="text-xs font-semibold uppercase text-slate-500">Price</dt><dd className="mt-1">{money.format(viewing.price ?? 0)}</dd></div><div><dt className="text-xs font-semibold uppercase text-slate-500">Status</dt><dd className="mt-1">{viewing.active ? "Active" : "Inactive"}</dd></div><div className="sm:col-span-2"><dt className="text-xs font-semibold uppercase text-slate-500">Description</dt><dd className="mt-1 whitespace-pre-wrap text-slate-700">{viewing.description || "No description"}</dd></div></dl><div className="flex justify-end border-t border-slate-200 p-5"><button type="button" onClick={() => setViewing(null)} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white">Close</button></div></div></div>
      )}

      {editing !== undefined && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4" role="presentation"><div role="dialog" aria-modal="true" aria-labelledby="service-form-title" className="mx-auto my-10 max-w-xl rounded-2xl bg-white shadow-xl"><form onSubmit={submit}><div className="flex items-center justify-between border-b border-slate-200 p-5"><div><h2 id="service-form-title" className="text-lg font-bold">{editing ? "Edit Service" : "Add Service"}</h2><p className="text-sm text-slate-500">Service details and booking availability</p></div><button type="button" onClick={() => setEditing(undefined)} aria-label="Close service form" className="rounded-lg px-3 py-2 text-xl text-slate-500">×</button></div><div className="grid gap-4 p-5 sm:grid-cols-2">{error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 sm:col-span-2">{error}</p>}<label className="text-sm font-medium sm:col-span-2">Name <span className="text-red-600">*</span><input required maxLength={120} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium">Duration (minutes) <span className="text-red-600">*</span><input type="number" required min={1} step={1} value={form.duration_minutes} onChange={(event) => setForm({ ...form, duration_minutes: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium">Price <span className="text-red-600">*</span><input type="number" required min={0} step="0.01" value={form.price} onChange={(event) => setForm({ ...form, price: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="text-sm font-medium sm:col-span-2">Description<textarea rows={4} value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" /></label><label className="flex items-center gap-2 text-sm font-medium sm:col-span-2"><input type="checkbox" checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} /> Active and available for booking</label></div><div className="flex justify-end gap-3 border-t border-slate-200 p-5"><button type="button" onClick={() => setEditing(undefined)} disabled={isPending} className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold">Cancel</button><button type="submit" disabled={isPending} className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{isPending ? "Saving…" : "Save Service"}</button></div></form></div></div>
      )}
    </>
  );
}
