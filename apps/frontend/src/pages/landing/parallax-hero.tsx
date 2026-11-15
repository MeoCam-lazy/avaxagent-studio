import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowRight, Bot } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ParallaxHero() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let ticking = false;

    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const scrollY = window.scrollY;
          // Pinned viewport track across 90% of screen height
          const maxScroll = window.innerHeight * 0.9;
          const p = Math.min(1, Math.max(0, scrollY / maxScroll));
          setProgress(p);
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Exact Bxcmuse Parallax Physics (from Figma Community "Parallax Scroll Effect (Explore)")
  // 1. Sky: subtle zoom for depth
  const skyScale = 1 + progress * 0.08;

  // 2. Mountains: gentle zoom & elevation
  const mountScale = 1 + progress * 0.16;
  const mountY = progress * -24;

  // 3. Volumetric Clouds Parting (clouds01 - clouds11)
  const cloudLeftX = progress * -280;
  const cloudRightX = progress * 300;
  const cloudDownY = progress * 100;
  const cloudUpY = progress * -70;

  // 4. Cinematic Typography & CTA: gentle scale forward and graceful fade
  const textScale = 1 + progress * 0.12;
  const textOpacity = Math.max(0, 1 - progress * 2.2);
  const textY = progress * -35;

  return (
    <section className="relative h-[190vh] w-full bg-[#08090E]">
      {/* Sticky Fullscreen Stage (Pinned at top 0 while scrolling) */}
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        {/* Layer 1: Bg_Sky */}
        <img
          src="/assets/bxcmuse/Bg_Sky.png"
          alt="Sky"
          className="pointer-events-none absolute inset-0 h-full w-full object-cover object-top select-none will-change-transform"
          style={{
            transform: `scale(${skyScale})`,
            transformOrigin: "center top",
            zIndex: 1,
          }}
        />

        {/* Layer 2: Mountains (Sunlit alpine peak framed at center-top) */}
        <img
          src="/assets/bxcmuse/Mountains.png"
          alt="Mountains"
          className="pointer-events-none absolute inset-0 h-[115%] w-full object-cover object-[center_32%] select-none will-change-transform"
          style={{
            transform: `scale(${mountScale}) translateY(${mountY}px)`,
            transformOrigin: "center center",
            zIndex: 2,
          }}
        />

        {/* Layer 3: Back Clouds (clouds03, clouds07, clouds09) */}
        <img
          src="/assets/bxcmuse/clouds03.png"
          alt="Clouds 03"
          className="pointer-events-none absolute top-[6%] -left-[15%] w-[130%] max-w-none opacity-60 select-none will-change-transform"
          style={{
            transform: `translateX(${cloudLeftX * 1.1}px)`,
            zIndex: 3,
          }}
        />
        <img
          src="/assets/bxcmuse/clouds07.png"
          alt="Clouds 07"
          className="pointer-events-none absolute top-[14%] -left-[10%] w-[120%] max-w-none opacity-55 select-none will-change-transform"
          style={{
            transform: `translateX(${cloudLeftX}px)`,
            zIndex: 3,
          }}
        />
        <img
          src="/assets/bxcmuse/clouds09.png"
          alt="Clouds 09"
          className="pointer-events-none absolute top-[12%] left-[5%] w-[110%] max-w-none opacity-50 select-none will-change-transform"
          style={{
            transform: `translateX(${cloudRightX * 0.75}px)`,
            zIndex: 3,
          }}
        />

        {/* Layer 4: Big Cinematic Headline (Sandwiched between back & front clouds like 'EXPLORE' in Figma) */}
        <div
          className="pointer-events-none absolute top-[16%] sm:top-[18%] left-0 right-0 z-4 flex flex-col items-center justify-center text-center select-none px-4"
          style={{
            opacity: textOpacity,
            transform: `scale(${textScale}) translateY(${textY}px)`,
            transformOrigin: "center center",
          }}
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-black/55 px-4 py-1.5 backdrop-blur-md shadow-2xl mb-3">
            <span className="h-2 w-2 rounded-full bg-[#E84142] animate-pulse" />
            <span className="text-xs font-semibold tracking-wider text-slate-100 uppercase font-mono">
              The Autonomous AI Agent Studio · Avalanche C-Chain
            </span>
          </div>

          {/* Big Bold Headline */}
          <h1 className="text-6xl font-black tracking-tight text-white drop-shadow-[0_15px_40px_rgba(0,0,0,0.9)] sm:text-8xl md:text-9xl leading-none">
            AVAXAGENT
          </h1>
          <div className="text-2xl font-extrabold tracking-[0.25em] uppercase bg-gradient-to-r from-white via-slate-100 to-[#FFA4A6] bg-clip-text text-transparent drop-shadow-[0_8px_25px_rgba(0,0,0,0.95)] sm:text-4xl md:text-5xl mt-2">
            STUDIO
          </div>
        </div>

        {/* Layer 5: Foreground & Midground Clouds (clouds05, clouds11, clouds01, clouds02) */}
        <img
          src="/assets/bxcmuse/clouds05.png"
          alt="Clouds 05"
          className="pointer-events-none absolute top-[28%] left-[20%] w-[95%] max-w-none opacity-70 select-none will-change-transform"
          style={{
            transform: `translateX(${cloudRightX}px)`,
            zIndex: 5,
          }}
        />
        <img
          src="/assets/bxcmuse/clouds11.png"
          alt="Clouds 11"
          className="pointer-events-none absolute top-[25%] left-[12%] w-[100%] max-w-none opacity-60 select-none will-change-transform"
          style={{
            transform: `translateX(${cloudRightX * 1.2}px)`,
            zIndex: 5,
          }}
        />
        <img
          src="/assets/bxcmuse/clouds01.png"
          alt="Clouds 01"
          className="pointer-events-none absolute bottom-0 left-0 w-full opacity-75 select-none will-change-transform"
          style={{
            transform: `translateY(${cloudDownY}px)`,
            zIndex: 6,
          }}
        />
        <img
          src="/assets/bxcmuse/clouds02.png"
          alt="Clouds 02"
          className="pointer-events-none absolute top-[8%] left-[46%] w-[42%] max-w-none opacity-85 select-none will-change-transform"
          style={{
            transform: `translateY(${cloudUpY}px)`,
            zIndex: 6,
          }}
        />

        {/* Layer 6: Action CTA Buttons & Subtitle (Layered above front clouds for 100% legibility) */}
        <div
          className="absolute bottom-8 sm:bottom-12 left-0 right-0 z-20 flex flex-col items-center justify-center gap-4 text-center select-none px-4"
          style={{
            opacity: textOpacity,
            pointerEvents: textOpacity > 0.2 ? "auto" : "none",
            transform: `translateY(${textY * 0.5}px)`,
          }}
        >
          {/* Subtitle with dark backdrop pill for crystal-clear readability against clouds */}
          <p className="mx-auto max-w-lg rounded-2xl border border-white/10 bg-black/60 px-5 py-2.5 text-xs sm:text-sm leading-relaxed text-slate-100 backdrop-blur-md shadow-2xl font-normal">
            Khởi tạo, vận hành và thương mại hóa AI Agent tự quản.
            Bảo mật ví Turnkey Enclave, mint định danh ERC-8004 và thanh toán micropayment x402.
          </p>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-4">
            <a href="#marketplace-preview">
              <Button
                size="lg"
                className="bg-gradient-to-r from-[#E84142] to-[#C72A2D] px-8 py-6 text-sm font-bold text-white shadow-[0_0_35px_rgba(232,65,66,0.65)] transition-all hover:scale-105 hover:brightness-110 active:scale-95"
              >
                <span>Khám phá Marketplace</span>
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </a>

            <Link to="/agents/new">
              <Button
                variant="outline"
                size="lg"
                className="border-white/30 bg-black/70 px-7 py-6 text-sm font-semibold text-slate-100 backdrop-blur-md transition-all hover:border-white/60 hover:bg-white/15 hover:scale-105 active:scale-95"
              >
                <Bot className="mr-2 h-4 w-4 text-[#FFA4A6]" />
                <span>Khởi tạo Agent mới</span>
              </Button>
            </Link>
          </div>

          {/* Scroll Cue */}
          <div className="flex flex-col items-center gap-1.5 text-slate-200 drop-shadow mt-1">
            <span className="font-mono text-[11px] tracking-widest uppercase">
              Cuộn để khám phá
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-full border border-white/25 bg-black/50 animate-bounce">
              <ArrowDown className="h-3.5 w-3.5 text-[#FFA4A6]" />
            </div>
          </div>
        </div>

        {/* Layer 7: Soft Bottom Feather Fade into #08090E content sections */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0 h-36 bg-gradient-to-t from-[#08090E] via-[#08090E]/60 to-transparent"
          style={{ zIndex: 15 }}
        />
      </div>
    </section>
  );
}
