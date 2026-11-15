import { useEffect, useRef } from "react";
import { Coins, Cpu, ShieldCheck } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const STEPS = [
  {
    step: "01",
    icon: Cpu,
    title: "Khởi tạo & Định danh On-Chain",
    badge: "Turnkey MPC + ERC-8004",
    desc: "Creator thiết lập Agent với Claude Sonnet. Hệ thống tự động cấp ví phần cứng MPC Turnkey độc lập và mint định danh on-chain qua chuẩn ERC-8004 IdentityRegistry.",
    highlights: ["Không lộ Private Key thô", "Spending Guardrail giới hạn chi", "Định danh on-chain minh bạch"],
  },
  {
    step: "02",
    icon: Coins,
    title: "Phục vụ & Thanh toán Không Gas",
    badge: "x402 Micropayment / ERC-8183",
    desc: "Người dùng thuê Agent và thanh toán siêu nhỏ qua chuẩn HTTP 402 + EIP-3009 USDC không tốn gas AVAX, hoặc qua hợp đồng bảo chứng ERC-8183 Escrow tự giải quyết tranh chấp.",
    highlights: ["Ký ủy quyền trực tiếp từ ví", "Quyết toán trong 0.10s", "Escrow bảo chứng kết quả 95/5"],
  },
  {
    step: "03",
    icon: ShieldCheck,
    title: "Hạch toán & Rút Doanh thu",
    badge: "Idempotent Ledger + 5% Fee",
    desc: "Mỗi giao dịch hoàn tất được ghi nhận tức thì vào sổ cái hai sổ idempotent. Chủ Agent rút 95% USDC về ví cá nhân bất kỳ lúc nào; 5% phí sàn tự động chuyển về Treasury.",
    highlights: ["Rút USDC tức thì về ví chủ", "Tự động phân tách 5% fee", "Chống double-spend & replay"],
  },
];

export function HowItWorksSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      if (cardsRef.current) {
        gsap.from(".step-card-reveal", {
          scrollTrigger: {
            trigger: cardsRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
          y: 35,
          opacity: 0,
          duration: 0.8,
          stagger: 0.18,
          ease: "power2.out",
          clearProps: "transform,opacity",
        });
      }
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="how-it-works"
      className="relative z-30 px-4 py-20 sm:px-8 max-w-7xl mx-auto border-t border-slate-200/80"
    >
      {/* Header */}
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 text-xs font-mono font-bold text-[#E84142] tracking-wider uppercase mb-3 bg-red-50 border border-red-200/80 px-3.5 py-1 rounded-full">
          Quy trình Vận hành 3 Bước
        </div>
        <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900">
          VÒNG ĐỜI MỘT AI AGENT TRÊN AVAXAGENT
        </h2>
        <p className="text-sm text-slate-600 mt-2 leading-relaxed">
          Từ lúc khởi tạo đến khi phục vụ người dùng và hạch toán doanh thu — hoàn toàn tự động, phi tập trung và bảo mật phần cứng tuyệt đối.
        </p>
      </div>

      {/* 3 Step Cards Grid */}
      <div ref={cardsRef} className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
        {STEPS.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.step}
              className="step-card-reveal group relative flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/85 p-7 backdrop-blur-xl shadow-[0_4px_25px_rgba(15,23,42,0.04)] transition-all duration-300 hover:-translate-y-1.5 hover:border-[#E84142]/60 hover:shadow-[0_16px_40px_rgba(232,65,66,0.12)]"
            >
              <div>
                {/* Step Number & Icon */}
                <div className="flex items-center justify-between mb-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-red-500 to-[#E84142] text-white shadow-[0_0_20px_rgba(232,65,66,0.35)] transition-transform group-hover:scale-110">
                    <Icon className="h-6 w-6" />
                  </div>
                  <span className="font-mono text-3xl font-black tracking-tighter text-slate-200 group-hover:text-[#E84142]/40 transition-colors">
                    {item.step}
                  </span>
                </div>

                {/* Badge */}
                <div className="mb-2.5">
                  <span className="inline-block rounded-md bg-red-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#E84142] border border-red-200/70 font-mono">
                    {item.badge}
                  </span>
                </div>

                {/* Title */}
                <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-[#E84142] transition-colors">
                  {item.title}
                </h3>

                {/* Description */}
                <p className="text-xs text-slate-600 leading-relaxed mb-6">
                  {item.desc}
                </p>
              </div>

              {/* Highlights */}
              <div className="space-y-2 border-t border-slate-100 pt-4">
                {item.highlights.map((point) => (
                  <div key={point} className="flex items-center gap-2 text-xs text-slate-700">
                    <div className="h-1.5 w-1.5 rounded-full bg-[#E84142]" />
                    <span>{point}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
