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
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      // Ẩn thanh navbar trong suốt quá trình cuộn thưởng thức Parallax Hero
      // Chỉ hiện ra khi người dùng cuộn tới các section nội dung (Marketplace, Architecture)
      const threshold = window.innerHeight * 3.05;
      setIsVisible(window.scrollY >= threshold);
    };
    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed z-50 flex items-center justify-between transition-all duration-500 ease-out",
        "top-3 left-4 right-4 mx-auto h-14 max-w-4xl rounded-full border border-slate-200/90 bg-white/92 px-6 backdrop-blur-2xl shadow-[0_12px_35px_rgba(15,23,42,0.08)]",
        isVisible
          ? "translate-y-0 opacity-100 pointer-events-auto"
          : "-translate-y-12 opacity-0 pointer-events-none"
      )}
    >
      {/* Brand Logo */}
      <Link to="/" className="group flex items-center gap-3">
        <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#E84142] to-[#A81D20] text-white font-black shadow-[0_0_20px_rgba(232,65,66,0.4)] transition-transform group-hover:scale-105">
          <Flame className="h-4 w-4 sm:h-5 sm:w-5 fill-white" />
        </div>
        <div className="flex flex-col">
          <span className="text-xs sm:text-sm font-black tracking-wider text-slate-900">
            AVAXAGENT <span className="text-[#E84142]">STUDIO</span>
          </span>
        </div>
      </Link>

      {/* Navigation Links */}
      <nav className="hidden items-center gap-6 md:flex">
        <a
          href="#marketplace-preview"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          Marketplace
        </a>
        <a
          href="#how-it-works"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          Quy trình
        </a>
        <a
          href="#architecture"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          Kiến trúc x402
        </a>
        <a
          href="#security"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          Bảo mật Turnkey
        </a>
        <Badge
          variant="outline"
          className="border-[#E84142]/30 bg-[#E84142]/10 text-[11px] font-bold text-[#E84142]"
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
              className="border-slate-200 bg-slate-50 text-xs font-semibold text-slate-800 hover:bg-slate-100"
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
              className="hidden text-xs font-semibold text-slate-600 hover:text-slate-900 sm:inline-flex"
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
