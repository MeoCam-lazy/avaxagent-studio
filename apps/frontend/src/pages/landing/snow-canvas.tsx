import { useEffect, useRef } from "react";

export function SnowCanvas() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId = 0;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const onResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", onResize);

    const flakes = Array.from({ length: 70 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      r: Math.random() * 2.2 + 0.6,
      vy: Math.random() * 1.0 + 0.5,
      vx: (Math.random() - 0.5) * 0.5,
      alpha: Math.random() * 0.7 + 0.2,
      isCrimson: Math.random() < 0.15, // 15% are Avalanche red embers
    }));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      for (const f of flakes) {
        f.y += f.vy;
        f.x += f.vx;

        if (f.y > height) {
          f.y = -5;
          f.x = Math.random() * width;
        }
        if (f.x > width) f.x = 0;
        if (f.x < 0) f.x = width;

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        if (f.isCrimson) {
          ctx.fillStyle = `rgba(232, 65, 66, ${f.alpha})`;
          ctx.shadowColor = "#E84142";
          ctx.shadowBlur = 6;
        } else {
          ctx.fillStyle = `rgba(240, 246, 255, ${f.alpha})`;
          ctx.shadowBlur = 0;
        }
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0 h-full w-full opacity-80"
      style={{ zIndex: 15 }}
    />
  );
}
