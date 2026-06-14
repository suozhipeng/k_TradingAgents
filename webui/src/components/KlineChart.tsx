import { useEffect, useRef } from "react";

export interface OHLCV {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface KlineChartProps {
  data: OHLCV[];
  symbol?: string;
  height?: number;
}

/**
 * A lightweight OHLCV chart rendered on a Canvas 2D context.
 * Draws a close-price line chart with volume bars underneath.
 * Uses a dark theme matching the TradingAgents WebUI palette.
 */
export default function KlineChart({
  data,
  symbol = "",
  height = 320,
}: KlineChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data.length) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement?.clientWidth ?? 600;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const padding = { top: 24, right: 16, bottom: 48, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    const volH = 48;
    const priceH = chartH - volH - 8;

    // Compute min/max
    const closes = data.map((d) => d.close);
    const volumes = data.map((d) => d.volume);
    const minPrice = Math.min(...closes);
    const maxPrice = Math.max(...closes);
    const maxVol = Math.max(...volumes);
    const priceRange = maxPrice - minPrice || 1;

    const stepX = chartW / Math.max(data.length - 1, 1);

    // Background
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    // Grid
    ctx.strokeStyle = "rgba(148, 163, 184, 0.15)";
    ctx.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const y = padding.top + (priceH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    // Price axis labels
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px monospace";
    ctx.textAlign = "right";
    for (let i = 0; i < 5; i++) {
      const price = maxPrice - (priceRange / 4) * i;
      const y = padding.top + (priceH / 4) * i;
      ctx.fillText(price.toFixed(2), padding.left - 6, y + 3);
    }

    // Price line
    ctx.strokeStyle = "#22d3ee";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    data.forEach((d, i) => {
      const x = padding.left + i * stepX;
      const y = padding.top + priceH - ((d.close - minPrice) / priceRange) * priceH;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Volume bars
    data.forEach((d, i) => {
      const x = padding.left + i * stepX;
      const barW = Math.max(stepX * 0.6, 1);
      const volBarH = (d.volume / maxVol) * volH;
      const yBase = padding.top + priceH + 8;
      ctx.fillStyle = d.close >= (data[i - 1]?.close ?? d.close) ? "#22c55e" : "#ef4444";
      ctx.fillRect(x - barW / 2, yBase + volH - volBarH, barW, volBarH);
    });

    // Date labels (5 evenly spaced)
    ctx.fillStyle = "#64748b";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    const labelStep = Math.max(Math.floor(data.length / 5), 1);
    for (let i = 0; i < data.length; i += labelStep) {
      const x = padding.left + i * stepX;
      const dateStr = data[i].trade_date?.slice(5) ?? "";
      ctx.fillText(dateStr, x, height - 12);
    }

    // Symbol title
    if (symbol) {
      ctx.fillStyle = "#e2e8f0";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(symbol, padding.left, 16);
    }
  }, [data, symbol, height]);

  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center rounded border border-white/10 bg-slate-950 text-sm text-slate-400"
        style={{ height }}
      >
        No data
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className="w-full rounded border border-white/10"
      style={{ height }}
    />
  );
}
