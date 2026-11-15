import { Link, NavLink } from "react-router-dom";
import { Bot, Home, LayoutDashboard, ListChecks, Store, Wallet } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV: { to: string; label: string; icon: typeof Home; end?: boolean }[] = [
  { to: "/", label: "Trang chủ", icon: Home, end: true },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/wallet", label: "Ví / Thu nhập", icon: Wallet },
  { to: "/jobs", label: "Log job", icon: ListChecks },
];

export function Sidebar() {
  return (
    <aside className="bg-sidebar text-sidebar-foreground border-sidebar-border hidden w-60 shrink-0 flex-col border-r md:flex">
      <Link to="/" className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4 transition-colors hover:bg-sidebar-accent">
        <div className="bg-primary text-primary-foreground grid size-7 place-items-center rounded-md text-sm font-bold shadow-[0_0_12px_rgba(232,65,66,0.4)]">
          A
        </div>
        <span className="font-semibold">Avaxagent Studio</span>
      </Link>
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-sidebar-accent",
                isActive && "bg-sidebar-accent font-medium",
              )
            }
          >
            <Icon className="size-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
