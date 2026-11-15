import { LandingNavbar } from "@/pages/landing/landing-navbar";
import { LiveAgentsSection } from "@/pages/landing/live-agents-section";
import { ParallaxHero } from "@/pages/landing/parallax-hero";
import { TechFeaturesSection } from "@/pages/landing/tech-features-section";

export function LandingPage() {
  return (
    <div className="relative min-h-screen w-full bg-[#08090E] text-slate-100 selection:bg-[#E84142] selection:text-white overflow-x-clip">
      {/* Fixed Header */}
      <LandingNavbar />

      {/* 1. Scroll-driven Cave Zoom Parallax Hero */}
      <ParallaxHero />

      {/* 2. Live Marketplace Agents Section */}
      <LiveAgentsSection />

      {/* 3. Tech Architecture & UniHack Pillars */}
      <TechFeaturesSection />
    </div>
  );
}
