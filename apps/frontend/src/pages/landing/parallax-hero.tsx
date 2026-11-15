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
  const mistRef = useRef<HTMLDivElement>(null);
  const headlineRef = useRef<HTMLDivElement>(null);
  const caveRef = useRef<HTMLImageElement>(null);
  const explorerRef = useRef<HTMLImageElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const scrollCueRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      // 60 FPS GSAP ScrollTrigger Timeline with 1.0s scrubbed inertia across 320vh
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 1.0,
        },
      });

      // ---------------------------------------------------------------------
      // PHASE 1 (0.0 -> 0.32): MÂY CHE KÍN -> RẼ MÂY ĐỂ LỘ ĐỈNH NÚI TUYẾT
      // ---------------------------------------------------------------------
      // Bầu trời zoom chiều sâu nhẹ nhàng xuyên suốt toàn bộ hành trình
      if (skyRef.current) {
        tl.to(skyRef.current, { scale: 1.15, ease: "none", duration: 100 }, 0);
      }

      // Lớp sương mây dày đặc che phủ 100% màn hình ban đầu tan biến dần
      if (mistRef.current) {
        tl.to(mistRef.current, { opacity: 0, ease: "power1.inOut", duration: 25 }, 0);
      }

      // Hướng dẫn cuộn ở vị trí scroll = 0 mờ dần và bay lên
      if (scrollCueRef.current) {
        tl.to(scrollCueRef.current, { opacity: 0, y: -25, ease: "power1.out", duration: 14 }, 0);
      }

      // Cụm mây bên trái (clouds03, clouds07) rẽ dạt mạnh sang trái
      if (cloud03Ref.current) {
        tl.to(cloud03Ref.current, { x: -500, opacity: 0.1, ease: "power1.out", duration: 32 }, 0);
      }
      if (cloud07Ref.current) {
        tl.to(cloud07Ref.current, { x: -440, opacity: 0.1, ease: "power1.out", duration: 32 }, 0);
      }

      // Cụm mây bên phải (clouds09, clouds05, clouds11) rẽ dạt mạnh sang phải
      if (cloud09Ref.current) {
        tl.to(cloud09Ref.current, { x: 440, opacity: 0.1, ease: "power1.out", duration: 32 }, 0);
      }
      if (cloud05Ref.current) {
        tl.to(cloud05Ref.current, { x: 500, opacity: 0.1, ease: "power1.out", duration: 32 }, 0);
      }
      if (cloud11Ref.current) {
        tl.to(cloud11Ref.current, { x: 540, opacity: 0.1, ease: "power1.out", duration: 32 }, 0);
      }

      // Mây dưới và mây trên tản dần lên và xuống
      if (cloud01Ref.current) {
        tl.to(cloud01Ref.current, { y: 160, opacity: 0.1, ease: "power1.out", duration: 28 }, 0);
      }
      if (cloud02Ref.current) {
        tl.to(cloud02Ref.current, { y: -110, opacity: 0.1, ease: "power1.out", duration: 28 }, 0);
      }

      // Đỉnh núi tuyết Mountains.png dần lộ diện từ sau làn mây dày, hiện rõ sừng sững
      if (mountRef.current) {
        tl.fromTo(
          mountRef.current,
          { opacity: 0.15, scale: 1.25, y: 35 },
          { opacity: 1, scale: 1.08, y: -20, ease: "power1.out", duration: 35 },
          0
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 2 (0.24 -> 0.52): HIỆN RA CHỮ AVAXAGENT STUDIO
      // ---------------------------------------------------------------------
      if (headlineRef.current) {
        tl.fromTo(
          headlineRef.current,
          { opacity: 0, y: 60, scale: 0.88 },
          { opacity: 1, y: 0, scale: 1.0, ease: "power2.out", duration: 26 },
          24
        );
        // Sau đó zoom nhẹ rất cinematic làm tâm điểm phía xa
        tl.to(headlineRef.current, { scale: 1.08, ease: "none", duration: 48 }, 52);
      }

      // ---------------------------------------------------------------------
      // PHASE 3 (0.46 -> 0.76): TRẦN HANG ĐỘNG CAVE.PNG BUÔNG / UỐN XUỐNG
      // ---------------------------------------------------------------------
      if (caveRef.current) {
        tl.fromTo(
          caveRef.current,
          { opacity: 0, yPercent: -55, scale: 1.18 },
          { opacity: 1, yPercent: 0, scale: 1.0, ease: "power2.out", duration: 30 },
          46
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 4 (0.70 -> 0.96): EXPLORER.PNG NỔI LÊN TRÊN MỎM ĐÁ & NÚT CTA
      // ---------------------------------------------------------------------
      if (explorerRef.current) {
        tl.fromTo(
          explorerRef.current,
          { opacity: 0, y: 160, scale: 0.92 },
          { opacity: 1, y: 0, scale: 1.0, ease: "power2.out", duration: 24 },
          70
        );
      }

      // Cụm CTA Controls: xuất hiện ngay sau khi Explorer định hình
      if (ctaRef.current) {
        tl.fromTo(
          ctaRef.current,
          { opacity: 0, y: 35 },
          {
            opacity: 1,
            y: 0,
            ease: "power2.out",
            duration: 20,
            onUpdate: function () {
              const currentProgress = this.progress();
              if (ctaRef.current) {
                ctaRef.current.style.pointerEvents = currentProgress > 0.4 ? "auto" : "none";
              }
            },
          },
          76
        );
      }
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="relative h-[320vh] w-full bg-[#08090E]">
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

        {/* Layer 2: Mountains (Sunlit alpine peaks revealed behind parted clouds) */}
        <img
          ref={mountRef}
          src="/assets/bxcmuse/Mountains.png"
          alt="Mountains"
          className="pointer-events-none absolute inset-0 h-[115%] w-full object-cover object-[center_35%] select-none will-change-transform"
          style={{ zIndex: 2 }}
        />

        {/* Layer 3: Big Cinematic Headline (AVAXAGENT STUDIO revealed in Phase 2) */}
        <div
          ref={headlineRef}
          className="pointer-events-none absolute top-[14%] sm:top-[16%] left-0 right-0 flex flex-col items-center justify-center text-center select-none px-4 will-change-transform"
          style={{ zIndex: 3 }}
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-black/60 px-4 py-1.5 backdrop-blur-md shadow-2xl mb-3">
            <span className="h-2 w-2 rounded-full bg-[#E84142] animate-pulse" />
            <span className="text-xs font-semibold tracking-wider text-slate-100 uppercase font-mono">
              The Autonomous AI Agent Studio · Avalanche C-Chain
            </span>
          </div>

          {/* Big Bold Headline */}
          <h1 className="text-6xl font-black tracking-tight text-white drop-shadow-[0_15px_45px_rgba(0,0,0,0.95)] sm:text-8xl md:text-9xl leading-none">
            AVAXAGENT
          </h1>
          <div className="text-2xl font-extrabold tracking-[0.25em] uppercase bg-gradient-to-r from-white via-slate-100 to-[#FFA4A6] bg-clip-text text-transparent drop-shadow-[0_8px_30px_rgba(0,0,0,0.95)] sm:text-4xl md:text-5xl mt-2">
            STUDIO
          </div>
        </div>

        {/* Layer 4: Clouds Parting & Dense Initial Mist Covering (Che kín ở scroll = 0) */}
        <img
          ref={cloud03Ref}
          src="/assets/bxcmuse/clouds03.png"
          alt="Clouds 03"
          className="pointer-events-none absolute top-[2%] -left-[10%] w-[125%] max-w-none opacity-90 select-none will-change-transform"
          style={{ zIndex: 5 }}
        />
        <img
          ref={cloud07Ref}
          src="/assets/bxcmuse/clouds07.png"
          alt="Clouds 07"
          className="pointer-events-none absolute top-[10%] -left-[5%] w-[115%] max-w-none opacity-85 select-none will-change-transform"
          style={{ zIndex: 5 }}
        />
        <img
          ref={cloud09Ref}
          src="/assets/bxcmuse/clouds09.png"
          alt="Clouds 09"
          className="pointer-events-none absolute top-[8%] left-[10%] w-[110%] max-w-none opacity-85 select-none will-change-transform"
          style={{ zIndex: 5 }}
        />
        <img
          ref={cloud05Ref}
          src="/assets/bxcmuse/clouds05.png"
          alt="Clouds 05"
          className="pointer-events-none absolute top-[22%] left-[15%] w-[105%] max-w-none opacity-90 select-none will-change-transform"
          style={{ zIndex: 6 }}
        />
        <img
          ref={cloud11Ref}
          src="/assets/bxcmuse/clouds11.png"
          alt="Clouds 11"
          className="pointer-events-none absolute top-[18%] left-[8%] w-[110%] max-w-none opacity-85 select-none will-change-transform"
          style={{ zIndex: 6 }}
        />
        <img
          ref={cloud01Ref}
          src="/assets/bxcmuse/clouds01.png"
          alt="Clouds 01"
          className="pointer-events-none absolute bottom-0 left-0 w-full opacity-95 select-none will-change-transform"
          style={{ zIndex: 6 }}
        />
        <img
          ref={cloud02Ref}
          src="/assets/bxcmuse/clouds02.png"
          alt="Clouds 02"
          className="pointer-events-none absolute top-[4%] left-[40%] w-[50%] max-w-none opacity-95 select-none will-change-transform"
          style={{ zIndex: 6 }}
        />

        {/* Dense Initial Mist Overlay to guarantee 100% cloudy whiteout at scroll = 0 */}
        <div
          ref={mistRef}
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/70 via-white/85 to-slate-200/90 backdrop-blur-[3px] select-none will-change-transform"
          style={{ zIndex: 7 }}
        />

        {/* Layer 5: Trần hang động Cave.png (Buông / uốn xuống ở Phase 3) */}
        <img
          ref={caveRef}
          src="/assets/bxcmuse/Cave.png"
          alt="Cave Frame"
          className="pointer-events-none absolute inset-0 h-full w-full object-cover object-top select-none will-change-transform drop-shadow-[0_20px_50px_rgba(0,0,0,0.8)]"
          style={{ zIndex: 10 }}
        />

        {/* Layer 6: Explorer.png (Nhà thám hiểm nổi lên ở Phase 4) */}
        <img
          ref={explorerRef}
          src="/assets/bxcmuse/Explorer.png"
          alt="Explorer"
          className="pointer-events-none absolute bottom-0 left-0 w-full h-[65%] sm:h-[75%] object-contain object-bottom select-none will-change-transform drop-shadow-[0_15px_35px_rgba(0,0,0,0.9)]"
          style={{ zIndex: 12 }}
        />

        {/* Initial Scroll Cue (Hiển thị ngay tại scroll = 0 báo hiệu cuộn xuống) */}
        <div
          ref={scrollCueRef}
          className="pointer-events-none absolute bottom-12 left-0 right-0 z-30 flex flex-col items-center justify-center gap-2 text-center select-none"
        >
          <div className="flex items-center gap-2 rounded-full border border-slate-700/60 bg-black/70 px-4 py-2 backdrop-blur-md shadow-2xl">
            <span className="font-mono text-xs font-bold tracking-widest uppercase text-slate-100">
              Cuộn để khám phá
            </span>
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#E84142] animate-bounce">
              <ArrowDown className="h-3 w-3 text-white" />
            </div>
          </div>
        </div>

        {/* Layer 7: Action CTA Buttons & Subtitle (Nổi lên cùng Explorer ở Phase 4) */}
        <div
          ref={ctaRef}
          className="absolute bottom-6 sm:bottom-10 left-0 right-0 z-20 flex flex-col items-center justify-center gap-3.5 text-center select-none px-4 will-change-transform"
          style={{ pointerEvents: "none" }}
        >
          {/* Subtitle with dark backdrop pill for crystal-clear readability */}
          <p className="mx-auto max-w-lg rounded-2xl border border-white/15 bg-black/70 px-5 py-2.5 text-xs sm:text-sm leading-relaxed text-slate-100 backdrop-blur-md shadow-2xl font-normal">
            Khởi tạo, vận hành và thương mại hóa AI Agent tự quản.
            Bảo mật ví Turnkey Enclave, mint định danh ERC-8004 và thanh toán micropayment x402.
          </p>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-4">
            <a href="#marketplace-preview">
              <Button
                size="lg"
                className="bg-gradient-to-r from-[#E84142] to-[#C72A2D] px-8 py-6 text-sm font-bold text-white shadow-[0_0_35px_rgba(232,65,66,0.65)] transition-all hover:scale-105 hover:brightness-110 active:scale-95 cursor-pointer"
              >
                <span>Khám phá Marketplace</span>
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </a>

            <Link to="/agents/new">
              <Button
                variant="outline"
                size="lg"
                className="border-white/30 bg-black/70 px-7 py-6 text-sm font-semibold text-slate-100 backdrop-blur-md transition-all hover:border-white/60 hover:bg-white/15 hover:scale-105 active:scale-95 cursor-pointer"
              >
                <Bot className="mr-2 h-4 w-4 text-[#FFA4A6]" />
                <span>Khởi tạo Agent mới</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Soft Bottom Feather Fade into #08090E content sections */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#08090E] via-[#08090E]/60 to-transparent"
          style={{ zIndex: 18 }}
        />
      </div>
    </section>
  );
}
