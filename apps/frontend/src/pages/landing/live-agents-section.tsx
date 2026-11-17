import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowUpRight, Compass, ShieldCheck, Sparkles, TrendingUp, type LucideIcon } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatAtomic } from "@/lib/format";
import { LANDING_COPY, type LandingLang } from "@/pages/landing/landing-i18n";

interface FeaturedAgent {
  slug: string;
  name: string;
  price: string;
  tags: string[];
  erc8004Id: string;
  icon: LucideIcon;
}

const ICONS_BY_SLUG: Record<string, LucideIcon> = {
  "avax-defi-analyst": TrendingUp,
  "solidity-security-auditor": ShieldCheck,
  "avalanche-ecosystem-concierge": Compass,
};

const FALLBACK_AGENTS: FeaturedAgent[] = [
  {
    slug: "avax-defi-analyst",
    name: "AVAX DeFi Analyst",
    price: "0.25 USDC",
    tags: ["defi-analytics", "avalanche-c-chain", "yield-research"],
    erc8004Id: "#101",
    icon: TrendingUp,
  },
  {
    slug: "solidity-security-auditor",
    name: "Solidity Security Auditor",
    price: "0.50 USDC",
    tags: ["solidity-audit", "erc-8004", "security-check"],
    erc8004Id: "#102",
    icon: ShieldCheck,
  },
  {
    slug: "avalanche-ecosystem-concierge",
    name: "Avalanche Ecosystem Concierge",
    price: "0.10 USDC",
    tags: ["ecosystem-docs", "a2a-protocol", "assistant"],
    erc8004Id: "#103",
    icon: Compass,
  },
];

export function LiveAgentsSection({ lang }: { lang: LandingLang }) {
  const sectionRef = useRef<HTMLElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const copy = LANDING_COPY[lang].agents;

  const liveQuery = useQuery({
    queryKey: ["marketplace", "landing-featured"],
    queryFn: () => api.marketplace(),
    staleTime: 30_000,
    retry: false,
  });

  const displayAgents: (FeaturedAgent & { desc: string })[] =
    liveQuery.data && liveQuery.data.length >= 3
      ? liveQuery.data.slice(0, 3).map((a, idx) => ({
          slug: a.slug,
          name: a.name,
          price: `${formatAtomic(a.price_atomic)} USDC`,
          desc:
            lang === "en"
              ? (copy.fallbackDescriptions[a.slug] ?? a.description)
              : (a.description || copy.fallbackDescriptions[a.slug] || ""),
          tags: a.skills.slice(0, 4),
          erc8004Id: a.erc8004_agent_id != null ? `#${a.erc8004_agent_id}` : `#10${idx + 1}`,
          icon: ICONS_BY_SLUG[a.slug] ?? [TrendingUp, ShieldCheck, Compass][idx % 3],
        }))
      : FALLBACK_AGENTS.map((a) => ({
          ...a,
          desc: copy.fallbackDescriptions[a.slug] ?? "",
        }));

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
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

      const cardNodes = gsap.utils.toArray<HTMLElement>(".agent-card-reveal");
      if (cardNodes.length === 3) {
        gsap.to(cardNodes[0], {
          y: -25,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.0 },
        });
        gsap.to(cardNodes[1], {
          y: -60,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.0 },
        });
        gsap.to(cardNodes[2], {
          y: -35,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.0 },
        });
      }

      gsap.to(".glacier-shard-1", {
        y: -140,
        rotation: 20,
        ease: "none",
        scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.2 },
      });
      gsap.to(".glacier-shard-2", {
        y: -190,
        rotation: -25,
        ease: "none",
        scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.4 },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="marketplace-preview"
      className="relative z-30 px-4 py-24 sm:px-8 max-w-7xl mx-auto overflow-hidden"
    >
      <div className="pointer-events-none absolute -top-8 -left-10 glacier-shard-1 opacity-25 select-none hidden lg:block">
        <svg width="120" height="120" viewBox="0 0 100 100" fill="none">
          <polygon points="50,5 90,40 70,90 25,85 10,40" stroke="#E84142" strokeWidth="1.5" fill="rgba(232,65,66,0.04)" />
        </svg>
      </div>
      <div className="pointer-events-none absolute top-1/2 -right-12 glacier-shard-2 opacity-25 select-none hidden lg:block">
        <svg width="150" height="150" viewBox="0 0 100 100" fill="none">
          <polygon points="50,10 95,50 65,95 20,80 5,30" stroke="#94A3B8" strokeWidth="1.2" fill="rgba(148,163,184,0.06)" />
        </svg>
      </div>

      <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 text-xs font-mono font-bold text-[#E84142] tracking-wider uppercase mb-2 bg-red-50 border border-red-200/80 px-3 py-1 rounded-full">
            <Sparkles className="w-3.5 h-3.5 text-[#E84142]" />
            {copy.badge}
          </div>
          <h2 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900">
            {copy.heading}
          </h2>
          <p className="text-sm text-slate-600 mt-1 max-w-xl">{copy.subheading}</p>
        </div>

        <Link to="/marketplace">
          <Button variant="outline" className="border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-100 shadow-sm">
            <span>{copy.viewAll}</span>
            <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </Link>
      </div>

      <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {displayAgents.map((agent) => {
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

                <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                      {copy.serviceFee}
                    </div>
                    <div className="text-base font-black text-[#E84142]">{agent.price}</div>
                  </div>

                  <Link to={`/marketplace/${agent.slug}`}>
                    <Button
                      size="sm"
                      className="bg-[#E84142] hover:bg-[#D03031] text-xs font-bold text-white shadow-[0_0_15px_rgba(232,65,66,0.3)]"
                    >
                      <span>{copy.hire}</span>
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
