import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Flame } from "lucide-react";
import { useAccount } from "wagmi";

import { ConnectButton } from "@/components/connect-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { shortAddress } from "@/lib/format";
import { cn } from "@/lib/utils";

export function LandingNavbar() {
  const { address, isConnected } = useAccount();
  const [isPill, setIsPill] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsPill(window.scrollY > 80);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed z-50 flex items-center justify-between transition-all duration-500 ease-out",
        isPill
          ? "top-3 left-4 right-4 mx-auto h-14 max-w-4xl rounded-full border border-white/20 bg-[#07080D]/85 px-6 backdrop-blur-2xl shadow-[0_10px_35px_rgba(0,0,0,0.85)]"
          : "top-0 left-0 right-0 h-16 border-b border-white/10 bg-[#07080D]/75 px-4 backdrop-blur-xl sm:px-8"
      )}
    >
      {/* Brand Logo */}
      <Link to="/" className="group flex items-center gap-3">
        <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#E84142] to-[#A81D20] text-white font-black shadow-[0_0_20px_rgba(232,65,66,0.5)] transition-transform group-hover:scale-105">
          <Flame className="h-4 w-4 sm:h-5 sm:w-5 fill-white" />
        </div>
        <div className="flex flex-col">
          <span className="text-xs sm:text-sm font-black tracking-wider text-white">
            AVAXAGENT <span className="text-[#E84142]">STUDIO</span>
          </span>
          {!isPill && (
            <span className="font-mono text-[9px] tracking-widest text-slate-400 uppercase hidden sm:block">
              Avalanche C-Chain · Fuji
            </span>
          )}
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
              variant="outline"
              size="sm"
              className="border-white/20 bg-white/5 text-xs text-slate-200 backdrop-blur hover:bg-white/10"
            >
              <span>Dashboard ({shortAddress(address ?? "")})</span>
              <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Button>
          </Link>
        ) : (
          <Link to="/marketplace">
            <Button
              variant="ghost"
              size="sm"
              className="hidden text-xs text-slate-300 hover:text-white sm:inline-flex"
            >
              Khám phá Agent
            </Button>
          </Link>
        )}

        <ConnectButton />
      </div>
    </header>
  );
}
