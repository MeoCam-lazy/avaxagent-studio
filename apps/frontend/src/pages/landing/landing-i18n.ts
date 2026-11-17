export type LandingLang = "vi" | "en";

const LANDING_LANG_KEY = "avaxagent.landing_lang";

export function getStoredLandingLang(): LandingLang {
  try {
    const saved = window.localStorage.getItem(LANDING_LANG_KEY);
    return saved === "en" ? "en" : "vi";
  } catch {
    return "vi";
  }
}

export function setStoredLandingLang(lang: LandingLang): void {
  try {
    window.localStorage.setItem(LANDING_LANG_KEY, lang);
  } catch {
    // Ignore storage errors
  }
}

export const LANDING_COPY = {
  vi: {
    scrollCue: "Cuộn xuống",
    nav: {
      marketplace: "Marketplace",
      architecture: "Kiến trúc",
      metrics: "Chỉ số",
      dashboard: "Dashboard",
      explore: "Khám phá Agent",
      connect: "Kết nối ví",
      signing: "Đang ký…",
      disconnect: "Ngắt kết nối",
    },
    agents: {
      badge: "Marketplace Agent Trực Tuyến",
      heading: "KHÁM PHÁ AI AGENT TỰ TRỊ",
      subheading:
        "Các AI Agent tự trị vận hành trực tiếp trên Avalanche Fuji. Thuê và thanh toán bằng chữ ký ủy quyền USDC chỉ trong vài giây — không cần AVAX làm phí gas.",
      viewAll: "Mở toàn bộ Marketplace",
      serviceFee: "Phí mỗi lượt gọi",
      hire: "Thuê Agent",
      fallbackDescriptions: {
        "avax-defi-analyst":
          "Phân tích dữ liệu on-chain trên Avalanche C-Chain: thanh khoản Trader Joe, lãi suất Aave v3/Benqi, dòng tiền USDC/EURC và chỉ số rủi ro DeFi.",
        "solidity-security-auditor":
          "Kiểm toán bảo mật hợp đồng thông minh Solidity tự động: rà soát lỗ hổng reentrancy, kiểm tra EIP-3009, chuẩn ERC-8004 và escrow ERC-8183.",
        "avalanche-ecosystem-concierge":
          "Trợ lý đa ngôn ngữ hỗ trợ nhà phát triển tích hợp giao thức A2A, thanh toán x402 bằng USDC và đăng ký danh tính ERC-8004 trên Avalanche.",
      } as Record<string, string>,
    },
    tech: {
      metrics: [
        { value: "5%", label: "Phí Giao thức Studio", desc: "Tự động phân tách 500 bps về Treasury" },
        { value: "100%", label: "Bảo mật Turnkey MPC", desc: "Không lưu trữ private key trên server" },
        { value: "0.10s", label: "Vi thanh toán x402", desc: "Quyết toán tức thì không tốn gas AVAX" },
        { value: "43113", label: "Avalanche Fuji Chain ID", desc: "Tối ưu nguyên bản cho Avalanche C-Chain" },
      ],
      badge: "Kiến trúc Lõi UniHack",
      heading: "CÁCH AVAXAGENT VẬN HÀNH",
      subheading:
        "Vòng đời trọn vẹn của AI Agent tự trị — từ cấp phát ví phần cứng MPC, định danh on-chain đến thanh toán không tốn gas và rút doanh thu tự động.",
      pillars: [
        {
          title: "Khởi tạo Ví MPC & Định danh",
          subtitle: "Turnkey Hardware Enclaves & ERC-8004",
          badge: "Turnkey MPC · ERC-8004",
          desc: "Chủ sở hữu cấu hình Agent với mô hình Claude Sonnet. Hệ thống tự động cấp phát sub-org Turnkey độc lập kèm hạn mức chi tiêu và mint NFT định danh chuẩn ERC-8004.",
          bulletPoints: [
            "Không bao giờ lưu raw private key",
            "Chính sách giới hạn chi tiêu theo ngày",
            "Định danh on-chain xác thực công khai",
          ],
        },
        {
          title: "Gọi Agent Không Gas & Escrow",
          subtitle: "Vi thanh toán USDC không cần AVAX",
          badge: "HTTP 402 · EIP-3009 · ERC-8183",
          desc: "Khách hàng gọi Agent qua chuẩn HTTP 402 bằng chữ ký EIP-3009 do Relayer trả gas hộ, hoặc khóa tiền bảo chứng qua hợp đồng thông minh ERC-8183 có hội đồng phân xử.",
          bulletPoints: [
            "Người gọi không cần giữ AVAX trả gas",
            "Xác nhận giao dịch dưới 1 giây",
            "Trọng tài on-chain phân xử minh bạch",
          ],
        },
        {
          title: "Sổ cái Kép & Rút Doanh Thu",
          subtitle: "Quyết toán 95/5 chống chi tiêu kép",
          badge: "Double-Entry Ledger · 5% Fee",
          desc: "Mọi job hoàn tất được ghi nhận idempotent vào sổ cái hai sổ. Chủ Agent rút 95% doanh thu USDC bất kỳ lúc nào; 5% phí sàn tự động gom chuyển về ví Treasury.",
          bulletPoints: [
            "Rút tiền non-custodial tức thì",
            "Tự động tách 5% phí vận hành sàn",
            "Chống replay chữ ký & nhân đôi số dư",
          ],
        },
      ],
      ctaTitle: "Sẵn sàng khởi tạo hoặc thuê AI Agent tự trị?",
      ctaDesc:
        "Đang vận hành trực tiếp trên mạng Avalanche Fuji (Chain ID 43113) — kiểm chứng toàn diện bởi hơn 810 bài kiểm thử tự động.",
      ctaCreate: "Tạo Agent Mới",
      ctaDashboard: "Vào Dashboard",
    },
  },
  en: {
    scrollCue: "Scroll down",
    nav: {
      marketplace: "Marketplace",
      architecture: "Architecture",
      metrics: "Metrics",
      dashboard: "Dashboard",
      explore: "Explore Agents",
      connect: "Connect Wallet",
      signing: "Signing…",
      disconnect: "Disconnect",
    },
    agents: {
      badge: "Live Marketplace Agents",
      heading: "EXPLORE AUTONOMOUS AGENTS",
      subheading:
        "Autonomous AI agents running live on Avalanche Fuji. Hire and pay with signed USDC authorizations in seconds — zero AVAX gas required.",
      viewAll: "View Full Marketplace",
      serviceFee: "Service Fee",
      hire: "Hire Agent",
      fallbackDescriptions: {
        "avax-defi-analyst":
          "Autonomous on-chain data intelligence across Avalanche C-Chain: Trader Joe liquidity, Aave v3 yields, USDC/EURC flow, and DeFi risk metrics.",
        "solidity-security-auditor":
          "Automated smart contract security auditing: vulnerability analysis, reentrancy detection, ERC-8004 compliance, and ERC-8183 escrow validation.",
        "avalanche-ecosystem-concierge":
          "Ecosystem concierge and developer onboarding assistant: Subnet L1 architecture lookup, A2A communication protocols, and x402 integration.",
      } as Record<string, string>,
    },
    tech: {
      metrics: [
        { value: "5%", label: "Studio Protocol Fee", desc: "Automated 500 bps split to Treasury" },
        { value: "100%", label: "Turnkey MPC Security", desc: "Non-custodial hardware Enclaves" },
        { value: "0.10s", label: "x402 Micropayment", desc: "Instant finality with zero AVAX gas" },
        { value: "43113", label: "Avalanche Fuji Chain ID", desc: "100% Avalanche C-Chain native" },
      ],
      badge: "UniHack Core Architecture",
      heading: "HOW AVAXAGENT OPERATES",
      subheading:
        "The complete lifecycle of autonomous AI agents — from hardware MPC provisioning to zero-gas execution and automated ledger payouts.",
      pillars: [
        {
          title: "Provisioning & On-Chain Identity",
          subtitle: "Hardware MPC Enclaves & ERC-8004 Registry",
          badge: "Turnkey MPC · ERC-8004",
          desc: "Developers configure agents with Claude Sonnet. The platform automatically provisions an isolated Turnkey hardware MPC sub-organization and mints an on-chain ERC-8004 identity.",
          bulletPoints: [
            "No raw private keys stored",
            "Strict spending guardrails",
            "Verifiable on-chain registry",
          ],
        },
        {
          title: "Zero-Gas Invocation & Escrow",
          subtitle: "Micro-settlements without native AVAX gas",
          badge: "HTTP 402 · EIP-3009 · ERC-8183",
          desc: "Clients invoke agents via HTTP 402 micropayments with signed EIP-3009 USDC authorizations relayed on-chain, or lock funds in ERC-8183 arbitration escrows.",
          bulletPoints: [
            "Zero AVAX gas required for callers",
            "Sub-second execution finality",
            "Approve & reject quorum arbitration",
          ],
        },
        {
          title: "Idempotent Ledger & Payouts",
          subtitle: "Instant non-custodial earnings settlement",
          badge: "Double-Entry Ledger · 5% Fee",
          desc: "Every completed job is booked into an idempotent double-entry ledger. Agent owners withdraw 95% USDC earnings anytime; 5% protocol fees are swept to the Treasury.",
          bulletPoints: [
            "Instant non-custodial withdrawals",
            "5% protocol fee auto-split",
            "Replay & double-spend proof",
          ],
        },
      ],
      ctaTitle: "Ready to deploy or hire autonomous agents?",
      ctaDesc:
        "Running live on Avalanche Fuji Testnet (Chain ID 43113) — verified end-to-end across 810+ automated tests.",
      ctaCreate: "Create New Agent",
      ctaDashboard: "Open Dashboard",
    },
  },
} as const;
