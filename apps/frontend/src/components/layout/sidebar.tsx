import { Link, NavLink } from "react-router-dom";
import { Bot, Flame, Home, LayoutDashboard, ListChecks, Store, Wallet, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV: { to: string; label: string; icon: typeof Home; end?: boolean }[] = [
  { to: "/", label: "Trang chủ", icon: Home, end: true },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/marketplace", label: "Marketplace", icon: Store },
  { to: "/wallet", label: "Ví / Thu nhập", icon: Wallet },
  { to: "/jobs", label: "Log job", icon: ListChecks },
];

function BrandHeader({ onClose }: { onClose?: () => void }) {
  return (
    <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
      <Link
        to="/"
        onClick={onClose}
        className="flex items-center gap-3 transition-opacity hover:opacity-90"
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#E84142] to-[#A81D20] text-white shadow-[0_0_15px_rgba(232,65,66,0.35)]">
          <Flame className="h-4 w-4 fill-white text-white" />
        </div>
        <span className="text-sm font-black tracking-tight text-slate-900">
          AVAXAGENT <span className="text-[#E84142]">STUDIO</span>
        </span>
      </Link>
      {onClose && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClose}
          aria-label="Đóng menu"
          className="h-8 w-8 p-0"
        >
          <X className="size-4" />
        </Button>
      )}
    </div>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 p-2">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-sidebar-accent",
              isActive && "bg-sidebar-accent font-medium text-[#E84142]",
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="bg-sidebar text-sidebar-foreground border-sidebar-border hidden w-64 shrink-0 flex-col border-r md:flex">
      <BrandHeader />
      <NavList />
    </aside>
  );
}

export function MobileSidebarDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true">
      <div
        className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className="bg-sidebar text-sidebar-foreground relative z-10 flex w-72 max-w-[82vw] flex-col border-r shadow-2xl">
        <BrandHeader onClose={onClose} />
        <NavList onNavigate={onClose} />
      </aside>
    </div>
  );
}
