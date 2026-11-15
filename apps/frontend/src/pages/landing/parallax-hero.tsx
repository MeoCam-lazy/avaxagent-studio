import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowRight, Bot } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { Button } from "@/components/ui/button";

export function ParallaxHero() {
  const containerRef = useRef<HTMLDivElement>(null);
  const skyRef = useRef<HTMLImageElement>(null);
  const mountRef = useRef<HTMLImageElement>(null);
  const cloud03Ref = useRef<HTMLImageElement>(null);
  const cloud07Ref = useRef<HTMLImageElement>(null);
  const cloud09Ref = useRef<HTMLImageElement>(null);
  const cloud05Ref = useRef<HTMLImageElement>(null);
  const cloud11Ref = useRef<HTMLImageElement>(null);
  const cloud01Ref = useRef<HTMLImageElement>(null);
  const cloud02Ref = useRef<HTMLImageElement>(null);
  const headlineRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      // 60 FPS GSAP ScrollTrigger Timeline with 1.0s scrubbed inertia
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 1.0,
        },
      });

      // 1. Sky: subtle depth zoom
      if (skyRef.current) {
        tl.to(skyRef.current, { scale: 1.08, ease: "none" }, 0);
      }

      // 2. Mountains: gentle zoom & elevation
      if (mountRef.current) {
        tl.to(mountRef.current, { scale: 1.16, y: -28, ease: "none" }, 0);
      }

      // 3. Clouds Parting Left (clouds03, clouds07)
      if (cloud03Ref.current) {
        tl.to(cloud03Ref.current, { x: -320, ease: "power1.out" }, 0);
      }
      if (cloud07Ref.current) {
        tl.to(cloud07Ref.current, { x: -280, ease: "power1.out" }, 0);
      }

      // 4. Clouds Parting Right (clouds09, clouds05, clouds11)
      if (cloud09Ref.current) {
        tl.to(cloud09Ref.current, { x: 260, ease: "power1.out" }, 0);
      }
      if (cloud05Ref.current) {
        tl.to(cloud05Ref.current, { x: 320, ease: "power1.out" }, 0);
      }
      if (cloud11Ref.current) {
        tl.to(cloud11Ref.current, { x: 360, ease: "power1.out" }, 0);
      }

      // 5. Cloud 01 (Downwards dissolve) & Cloud 02 (Upwards float)
      if (cloud01Ref.current) {
        tl.to(cloud01Ref.current, { y: 110, opacity: 0.1, ease: "power1.out" }, 0);
      }
      if (cloud02Ref.current) {
        tl.to(cloud02Ref.current, { y: -80, opacity: 0.2, ease: "power1.out" }, 0);
      }

      // 6. Headline & Badge: gentle forward scale & fade out
      if (headlineRef.current) {
        tl.to(
          headlineRef.current,
          { scale: 1.15, y: -50, opacity: 0, ease: "power2.in" },
          0
        );
      }

      // 7. CTA Controls: smooth fade out and disable clicks on scroll
      if (ctaRef.current) {
        tl.to(
          ctaRef.current,
          {
            y: -30,
            opacity: 0,
            ease: "power2.in",
            onUpdate: function () {
              const currentProgress = this.progress();
              if (ctaRef.current) {
                ctaRef.current.style.pointerEvents = currentProgress > 0.35 ? "none" : "auto";
              }
            },
          },
          0
        );
      }
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="relative h-[190vh] w-full bg-[#08090E]">
      {/* Sticky Fullscreen Stage (Firmly pinned at top 0 while scrolling) */}
      <div className="sticky top-0 h-screen w-full overflow-hidden">
        {/* Layer 1: Bg_Sky */}
        <img
          ref={skyRef}
          src="/assets/bxcmuse/Bg_Sky.png"
          alt="Sky"
          className="pointer-events-none absolute inset-0 h-full w-full object-cover object-top select-none will-change-transform"
          style={{ zIndex: 1 }}
        />

        {/* Layer 2: Mountains (Sunlit alpine peak framed at center-top) */}
        <img
          ref={mountRef}
          src="/assets/bxcmuse/Mountains.png"
          alt="Mountains"
          className="pointer-events-none absolute inset-0 h-[115%] w-full object-cover object-[center_32%] select-none will-change-transform"
          style={{ zIndex: 2 }}
        />

        {/* Layer 3: Back Clouds (clouds03, clouds07, clouds09) */}
        <img
          ref={cloud03Ref}
          src="/assets/bxcmuse/clouds03.png"
          alt="Clouds 03"
          className="pointer-events-none absolute top-[6%] -left-[15%] w-[130%] max-w-none opacity-60 select-none will-change-transform"
          style={{ zIndex: 3 }}
        />
        <img
          ref={cloud07Ref}
          src="/assets/bxcmuse/clouds07.png"
          alt="Clouds 07"
          className="pointer-events-none absolute top-[14%] -left-[10%] w-[120%] max-w-none opacity-55 select-none will-change-transform"
          style={{ zIndex: 3 }}
        />
        <img
          ref={cloud09Ref}
          src="/assets/bxcmuse/clouds09.png"
          alt="Clouds 09"
          className="pointer-events-none absolute top-[12%] left-[5%] w-[110%] max-w-none opacity-50 select-none will-change-transform"
          style={{ zIndex: 3 }}
        />

        {/* Layer 4: Big Cinematic Headline (Sandwiched between clouds like 'EXPLORE' in Figma) */}
        <div
          ref={headlineRef}
          className="pointer-events-none absolute top-[16%] sm:top-[18%] left-0 right-0 z-4 flex flex-col items-center justify-center text-center select-none px-4 will-change-transform"
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
          ref={cloud05Ref}
          src="/assets/bxcmuse/clouds05.png"
          alt="Clouds 05"
          className="pointer-events-none absolute top-[28%] left-[20%] w-[95%] max-w-none opacity-70 select-none will-change-transform"
          style={{ zIndex: 5 }}
        />
        <img
          ref={cloud11Ref}
          src="/assets/bxcmuse/clouds11.png"
          alt="Clouds 11"
          className="pointer-events-none absolute top-[25%] left-[12%] w-[100%] max-w-none opacity-60 select-none will-change-transform"
          style={{ zIndex: 5 }}
        />
        <img
          ref={cloud01Ref}
          src="/assets/bxcmuse/clouds01.png"
          alt="Clouds 01"
          className="pointer-events-none absolute bottom-0 left-0 w-full opacity-75 select-none will-change-transform"
          style={{ zIndex: 6 }}
        />
        <img
          ref={cloud02Ref}
          src="/assets/bxcmuse/clouds02.png"
          alt="Clouds 02"
          className="pointer-events-none absolute top-[8%] left-[46%] w-[42%] max-w-none opacity-85 select-none will-change-transform"
          style={{ zIndex: 6 }}
        />

        {/* Layer 6: Action CTA Buttons & Subtitle (Elevated to z-20 for high-contrast clickability) */}
        <div
          ref={ctaRef}
          className="absolute bottom-8 sm:bottom-12 left-0 right-0 z-20 flex flex-col items-center justify-center gap-4 text-center select-none px-4 will-change-transform"
        >
          {/* Subtitle with dark backdrop pill for crystal-clear readability */}
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
