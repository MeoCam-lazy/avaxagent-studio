import { useState } from "react";
import { Menu } from "lucide-react";
import { Outlet } from "react-router-dom";

import { ConnectButton } from "@/components/connect-button";
import { MobileSidebarDrawer, Sidebar } from "@/components/layout/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useNetwork } from "@/hooks/use-network";
import { CHAIN_NAMES } from "@/lib/format";

export function AppShell() {
  const { data: net, isError } = useNetwork();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex min-h-svh">
      <Sidebar />
      <MobileSidebarDrawer open={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-2 border-b px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Mở menu điều hướng"
              className="h-9 w-9 p-0 md:hidden"
            >
              <Menu className="size-5" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            {net ? (
              <>
                <Badge variant="outline" className="hidden sm:inline-flex">
                  {CHAIN_NAMES[net.chain_id] ?? net.network} · {net.chain_id}
                </Badge>
                <Badge
                  variant={net.erc8183_enabled ? "default" : "secondary"}
                  className="hidden sm:inline-flex"
                >
                  ERC-8183 {net.erc8183_enabled ? "on" : "off (x402)"}
                </Badge>
              </>
            ) : (
              <Badge variant="secondary">{isError ? "API offline" : "…"}</Badge>
            )}
            <ConnectButton />
          </div>
        </header>
        <main className="flex-1 space-y-6 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
