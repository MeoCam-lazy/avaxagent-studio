import { Link } from "react-router-dom";
import { ArrowRight, Flame } from "lucide-react";
import { useAccount } from "wagmi";

import { ConnectButton } from "@/components/connect-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { shortAddress } from "@/lib/format";

export function LandingNavbar() {
  const { address, isConnected } = useAccount();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex h-16 items-center justify-between border-b border-white/10 bg-[#07080D]/75 px-4 backdrop-blur-xl sm:px-8">
      {/* Brand Logo */}
      <Link to="/" className="group flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#E84142] to-[#A81D20] text-white font-black shadow-[0_0_20px_rgba(232,65,66,0.5)] transition-transform group-hover:scale-105">
          <Flame className="h-5 w-5 fill-white" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-black tracking-wider text-white sm:text-base">
            AVAXAGENT <span className="text-[#E84142]">STUDIO</span>
          </span>
          <span className="font-mono text-[10px] tracking-widest text-slate-400 uppercase">
            Avalanche C-Chain · Fuji
          </span>
        </div>
      </Link>

      {/* Navigation Links */}
      <nav className="hidden items-center gap-6 md:flex">
        <a
          href="#marketplace-preview"
          className="text-xs font-medium text-slate-300 transition-colors hover:text-white"
        >
          Marketplace
        </a>
        <a
          href="#architecture"
          className="text-xs font-medium text-slate-300 transition-colors hover:text-white"
        >
          Kiến trúc x402
        </a>
        <a
          href="#security"
          className="text-xs font-medium text-slate-300 transition-colors hover:text-white"
        >
          Bảo mật Turnkey
        </a>
        <Badge
          variant="outline"
          className="border-[#E84142]/40 bg-[#E84142]/10 text-[11px] text-[#FFA4A6]"
        >
          UniHack 2026
        </Badge>
      </nav>

      {/* Action / Connect Wallet */}
      <div className="flex items-center gap-3">
        {isConnected ? (
          <Link to="/dashboard">
            <Button
              size="sm"
              className="bg-gradient-to-r from-[#E84142] to-[#C72A2D] text-xs font-bold text-white shadow-[0_0_20px_rgba(232,65,66,0.4)] hover:brightness-110"
            >
              <span>Vào Studio ({shortAddress(address)})</span>
              <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Button>
          </Link>
        ) : (
          <div className="flex items-center gap-2">
            <Link to="/marketplace" className="hidden sm:inline-block">
              <Button
                variant="outline"
                size="sm"
                className="border-white/20 bg-white/5 text-xs text-slate-200 hover:bg-white/10"
              >
                Khám phá Agent
              </Button>
            </Link>
            <ConnectButton />
          </div>
        )}
      </div>
    </header>
  );
}
