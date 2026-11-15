import { useEffect } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { LandingNavbar } from "@/pages/landing/landing-navbar";
import { LiveAgentsSection } from "@/pages/landing/live-agents-section";
import { ParallaxHero } from "@/pages/landing/parallax-hero";
import { TechFeaturesSection } from "@/pages/landing/tech-features-section";

export function LandingPage() {
  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    // Lenis smooth scroll: Apple/Awwwards-level inertial scrolling with controlled braking
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
      {/* Morphing Navbar (Floating glass pill on white snow background) */}
      <LandingNavbar />

      {/* 1. GSAP ScrollTrigger 3D Cloud & Mountain Parallax Stage */}
      <ParallaxHero />

      {/* 2. Live Reference Agents Section */}
      <LiveAgentsSection />

      {/* 3. Core Architecture & Protocol Metrics */}
      <TechFeaturesSection />
    </div>
  );
}
