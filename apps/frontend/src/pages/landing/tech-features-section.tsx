import { ArrowRight, CheckCircle2, Globe, KeyRound, Shield, Zap } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

const PILLARS = [
  {
    icon: Zap,
    title: "Giao thức x402 Micropayment",
    subtitle: "Thanh toán siêu nhỏ không tốn gas",
    desc: "Tích hợp chuẩn HTTP 402 Payment Required kết hợp EIP-3009 TransferWithAuthorization. Người dùng ký uỷ quyền USDC trực tiếp từ ví, Gateway đóng vai trò Relayer bảo lãnh giao dịch on-chain.",
    bulletPoints: ["Không cần nạp AVAX gas", "Quyết toán trong 2 giây", "Chống replay attack bằng nonce"],
  },
  {
    icon: Shield,
    title: "Bảo mật Ví Turnkey Enclave",
    subtitle: "Ví phần cứng MPC tự quản cho từng Agent",
    desc: "Mỗi Agent sở hữu một Sub-Organization riêng biệt trên hạ tầng Turnkey Enclave. Toàn bộ Private Key được lưu trong phần cứng an toàn, gắn kèm Spending Guardrail giới hạn chi tiêu chặt chẽ.",
    bulletPoints: ["Khởi tạo tự động trong 2s", "Chính sách chi tiêu giới hạn", "Không lưu trữ private key thô"],
  },
  {
    icon: Globe,
    title: "ERC-8004 & ERC-8183 On-Chain",
    subtitle: "Định danh và Bảo chứng hợp đồng",
    desc: "Danh tính của Agent được mint trực tiếp lên Avalanche C-Chain qua chuẩn ERC-8004 IdentityRegistry. Hỗ trợ cơ chế Ký quỹ bảo chứng ERC-8183 giúp giải quyết tranh chấp kết quả tự động.",
    bulletPoints: ["Minh bạch tra cứu trên Snowtrace", "Cơ chế bảo chứng Escrow 95/5", "Đồng bộ realtime qua Indexer"],
  },
];

export function TechFeaturesSection() {
  return (
    <section id="architecture" className="relative z-30 px-4 py-20 sm:px-8 max-w-7xl mx-auto border-t border-white/10">
      {/* Section Header */}
      <div className="text-center max-w-2xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 text-xs font-mono font-bold text-[#FFA4A6] tracking-wider uppercase mb-2">
          <KeyRound className="w-3.5 h-3.5 text-[#E84142]" />
          Kiến trúc công nghệ UniHack
        </div>
        <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white">
          VÌ SAO CHỌN AVAXAGENT STUDIO?
        </h2>
        <p className="text-sm sm:text-base text-slate-400 mt-2 font-light">
          Kết hợp hoàn hảo giữa Trí tuệ Nhân tạo (LLM), Hạ tầng Mật mã học (MPC Enclave) và Tốc độ giao dịch của Avalanche C-Chain.
        </p>
      </div>

      {/* 3 Pillars Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {PILLARS.map((p, idx) => {
          const Icon = p.icon;
          return (
            <div
              key={idx}
              className="relative rounded-2xl border border-white/10 bg-[#0A0C14]/90 p-8 backdrop-blur-xl transition-all duration-300 hover:border-[#E84142]/40 hover:-translate-y-1 shadow-2xl flex flex-col justify-between"
            >
              <div>
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#E84142]/10 border border-[#E84142]/30 text-[#FFA4A6] mb-6">
                  <Icon className="h-6 w-6" />
                </div>

                <h3 className="text-xl font-bold text-white">{p.title}</h3>
                <div className="text-xs font-medium text-[#E84142] mt-0.5 mb-3 font-mono">
                  {p.subtitle}
                </div>
                <p className="text-xs sm:text-sm text-slate-400 leading-relaxed font-light mb-6">
                  {p.desc}
                </p>
              </div>

              <div className="space-y-2 border-t border-white/10 pt-4">
                {p.bulletPoints.map((item, bIdx) => (
                  <div key={bIdx} className="flex items-center gap-2 text-xs text-slate-300">
                    <CheckCircle2 className="h-3.5 w-3.5 text-[#E84142] shrink-0" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom CTA Banner */}
      <div className="mt-20 rounded-3xl border border-[#E84142]/30 bg-gradient-to-r from-[#170B0E] via-[#0D0E18] to-[#0A0C14] p-8 sm:p-12 flex flex-col md:flex-row items-center justify-between gap-6 shadow-[0_0_50px_rgba(232,65,66,0.15)]">
        <div className="max-w-xl text-center md:text-left">
          <h3 className="text-2xl sm:text-3xl font-black text-white">
            Sẵn sàng trải nghiệm hoặc triển khai Agent của bạn?
          </h3>
          <p className="text-sm text-slate-300 mt-2 font-light">
            Chạy trực tiếp trên Avalanche Fuji Testnet (Chain ID 43113). Đã vượt qua 805/805 unit và E2E tests.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Link to="/agents/new">
            <Button size="lg" className="bg-[#E84142] hover:bg-[#D03031] text-xs sm:text-sm font-bold text-white shadow-[0_0_25px_rgba(232,65,66,0.5)]">
              <span>Khởi tạo Agent mới</span>
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          </Link>
          <Link to="/dashboard">
            <Button variant="outline" size="lg" className="border-white/20 bg-white/5 text-xs sm:text-sm text-slate-200 hover:bg-white/10">
              Vào Dashboard
            </Button>
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-24 pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
        <div>
          © 2026 <b>Avaxagent Studio</b> · Xây dựng cho cuộc thi <b>UniHack 2026</b> trên Avalanche.
        </div>
        <div className="flex items-center gap-6">
          <a href="https://testnet.snowtrace.io" target="_blank" rel="noreferrer" className="hover:text-slate-300 transition-colors">
            Snowtrace Fuji
          </a>
          <a href="https://github.com/CocDap/avax-agent" target="_blank" rel="noreferrer" className="hover:text-slate-300 transition-colors">
            GitHub Repo
          </a>
        </div>
      </footer>
    </section>
  );
}
