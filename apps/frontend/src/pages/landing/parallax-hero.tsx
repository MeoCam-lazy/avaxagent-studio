import { useEffect, useRef } from "react";
import { ChevronDown, Languages } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { LANDING_COPY, type LandingLang } from "@/pages/landing/landing-i18n";

export function ParallaxHero({
  lang,
  onToggleLang,
}: {
  lang: LandingLang;
  onToggleLang: () => void;
}) {
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
  const scrollCueRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      // Đảm bảo trạng thái ban đầu của các asset tầng sau luôn là opacity 0 (chống FOUC khi tải trang)
      gsap.set([caveRef.current, explorerRef.current, headlineRef.current], { opacity: 0 });
      gsap.set(mountRef.current, { opacity: 0.15 });

      // 60 FPS GSAP ScrollTrigger Timeline with 0.5s scrubbed inertia across 280vh
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 0.5,
        },
      });

      // ---------------------------------------------------------------------
      // PHASE 1 (0.0 -> 0.24): MÂY CHE KÍN -> RẼ MÂY ĐỂ LỘ ĐỈNH NÚI TUYẾT & BẦU TRỜI
      // ---------------------------------------------------------------------
      // Bầu trời zoom chiều sâu nhẹ nhàng
      if (skyRef.current) {
        tl.to(skyRef.current, { scale: 1.12, ease: "none", duration: 100 }, 0);
      }

      // Lớp sương mây dày đặc che phủ 100% màn hình ban đầu tan biến dần
      if (mistRef.current) {
        tl.to(mistRef.current, { opacity: 0, ease: "power1.inOut", duration: 18 }, 0);
      }

      // Hướng dẫn cuộn ban đầu mờ dần ngay khi bắt đầu cuộn chuột
      if (scrollCueRef.current) {
        tl.to(scrollCueRef.current, { opacity: 0, y: -25, ease: "power1.out", duration: 10 }, 0);
      }

      // Cụm mây bên trái (clouds03, clouds07) rẽ dạt mạnh sang trái
      if (cloud03Ref.current) {
        tl.to(cloud03Ref.current, { x: -550, opacity: 0.05, ease: "power1.out", duration: 24 }, 0);
      }
      if (cloud07Ref.current) {
        tl.to(cloud07Ref.current, { x: -480, opacity: 0.05, ease: "power1.out", duration: 24 }, 0);
      }

      // Cụm mây bên phải (clouds09, clouds05, clouds11) rẽ dạt mạnh sang phải
      if (cloud09Ref.current) {
        tl.to(cloud09Ref.current, { x: 480, opacity: 0.05, ease: "power1.out", duration: 24 }, 0);
      }
      if (cloud05Ref.current) {
        tl.to(cloud05Ref.current, { x: 550, opacity: 0.05, ease: "power1.out", duration: 24 }, 0);
      }
      if (cloud11Ref.current) {
        tl.to(cloud11Ref.current, { x: 580, opacity: 0.05, ease: "power1.out", duration: 24 }, 0);
      }

      // Mây dưới và mây trên tản dần
      if (cloud01Ref.current) {
        tl.to(cloud01Ref.current, { y: 160, opacity: 0.05, ease: "power1.out", duration: 22 }, 0);
      }
      if (cloud02Ref.current) {
        tl.to(cloud02Ref.current, { y: -120, opacity: 0.05, ease: "power1.out", duration: 22 }, 0);
      }

      // Đỉnh núi tuyết Mountains.png lộ diện: hiển thị trọn vẹn đỉnh núi nhọn và sườn núi đón nắng
      if (mountRef.current) {
        tl.fromTo(
          mountRef.current,
          { opacity: 0.15, y: 40 },
          { opacity: 1, y: 0, ease: "power1.out", duration: 24 },
          0
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 2 (0.18 -> 0.44): VÒM HANG CAVE.PNG CAMERA PULL-BACK (DOLLY OUT)
      // Khóa chặt trục Y, vòm hang từ ngoài mép màn hình nhẹ nhàng thu lại ôm khung cảnh
      // ---------------------------------------------------------------------
      if (caveRef.current) {
        tl.fromTo(
          caveRef.current,
          { opacity: 0, scale: 1.35, y: 0 },
          { opacity: 1, scale: 1.0, y: 0, ease: "power1.out", duration: 26 },
          18
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 3 (0.35 -> 0.57): EXPLORER.PNG XUẤT HIỆN SỪNG SỮNG TRÊN MỎM TUYẾT
      // ---------------------------------------------------------------------
      if (explorerRef.current) {
        tl.fromTo(
          explorerRef.current,
          { opacity: 0, y: 35, scale: 0.94 },
          { opacity: 1, y: 0, scale: 1.0, ease: "power2.out", duration: 22 },
          35
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 4 (0.48 -> 0.65): CHỮ AVAXAGENT STUDIO BỪNG SÁNG SỚM (TITLE DROP CLIMAX)
      // Xuất hiện kiêu hãnh ngay khoảng trời mở giữa vòm hang và đỉnh núi
      // ---------------------------------------------------------------------
      if (headlineRef.current) {
        tl.fromTo(
          headlineRef.current,
          { opacity: 0, y: 30, scale: 0.92 },
          { opacity: 1, y: 0, scale: 1.0, ease: "power2.out", duration: 17 },
          48
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 5 (0.65 -> 1.00): KHOẢNG NGHỈ DÀNH RIÊNG ĐỂ ĐỌC CHỮ & NGẮM KIỆT TÁC
      // Toàn bộ tựa đề AVAXAGENT STUDIO và bức tranh giữ nguyên 100% trong suốt 35% quãng cuộn
      // Giúp người dùng thong thả đọc tên dự án, cảm nhận trọn vẹn visual trước khi vào Marketplace
      // ---------------------------------------------------------------------
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="relative h-[280vh] w-full bg-[#08090E]">
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

        {/* Layer 2: Mountains (Đỉnh núi tuyết đón nắng, xóa triệt để vết cắt thẳng đứng bằng mask-image) */}
        <img
          ref={mountRef}
          src="/assets/bxcmuse/Mountains.png"
          alt="Mountains"
          className="pointer-events-none absolute top-[15%] sm:top-[18%] left-1/2 -translate-x-1/2 w-[114vw] sm:w-[108vw] max-w-none h-auto select-none will-change-transform drop-shadow-[0_15px_30px_rgba(0,0,0,0.7)] opacity-20"
          style={{
            zIndex: 2,
            opacity: 0.2,
            maskImage: "linear-gradient(to right, transparent 0%, black 14%, black 100%)",
            WebkitMaskImage: "linear-gradient(to right, transparent 0%, black 14%, black 100%)",
          }}
        />

        {/* Layer 3: Clouds Parting & Dense Initial Mist Covering (Che kín ở scroll = 0) */}
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

        {/* Layer 4: Trần hang động Cave.png (Ban đầu ẩn opacity 0, xuất hiện mượt mà khi cuộn tới Phase 2) */}
        <img
          ref={caveRef}
          src="/assets/bxcmuse/Cave.png"
          alt="Cave Frame"
          className="pointer-events-none absolute -top-8 sm:-top-14 left-1/2 -translate-x-1/2 w-[115vw] sm:w-[112vw] max-w-none h-[112vh] object-fill select-none will-change-transform drop-shadow-[0_25px_50px_rgba(0,0,0,0.85)] opacity-0"
          style={{ zIndex: 10, opacity: 0 }}
        />

        {/* Layer 5: Explorer.png (Ban đầu ẩn opacity 0, xuất hiện mượt mà khi cuộn tới Phase 3) */}
        <img
          ref={explorerRef}
          src="/assets/bxcmuse/Explorer_cropped.png"
          alt="Explorer"
          className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 w-[125vw] sm:w-[110vw] max-w-none h-auto object-contain object-bottom select-none will-change-transform drop-shadow-[0_20px_40px_rgba(0,0,0,0.95)] opacity-0"
          style={{ zIndex: 12, opacity: 0 }}
        />

        {/* Layer 6: Monumental Title Drop (Bừng sáng sau cùng - Tên dự án chủ đề hoành tráng) */}
        <div
          ref={headlineRef}
          className="pointer-events-none absolute top-[9%] sm:top-[11%] left-0 right-0 flex flex-col items-center justify-center text-center select-none px-4 will-change-transform max-w-6xl mx-auto opacity-0"
          style={{ zIndex: 14, opacity: 0 }}
        >
          {/* Monumental Headline */}
          <h1 className="text-6xl sm:text-8xl md:text-9xl lg:text-[8.5rem] font-black tracking-tighter text-white drop-shadow-[0_20px_50px_rgba(0,0,0,0.9)] leading-[0.88] select-none">
            AVAXAGENT
          </h1>
          <div className="text-2xl sm:text-4xl md:text-5xl font-black tracking-[0.38em] uppercase text-[#E84142] drop-shadow-[0_0_30px_rgba(232,65,66,0.55)] mt-2 sm:mt-3 select-none">
            STUDIO
          </div>
        </div>

        {/* Discreet Top-Right Language Pill on Hero Stage */}
        <button
          type="button"
          onClick={onToggleLang}
          className="absolute top-5 right-5 z-30 inline-flex items-center gap-1.5 rounded-full border border-slate-300/70 bg-white/80 px-3 py-1 text-[11px] font-bold text-slate-700 backdrop-blur-md shadow-sm transition-all hover:bg-white hover:text-[#E84142]"
        >
          <Languages className="size-3.5" />
          <span>{lang === "vi" ? "VI · Tiếng Việt" : "EN · English"}</span>
        </button>

        {/* Pure Typographic Scroll Cue with Downward Chevron */}
        <div
          ref={scrollCueRef}
          className="pointer-events-none absolute bottom-8 sm:bottom-10 left-0 right-0 z-30 flex flex-col items-center justify-center gap-1 text-center select-none"
        >
          <span className="font-mono text-xs font-semibold tracking-[0.25em] uppercase text-slate-700 drop-shadow-sm">
            {LANDING_COPY[lang].scrollCue}
          </span>
          <ChevronDown className="h-4 w-4 text-[#E84142] animate-bounce" strokeWidth={2.5} />
        </div>

        {/* Soft Bottom Feather Fade into #F8FAFC Snow White content sections */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0 h-36 bg-gradient-to-t from-[#F8FAFC] via-[#F8FAFC]/60 to-transparent"
          style={{ zIndex: 18 }}
        />
      </div>
    </section>
  );
}
