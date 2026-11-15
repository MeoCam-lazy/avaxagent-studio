import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Compass, ShieldCheck, Sparkles, TrendingUp, type LucideIcon } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

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
  icon: LucideIcon;
}

const FEATURED_AGENTS: FeaturedAgent[] = [
  {
    slug: "avax-defi-analyst",
    name: "AVAX DeFi Analyst",
    price: "0.25 USDC",
    desc: "Autonomous on-chain data intelligence across Avalanche C-Chain: Trader Joe liquidity, Aave v3 yields, USDC/EURC flow, and DeFi risk metrics.",
    tags: ["defi-analytics", "avalanche-c-chain", "yield-research"],
    erc8004Id: "#101",
    icon: TrendingUp,
  },
  {
    slug: "solidity-security-auditor",
    name: "Solidity Security Auditor",
    price: "0.50 USDC",
    desc: "Automated smart contract security auditing: AST vulnerability analysis, reentrancy detection, ERC-8004 compliance, and ERC-8183 escrow validation.",
    tags: ["solidity-audit", "erc-8004", "security-check"],
    erc8004Id: "#102",
    icon: ShieldCheck,
  },
  {
    slug: "avalanche-ecosystem-concierge",
    name: "Avalanche Ecosystem Concierge",
    price: "0.10 USDC",
    desc: "Ecosystem concierge and developer onboarding assistant: Subnet L1 architecture lookup, A2A communication protocols, and dev tools.",
    tags: ["ecosystem-docs", "a2a-protocol", "assistant"],
    erc8004Id: "#103",
    icon: Compass,
  },
];

export function LiveAgentsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      // Staggered reveal for agent cards when scrolling into viewport
      gsap.from(".agent-card-reveal", {
        scrollTrigger: {
          trigger: gridRef.current,
          start: "top 85%",
          toggleActions: "play none none reverse",
        },
        y: 45,
        opacity: 0,
        duration: 0.85,
        stagger: 0.16,
        ease: "power2.out",
        clearProps: "transform,opacity",
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="marketplace-preview"
      className="relative z-30 px-4 py-24 sm:px-8 max-w-7xl mx-auto"
    >
      {/* Section Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 text-xs font-mono font-bold text-[#E84142] tracking-wider uppercase mb-2 bg-red-50 border border-red-200/80 px-3 py-1 rounded-full">
            <Sparkles className="w-3.5 h-3.5 text-[#E84142]" />
            Live Marketplace Agents
          </div>
          <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900">
            EXPLORE AUTONOMOUS AGENTS
          </h2>
          <p className="text-sm text-slate-600 mt-1 max-w-xl">
            Autonomous AI agents running live on Avalanche Fuji. Hire and pay with signed USDC authorizations in seconds.
          </p>
        </div>

        <Link to="/marketplace">
          <Button variant="outline" className="border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-100 shadow-sm">
            <span>View Full Marketplace</span>
            <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </Link>
      </div>

      {/* Agents 3-Card Grid with GSAP Staggered Reveal */}
      <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {FEATURED_AGENTS.map((agent) => {
          const Icon = agent.icon;
          return (
            <Card
              key={agent.slug}
              className="agent-card-reveal group relative flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white/90 backdrop-blur-xl shadow-[0_4px_25px_rgba(15,23,42,0.04)] transition-all duration-300 hover:-translate-y-1.5 hover:border-[#E84142]/60 hover:shadow-[0_16px_40px_rgba(232,65,66,0.12)] will-change-transform"
            >
              <CardHeader className="space-y-3 pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-red-50 to-slate-100 border border-red-200/80 text-[#E84142] shadow-sm group-hover:scale-105 transition-transform">
                    <Icon className="h-6 w-6" />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-[11px] font-semibold text-emerald-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse" />
                      active
                    </Badge>
                    <Badge variant="outline" className="border-slate-200 bg-slate-100 text-[11px] text-slate-600 font-mono">
                      {agent.erc8004Id}
                    </Badge>
                  </div>
                </div>

              <div>
                <CardTitle className="text-lg font-bold text-slate-900 group-hover:text-[#E84142] transition-colors">
                  {agent.name}
                </CardTitle>
                <CardDescription className="text-xs text-slate-600 mt-1 line-clamp-3 leading-relaxed">
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
                    className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 border border-slate-200/70"
                  >
                    #{tag}
                  </span>
                ))}
              </div>

              {/* Price & Action */}
              <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">Service Fee</div>
                  <div className="text-base font-black text-[#E84142]">{agent.price}</div>
                </div>

                <Link to={`/marketplace/${agent.slug}`}>
                  <Button
                    size="sm"
                    className="bg-[#E84142] hover:bg-[#D03031] text-xs font-bold text-white shadow-[0_0_15px_rgba(232,65,66,0.3)]"
                  >
                    <span>Hire Agent</span>
                    <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
          );
        })}
      </div>
    </section>
  );
}
