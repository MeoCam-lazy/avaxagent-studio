import { useEffect, useRef } from "react";
import { ArrowDown } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

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
  const scrollCueRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      // 60 FPS GSAP ScrollTrigger Timeline with 1.0s scrubbed inertia across 300vh
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "bottom bottom",
          scrub: 1.0,
        },
      });

      // ---------------------------------------------------------------------
      // PHASE 1 (0.0 -> 0.30): MÂY CHE KÍN -> RẼ MÂY ĐỂ LỘ ĐỈNH NÚI TUYẾT & BẦU TRỜI
      // ---------------------------------------------------------------------
      // Bầu trời zoom chiều sâu nhẹ nhàng
      if (skyRef.current) {
        tl.to(skyRef.current, { scale: 1.1, ease: "none", duration: 100 }, 0);
      }

      // Lớp sương mây dày đặc che phủ 100% màn hình ban đầu tan biến dần
      if (mistRef.current) {
        tl.to(mistRef.current, { opacity: 0, ease: "power1.inOut", duration: 22 }, 0);
      }

      // Hướng dẫn cuộn ban đầu mờ dần ngay khi bắt đầu cuộn chuột
      if (scrollCueRef.current) {
        tl.to(scrollCueRef.current, { opacity: 0, y: -25, ease: "power1.out", duration: 12 }, 0);
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

      // Mây dưới và mây trên tản dần
      if (cloud01Ref.current) {
        tl.to(cloud01Ref.current, { y: 150, opacity: 0.1, ease: "power1.out", duration: 28 }, 0);
      }
      if (cloud02Ref.current) {
        tl.to(cloud02Ref.current, { y: -100, opacity: 0.1, ease: "power1.out", duration: 28 }, 0);
      }

      // Đỉnh núi tuyết Mountains.png lộ diện: hiển thị trọn vẹn đỉnh núi nhọn và sườn núi đón nắng
      if (mountRef.current) {
        tl.fromTo(
          mountRef.current,
          { opacity: 0.2, y: 50 },
          { opacity: 1, y: 0, ease: "power1.out", duration: 34 },
          0
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 2 (0.24 -> 0.50): HIỆN RA CHỮ AVAXAGENT STUDIO TRÊN NỀN TRỜI & ĐỈNH NÚI
      // ---------------------------------------------------------------------
      if (headlineRef.current) {
        tl.fromTo(
          headlineRef.current,
          { opacity: 0, y: 40, scale: 0.92 },
          { opacity: 1, y: 0, scale: 1.0, ease: "power2.out", duration: 26 },
          24
        );
        // Sau đó giữ ổn định làm tâm điểm sang trọng
        tl.to(headlineRef.current, { scale: 1.04, ease: "none", duration: 50 }, 50);
      }

      // ---------------------------------------------------------------------
      // PHASE 3 (0.45 -> 0.74): TRẦN HANG ĐỘNG CAVE.PNG BUÔNG / UỐN XUỐNG
      // ---------------------------------------------------------------------
      if (caveRef.current) {
        tl.fromTo(
          caveRef.current,
          { opacity: 0, yPercent: -45, scale: 1.08 },
          { opacity: 1, yPercent: 0, scale: 1.0, ease: "power2.out", duration: 28 },
          45
        );
      }

      // ---------------------------------------------------------------------
      // PHASE 4 (0.68 -> 0.94): EXPLORER.PNG TO RÕ SỪNG SỮNG TRÊN MỎM TUYẾT
      // ---------------------------------------------------------------------
      if (explorerRef.current) {
        tl.fromTo(
          explorerRef.current,
          { opacity: 0, y: 130, scale: 0.95 },
          { opacity: 1, y: 0, scale: 1.0, ease: "power2.out", duration: 25 },
          68
        );
      }
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <section ref={containerRef} className="relative h-[300vh] w-full bg-[#08090E]">
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

        {/* Layer 2: Mountains (Đỉnh núi tuyết nhọn và sườn núi hiện trọn vẹn, không bị phóng to cắt mất) */}
        <img
          ref={mountRef}
          src="/assets/bxcmuse/Mountains.png"
          alt="Mountains"
          className="pointer-events-none absolute top-[15%] sm:top-[18%] left-1/2 -translate-x-1/2 w-[110vw] sm:w-[104vw] max-w-none h-auto select-none will-change-transform drop-shadow-[0_15px_30px_rgba(0,0,0,0.7)]"
          style={{ zIndex: 2 }}
        />

        {/* Layer 3: Cinematic Headline (Nằm trên khoảng trời quang đãng ngay trên đỉnh núi) */}
        <div
          ref={headlineRef}
          className="pointer-events-none absolute top-[9%] sm:top-[11%] left-0 right-0 flex flex-col items-center justify-center text-center select-none px-6 will-change-transform max-w-4xl mx-auto"
          style={{ zIndex: 3 }}
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-black/60 px-3.5 py-1 backdrop-blur-md shadow-xl mb-2.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[#E84142] animate-pulse" />
            <span className="text-[11px] font-semibold tracking-wider text-slate-200 uppercase font-mono">
              The Autonomous AI Agent Studio · Avalanche C-Chain
            </span>
          </div>

          {/* Elegant Scaled Headline */}
          <h1 className="text-4xl sm:text-6xl md:text-7xl font-black tracking-tight text-white drop-shadow-[0_12px_35px_rgba(0,0,0,0.95)] leading-tight">
            AVAXAGENT
          </h1>
          <div className="text-xl sm:text-2xl md:text-3xl font-extrabold tracking-[0.3em] uppercase bg-gradient-to-r from-white via-slate-100 to-[#FFA4A6] bg-clip-text text-transparent drop-shadow-[0_8px_25px_rgba(0,0,0,0.95)] mt-0.5">
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

        {/* Layer 5: Trần hang động Cave.png (Vòm thạch nhũ rủ trên đỉnh khung hình) */}
        <img
          ref={caveRef}
          src="/assets/bxcmuse/Cave.png"
          alt="Cave Frame"
          className="pointer-events-none absolute -top-8 sm:-top-14 left-1/2 -translate-x-1/2 w-[115vw] sm:w-[112vw] max-w-none h-[112vh] object-fill select-none will-change-transform drop-shadow-[0_25px_50px_rgba(0,0,0,0.85)]"
          style={{ zIndex: 10 }}
        />

        {/* Layer 6: Explorer.png (Nhà thám hiểm nổi lên to rõ, uy nghi trên mỏm tuyết trung tâm) */}
        <img
          ref={explorerRef}
          src="/assets/bxcmuse/Explorer_cropped.png"
          alt="Explorer"
          className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 w-[125vw] sm:w-[110vw] max-w-none h-auto object-contain object-bottom select-none will-change-transform drop-shadow-[0_20px_40px_rgba(0,0,0,0.95)]"
          style={{ zIndex: 12 }}
        />

        {/* Initial Scroll Cue (Chỉ hiện ngay tại scroll = 0, mờ biến mất ngay khi cuộn) */}
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

        {/* Soft Bottom Feather Fade into #08090E content sections */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#08090E] via-[#08090E]/60 to-transparent"
          style={{ zIndex: 18 }}
        />
      </div>
    </section>
  );
}
