import { useEffect, useState } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import {
  getStoredLandingLang,
  setStoredLandingLang,
  type LandingLang,
} from "@/pages/landing/landing-i18n";
import { LandingNavbar } from "@/pages/landing/landing-navbar";
import { LiveAgentsSection } from "@/pages/landing/live-agents-section";
import { ParallaxHero } from "@/pages/landing/parallax-hero";
import { TechFeaturesSection } from "@/pages/landing/tech-features-section";

export function LandingPage() {
  const [lang, setLang] = useState<LandingLang>(() => getStoredLandingLang());

  function toggleLang() {
    const next: LandingLang = lang === "vi" ? "en" : "vi";
    setLang(next);
    setStoredLandingLang(next);
  }

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const lenis = new Lenis({
      duration: 0.75,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      wheelMultiplier: 0.9,
      smoothWheel: true,
    });

    lenis.on("scroll", ScrollTrigger.update);

    const updateTicker = (time: number) => {
      lenis.raf(time * 1000);
    };
    gsap.ticker.add(updateTicker);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(updateTicker);
      lenis.destroy();
    };
  }, []);

  return (
    <div className="relative min-h-screen w-full bg-[#F8FAFC] text-slate-900 selection:bg-[#E84142] selection:text-white overflow-x-clip">
      <LandingNavbar lang={lang} onToggleLang={toggleLang} />
      <ParallaxHero lang={lang} onToggleLang={toggleLang} />
      <LiveAgentsSection lang={lang} />
      <TechFeaturesSection lang={lang} />
    </div>
  );
}
