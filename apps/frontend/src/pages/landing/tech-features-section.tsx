import { useEffect, useRef } from "react";
import { ArrowRight, CheckCircle2, Cpu, KeyRound, ShieldCheck, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { Button } from "@/components/ui/button";
import { LANDING_COPY, type LandingLang } from "@/pages/landing/landing-i18n";

const PILLAR_ICONS = [Cpu, Zap, ShieldCheck] as const;

function MetricItem({ value, label, desc }: { value: string; label: string; desc: string }) {
  const numberRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const rawNum = parseFloat(value);
    const suffix = value.replace(/[0-9.]/g, "");
    if (!isNaN(rawNum) && numberRef.current) {
      const state = { val: 0 };
      gsap.to(state, {
        val: rawNum,
        duration: 1.4,
        ease: "power2.out",
        scrollTrigger: {
          trigger: numberRef.current,
          start: "top 92%",
          toggleActions: "play none none reverse",
        },
        onUpdate: () => {
          if (numberRef.current) {
            numberRef.current.textContent =
              (rawNum % 1 === 0 ? Math.round(state.val) : state.val.toFixed(2)) + suffix;
          }
        },
      });
    }
  }, [value]);

  return (
    <div className="metric-card-reveal rounded-2xl border border-slate-200/80 bg-white/90 backdrop-blur-xl p-5 shadow-[0_4px_20px_rgba(15,23,42,0.04)] will-change-transform">
      <div ref={numberRef} className="text-3xl sm:text-4xl font-black text-[#E84142] font-mono">
        {value}
      </div>
      <div className="text-xs font-bold text-slate-800 mt-1">{label}</div>
      <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">{desc}</div>
    </div>
  );
}

export function TechFeaturesSection({ lang }: { lang: LandingLang }) {
  const sectionRef = useRef<HTMLElement>(null);
  const marqueeRef = useRef<HTMLDivElement>(null);
  const pillarsRef = useRef<HTMLDivElement>(null);
  const copy = LANDING_COPY[lang].tech;

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      if (marqueeRef.current) {
        gsap.to(marqueeRef.current, {
          x: -180,
          ease: "none",
          scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.2 },
        });
      }

      gsap.from(".metric-card-reveal", {
        scrollTrigger: { trigger: ".metrics-container", start: "top 88%", toggleActions: "play none none reverse" },
        y: 30,
        opacity: 0,
        duration: 0.75,
        stagger: 0.12,
        ease: "power2.out",
        clearProps: "transform,opacity",
      });

      if (pillarsRef.current) {
        gsap.from(".pillar-card-reveal", {
          scrollTrigger: { trigger: pillarsRef.current, start: "top 85%", toggleActions: "play none none reverse" },
          y: 40,
          opacity: 0,
          duration: 0.85,
          stagger: 0.18,
          ease: "power2.out",
          clearProps: "transform,opacity",
        });

        const pillarNodes = gsap.utils.toArray<HTMLElement>(".pillar-card-reveal");
        if (pillarNodes.length === 3) {
          gsap.to(pillarNodes[0], {
            y: -25,
            ease: "none",
            scrollTrigger: { trigger: pillarsRef.current, start: "top bottom", end: "bottom top", scrub: 1.0 },
          });
          gsap.to(pillarNodes[1], {
            y: -60,
            ease: "none",
            scrollTrigger: { trigger: pillarsRef.current, start: "top bottom", end: "bottom top", scrub: 1.0 },
          });
          gsap.to(pillarNodes[2], {
            y: -30,
            ease: "none",
            scrollTrigger: { trigger: pillarsRef.current, start: "top bottom", end: "bottom top", scrub: 1.0 },
          });
        }
      }

      gsap.to(".tech-shard-1", {
        y: -130,
        rotation: 30,
        ease: "none",
        scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.2 },
      });
      gsap.to(".tech-shard-2", {
        y: -170,
        rotation: -25,
        ease: "none",
        scrollTrigger: { trigger: sectionRef.current, start: "top bottom", end: "bottom top", scrub: 1.3 },
      });
    }, sectionRef);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      id="architecture"
      className="relative z-30 pt-16 pb-20 border-t border-slate-200 overflow-hidden bg-slate-50/60"
    >
      <div className="pointer-events-none absolute top-1/4 -left-10 tech-shard-1 opacity-25 select-none hidden lg:block">
        <svg width="130" height="130" viewBox="0 0 100 100" fill="none">
          <polygon points="50,5 95,40 75,90 20,80 5,35" stroke="#E84142" strokeWidth="1.2" fill="rgba(232,65,66,0.03)" />
        </svg>
      </div>
      <div className="pointer-events-none absolute bottom-1/4 -right-10 tech-shard-2 opacity-25 select-none hidden lg:block">
        <svg width="150" height="150" viewBox="0 0 100 100" fill="none">
          <polygon points="50,10 90,50 60,95 15,75 10,25" stroke="#94A3B8" strokeWidth="1.2" fill="rgba(148,163,184,0.04)" />
        </svg>
      </div>

      <div className="w-full overflow-hidden py-4 select-none opacity-25 pointer-events-none mb-8">
        <div
          ref={marqueeRef}
          className="flex whitespace-nowrap text-3xl sm:text-5xl font-black font-mono tracking-widest uppercase text-transparent bg-gradient-to-r from-slate-300 via-[#E84142]/40 to-slate-300 bg-clip-text will-change-transform"
          style={{ width: "250%" }}
        >
          <span>
            AUTONOMOUS AI AGENTS · AVALANCHE C-CHAIN · ERC-8004 IDENTITY · X402 MICROPAYMENTS · TURNKEY MPC · ERC-8183 ESCROW ·
          </span>
          <span className="ml-8">
            AUTONOMOUS AI AGENTS · AVALANCHE C-CHAIN · ERC-8004 IDENTITY · X402 MICROPAYMENTS · TURNKEY MPC · ERC-8183 ESCROW ·
          </span>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-8">
        <div id="metrics" className="metrics-container grid grid-cols-2 md:grid-cols-4 gap-4 mb-20">
          {copy.metrics.map((m, idx) => (
            <MetricItem key={idx} value={m.value} label={m.label} desc={m.desc} />
          ))}
        </div>

        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 text-xs font-mono font-bold text-[#E84142] tracking-wider uppercase mb-2 bg-red-50 border border-red-200/80 px-3.5 py-1 rounded-full">
            <KeyRound className="w-3.5 h-3.5 text-[#E84142]" />
            {copy.badge}
          </div>
          <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-slate-900">
            {copy.heading}
          </h2>
          <p className="text-sm sm:text-base text-slate-600 mt-2 font-light">{copy.subheading}</p>
        </div>

        <div ref={pillarsRef} className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {copy.pillars.map((p, idx) => {
            const Icon = PILLAR_ICONS[idx % PILLAR_ICONS.length];
            return (
              <div
                key={idx}
                className="pillar-card-reveal relative rounded-2xl border border-slate-200/90 bg-white/90 p-8 backdrop-blur-xl shadow-[0_4px_25px_rgba(15,23,42,0.04)] transition-all duration-300 hover:border-[#E84142]/60 hover:-translate-y-1.5 hover:shadow-[0_16px_40px_rgba(232,65,66,0.12)] flex flex-col justify-between will-change-transform"
              >
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-red-50 to-slate-100 border border-red-200/80 text-[#E84142] shadow-sm">
                      <Icon className="h-6 w-6" />
                    </div>
                    <span className="rounded-md bg-red-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#E84142] border border-red-200/70 font-mono">
                      {p.badge}
                    </span>
                  </div>

                  <h3 className="text-xl font-bold text-slate-900">{p.title}</h3>
                  <div className="text-xs font-semibold text-[#E84142] mt-0.5 mb-3 font-mono">
                    {p.subtitle}
                  </div>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed font-light mb-6">
                    {p.desc}
                  </p>
                </div>

                <div className="space-y-2 border-t border-slate-100 pt-4">
                  {p.bulletPoints.map((item, bIdx) => (
                    <div key={bIdx} className="flex items-center gap-2 text-xs text-slate-700">
                      <CheckCircle2 className="h-3.5 w-3.5 text-[#E84142] shrink-0" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-20 rounded-3xl border border-red-500/20 bg-gradient-to-r from-[#E84142] via-[#D03031] to-[#A81D20] p-8 sm:p-12 flex flex-col md:flex-row items-center justify-between gap-6 shadow-[0_15px_45px_rgba(232,65,66,0.35)] text-white">
          <div className="max-w-xl text-center md:text-left">
            <h3 className="text-2xl sm:text-3xl font-black text-white">{copy.ctaTitle}</h3>
            <p className="text-sm text-red-100 mt-2 font-light">{copy.ctaDesc}</p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Link to="/agents/new">
              <Button size="lg" className="bg-white hover:bg-red-50 text-xs sm:text-sm font-bold text-[#E84142] shadow-xl">
                <span>{copy.ctaCreate}</span>
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </Link>
            <Link to="/dashboard">
              <Button variant="outline" size="lg" className="border-white/30 bg-white/10 text-xs sm:text-sm text-white hover:bg-white/20">
                {copy.ctaDashboard}
              </Button>
            </Link>
          </div>
        </div>

        <footer className="mt-24 pt-8 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <div>
            © 2026 <b>Avaxagent Studio</b> · Built for <b>UniHack 2026</b> on Avalanche.
          </div>
          <div className="flex items-center gap-6">
            <a href="https://testnet.snowtrace.io" target="_blank" rel="noreferrer" className="hover:text-slate-800 transition-colors">
              Snowtrace Fuji
            </a>
            <a href="https://github.com/MeoCam-lazy/avaxagent-studio" target="_blank" rel="noreferrer" className="hover:text-slate-800 transition-colors">
              GitHub Repo
            </a>
          </div>
        </footer>
      </div>
    </section>
  );
}
