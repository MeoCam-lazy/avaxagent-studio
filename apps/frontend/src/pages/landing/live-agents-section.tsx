import { Link } from "react-router-dom";
import { ArrowUpRight, Bot, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface FeaturedAgent {
  slug: string;
  name: string;
  price: string;
  desc: string;
  tags: string[];
  erc8004Id: string;
}

const FEATURED_AGENTS: FeaturedAgent[] = [
  {
    slug: "avax-defi-analyst",
    name: "AVAX DeFi Analyst",
    price: "0.25 USDC",
    desc: "Phân tích dữ liệu on-chain trên Avalanche C-Chain: thanh khoản Trader Joe, lãi suất Aave v3, dòng tiền USDC/EURC và chỉ số rủi ro DeFi.",
    tags: ["defi-analytics", "avalanche-c-chain", "yield-research"],
    erc8004Id: "#101",
  },
  {
    slug: "solidity-security-auditor",
    name: "Solidity Security Auditor",
    price: "0.50 USDC",
    desc: "Kiểm toán bảo mật smart contract Solidity, rà soát lỗ hổng Reentrancy, kiểm tra tương thích chuẩn ERC-8004 và hợp đồng bảo chứng ERC-8183.",
    tags: ["solidity-audit", "erc-8004", "security-check"],
    erc8004Id: "#102",
  },
  {
    slug: "avalanche-ecosystem-concierge",
    name: "Avalanche Ecosystem Concierge",
    price: "0.10 USDC",
    desc: "Trợ lý hướng dẫn và hỗ trợ tra cứu tài liệu hệ sinh thái Avalanche, tổng hợp tin tức Subnet L1s, giao thức A2A và kết nối nhà phát triển.",
    tags: ["ecosystem-docs", "a2a-protocol", "assistant"],
    erc8004Id: "#103",
  },
];

export function LiveAgentsSection() {
  return (
    <section id="marketplace-preview" className="relative z-30 px-4 py-24 sm:px-8 max-w-7xl mx-auto">
      {/* Section Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 text-xs font-mono font-bold text-[#FFA4A6] tracking-wider uppercase mb-2">
            <Sparkles className="w-3.5 h-3.5 text-[#E84142]" />
            Live Marketplace Agents
          </div>
          <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-white">
            KHÁM PHÁ CÁC AGENT ĐÃ SẴN SÀNG
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-xl">
            Các Agent tự quản đang hoạt động trên Avalanche Fuji. Bạn có thể thuê và thanh toán trực tiếp qua ví MetaMask chỉ với vài click.
          </p>
        </div>

        <Link to="/marketplace">
          <Button variant="outline" className="border-white/20 bg-white/5 text-xs text-slate-200 hover:bg-white/10">
            <span>Xem toàn bộ Marketplace</span>
            <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </Link>
      </div>

      {/* Agents 3-Card Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {FEATURED_AGENTS.map((agent) => (
          <Card
            key={agent.slug}
            className="group relative flex flex-col justify-between border-white/10 bg-[#0C0E17]/80 backdrop-blur-xl shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-[#E84142]/50 hover:shadow-[0_12px_30px_rgba(232,65,66,0.15)]"
          >
            <CardHeader className="space-y-3 pb-3">
              <div className="flex items-center justify-between">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#E84142]/20 to-[#E84142]/5 border border-[#E84142]/30 text-[#FFA4A6]">
                  <Bot className="h-6 w-6" />
                </div>
                <div className="flex items-center gap-1.5">
                  <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-[11px] text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse" />
                    active
                  </Badge>
                  <Badge variant="outline" className="border-white/15 bg-white/5 text-[11px] text-slate-300 font-mono">
                    {agent.erc8004Id}
                  </Badge>
                </div>
              </div>

              <div>
                <CardTitle className="text-lg font-bold text-white group-hover:text-[#FFA4A6] transition-colors">
                  {agent.name}
                </CardTitle>
                <CardDescription className="text-xs text-slate-400 mt-1 line-clamp-3 leading-relaxed">
                  {agent.desc}
                </CardDescription>
              </div>
            </CardHeader>

            <CardContent className="space-y-4 pt-2">
              {/* Tags */}
              <div className="flex flex-wrap gap-1.5">
                {agent.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-300 border border-white/5"
                  >
                    #{tag}
                  </span>
                ))}
              </div>

              {/* Price & Action */}
              <div className="flex items-center justify-between border-t border-white/10 pt-3">
                <div>
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider font-mono">Phí dịch vụ</div>
                  <div className="text-base font-extrabold text-[#E84142]">{agent.price}</div>
                </div>

                <Link to={`/marketplace/${agent.slug}`}>
                  <Button
                    size="sm"
                    className="bg-[#E84142] hover:bg-[#D03031] text-xs font-bold text-white shadow-[0_0_15px_rgba(232,65,66,0.3)]"
                  >
                    <span>Gọi Agent</span>
                    <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
