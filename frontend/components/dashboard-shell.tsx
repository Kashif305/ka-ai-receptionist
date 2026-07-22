import Link from "next/link";
import type { ReactNode } from "react";

const navigation = [
  { href: "/", label: "Overview", icon: "⌂" },
  { href: "/appointments", label: "Appointments", icon: "◷" },
  { href: "/customers", label: "Customers", icon: "♙" },
  { href: "/staff", label: "Staff", icon: "♢" },
  { href: "/services", label: "Services", icon: "✦" },
  { href: "/business-hours", label: "Business Hours", icon: "◴" },
];

type DashboardShellProps = {
  title: string;
  description: string;
  children: ReactNode;
};

export function DashboardShell({
  title,
  description,
  children,
}: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-[#f6f7f9] text-slate-900">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white lg:block">
        <div className="flex h-20 items-center border-b border-slate-200 px-6">
          <div>
            <p className="text-lg font-bold tracking-tight">
              Samina Beauty Salon
            </p>
            <p className="text-xs text-slate-500">Owner Dashboard</p>
          </div>
        </div>

        <nav className="space-y-1 p-4">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-base">
                {item.icon}
              </span>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="absolute bottom-0 w-full border-t border-slate-200 p-4">
          <div className="rounded-2xl bg-slate-950 p-4 text-white">
            <p className="text-sm font-semibold">Samina Receptionist</p>
            <p className="mt-1 text-xs text-slate-300">
              WhatsApp booking system online
            </p>
            <div className="mt-3 flex items-center gap-2 text-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Operational
            </div>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="flex min-h-20 items-center justify-between px-5 sm:px-8">
            <div>
              <h1 className="text-xl font-bold tracking-tight sm:text-2xl">
                {title}
              </h1>
              <p className="mt-1 text-sm text-slate-500">{description}</p>
            </div>

            <div className="hidden items-center gap-3 sm:flex">
              <div className="text-right">
                <p className="text-sm font-semibold">Salon Owner</p>
                <p className="text-xs text-slate-500">Administrator</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-950 text-sm font-bold text-white">
                SO
              </div>
            </div>
          </div>

          <nav className="flex gap-2 overflow-x-auto border-t border-slate-100 px-4 py-3 lg:hidden">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="whitespace-nowrap rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="p-5 sm:p-8">{children}</main>
      </div>
    </div>
  );
}
