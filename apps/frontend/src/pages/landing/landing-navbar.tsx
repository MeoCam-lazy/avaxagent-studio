import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Flame, Languages } from "lucide-react";
import { useAccount } from "wagmi";

import { ConnectButton } from "@/components/connect-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LANDING_COPY, type LandingLang } from "@/pages/landing/landing-i18n";

export function LandingNavbar({
  lang,
  onToggleLang,
}: {
  lang: LandingLang;
  onToggleLang: () => void;
}) {
  const { isConnected } = useAccount();
  const [isVisible, setIsVisible] = useState(false);
  const t = LANDING_COPY[lang].nav;

  useEffect(() => {
    const handleScroll = () => {
      const threshold = window.innerHeight * 2.15;
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
        "top-3 left-4 right-4 mx-auto h-14 max-w-5xl rounded-full border border-slate-200/90 bg-white/95 px-5 sm:px-6 backdrop-blur-2xl shadow-[0_12px_35px_rgba(15,23,42,0.08)]",
        isVisible
          ? "translate-y-0 opacity-100 pointer-events-auto"
          : "-translate-y-12 opacity-0 pointer-events-none",
      )}
    >
      <Link to="/" className="group flex items-center gap-2.5 sm:gap-3 shrink-0">
        <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#E84142] to-[#A81D20] text-white font-black shadow-[0_0_20px_rgba(232,65,66,0.4)] transition-transform group-hover:scale-105">
          <Flame className="h-4 w-4 sm:h-5 sm:w-5 fill-white" />
        </div>
        <span className="text-xs sm:text-sm font-black tracking-wider text-slate-900">
          AVAXAGENT <span className="text-[#E84142]">STUDIO</span>
        </span>
      </Link>

      <nav className="hidden items-center gap-5 lg:gap-6 md:flex">
        <a
          href="#marketplace-preview"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          {t.marketplace}
        </a>
        <a
          href="#architecture"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          {t.architecture}
        </a>
        <a
          href="#metrics"
          className="text-xs font-semibold text-slate-600 transition-colors hover:text-[#E84142]"
        >
          {t.metrics}
        </a>
        <Badge
          variant="outline"
          className="border-[#E84142]/30 bg-[#E84142]/10 text-[11px] font-bold text-[#E84142]"
        >
          UniHack 2026
        </Badge>
      </nav>

      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        <button
          type="button"
          onClick={onToggleLang}
          title="Chuyển ngôn ngữ VI / EN"
          className="inline-flex h-8 items-center gap-1 rounded-full border border-slate-200 bg-slate-100/80 px-2.5 text-[11px] font-bold text-slate-700 transition-colors hover:border-[#E84142]/40 hover:text-[#E84142]"
        >
          <Languages className="size-3.5" />
          <span>{lang.toUpperCase()}</span>
        </button>

        {isConnected ? (
          <Link to="/dashboard">
            <Button
              size="sm"
              className="bg-[#E84142] hover:bg-[#D33738] text-white text-xs font-semibold shadow-sm h-8 px-3"
            >
              <span>{t.dashboard}</span>
              <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Button>
          </Link>
        ) : (
          <Link to="/marketplace">
            <Button
              variant="ghost"
              size="sm"
              className="hidden text-xs font-semibold text-slate-600 hover:text-slate-900 sm:inline-flex h-8"
            >
              {t.explore}
            </Button>
          </Link>
        )}

        <ConnectButton
          label={t.connect}
          signingLabel={t.signing}
          logoutLabel={t.disconnect}
        />
      </div>
    </header>
  );
}
