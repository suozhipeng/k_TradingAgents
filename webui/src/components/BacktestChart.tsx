import { useEffect, useRef } from "react";

export interface EquityCurve {
  strategy_name: string;
  dates: string[];
  values: number[];
}

interface BacktestChartProps {
  curves: EquityCurve[];
  height?: number;
}

const COLORS = ["#22d3ee", "#f59e0b", "#22c55e", "#ef4444", "#a78bfa", "#ec4899"];

/**
 * Multi-strategy equity curve chart rendered on Canvas 2D.
 * Each strategy is drawn as a separate coloured line.
 * Dark theme matching the TradingAgents WebUI palette.
 */
export default function BacktestChart({ curves, height = 360 }: BacktestChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !curves.length) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement?.clientWidth ?? 600;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const padding = { top: 24, right: 16, bottom: 40, left: 60 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    // Find global min/max across all curves
    let globalMin = Infinity;
    let globalMax = -Infinity;
    for (const curve of curves) {
      for (const v of curve.values) {
        if (v < globalMin) globalMin = v;
        if (v > globalMax) globalMax = v;
      }
    }
    const range = globalMax - globalMin || 1;
    // Add 10% padding
    const paddedMin = globalMin - range * 0.1;
    const paddedMax = globalMax + range * 0.1;
    const paddedRange = paddedMax - paddedMin || 1;

    // Background
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    // Grid
    ctx.strokeStyle = "rgba(148, 163, 184, 0.15)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    // Y-axis labels
    ctx.fillStyle = "#94a3b8";
    ctx.font = "10px monospace";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const val = paddedMax - (paddedRange / 4) * i;
      const y = padding.top + (chartH / 4) * i;
      ctx.fillText(val.toFixed(0), padding.left - 6, y + 3);
    }

    // Draw each curve
    curves.forEach((curve, idx) => {
      if (!curve.dates.length || !curve.values.length) return;

      const stepX = chartW / Math.max(curve.dates.length - 1, 1);
      ctx.strokeStyle = COLORS[idx % COLORS.length];
      ctx.lineWidth = 2;
      ctx.beginPath();

      curve.values.forEach((v, i) => {
        const x = padding.left + i * stepX;
        const y = padding.top + chartH - ((v - paddedMin) / paddedRange) * chartH;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Legend label
      const lastX = padding.left + (curve.dates.length - 1) * stepX;
      const lastY =
        padding.top +
        chartH -
        ((curve.values[curve.values.length - 1] - paddedMin) / paddedRange) * chartH;
      ctx.fillStyle = COLORS[idx % COLORS.length];
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      ctx.fillText(curve.strategy_name, Math.min(lastX + 4, width - padding.right - 80), lastY + 3);

      // Legend at top-right
      const legendY = padding.top + 4 + idx * 14;
      ctx.fillStyle = COLORS[idx % COLORS.length];
      ctx.fillRect(width - padding.right - 90, legendY, 10, 10);
      ctx.fillStyle = "#e2e8f0";
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      ctx.fillText(curve.strategy_name, width - padding.right - 76, legendY + 9);
    });

    // Bottom date labels (first, middle, last)
    if (curves.length > 0) {
      const firstCurve = curves[0];
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "center";
      const indices = [0, Math.floor(firstCurve.dates.length / 2), firstCurve.dates.length - 1];
      indices.forEach((i) => {
        if (i >= 0 && i < firstCurve.dates.length) {
          const stepX = chartW / Math.max(firstCurve.dates.length - 1, 1);
          const x = padding.left + i * stepX;
          ctx.fillText(firstCurve.dates[i].slice(5), x, height - 12);
        }
      });
    }
  }, [curves, height]);

  if (!curves.length) {
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
