// Hand-built SVG charts (Recharts was not installable; see ADR-004).
// Spec: single-series bars <= 24px with 4px rounded data ends anchored to the
// baseline, hairline recessive grid, per-mark hover tooltips, text in ink
// tokens (never the series colour), and a table view for every chart.
import { useState } from "react";
import type { Point } from "../lib/types";
import { humanize, num, parseDay, shortDay, weekdayName } from "../lib/format";

function niceMax(v: number): number {
  if (v <= 0) return 10;
  const exp = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 1.5, 2, 2.5, 5, 10]) if (m * exp >= v) return m * exp;
  return 10 * exp;
}

/** Column path with a rounded top (data end) and square base. */
function columnPath(x: number, y: number, w: number, h: number, r = 4): string {
  const rr = Math.min(r, h, w / 2);
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`;
}

export function ColumnChart({ points, label, unit }: { points: Point[]; label: string; unit: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 720, H = 200, padL = 40, padB = 26, padT = 12;
  const max = niceMax(Math.max(0, ...points.map((p) => p.value)));
  const band = (W - padL) / Math.max(points.length, 1);
  const barW = Math.min(24, Math.max(3, band - 2));
  const scale = (v: number) => ((H - padB - padT) * Math.max(v, 0)) / max;
  const ticks = [0, max / 2, max];
  const labelEvery = Math.ceil(points.length / 7);
  const h = hover === null ? null : points[hover];
  return (
    <figure className="relative m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={`${label}, ${points.length} days`}>
        {ticks.map((t) => {
          const y = H - padB - scale(t);
          return (
            <g key={t}>
              <line x1={padL} x2={W} y1={y} y2={y} stroke="var(--lx-line)" strokeWidth={1} />
              <text x={padL - 8} y={y + 4} textAnchor="end" fontSize="11" fill="var(--lx-ink-3)">{num(t)}</text>
            </g>
          );
        })}
        {points.map((p, i) => {
          const x = padL + i * band + (band - barW) / 2;
          const bh = scale(p.value);
          return (
            <g key={p.date} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={padL + i * band} y={padT} width={band} height={H - padB - padT} fill="transparent" />
              {bh > 0 ? (
                <path d={columnPath(x, H - padB - bh, barW, bh)} fill="var(--lx-gold)" opacity={hover === null || hover === i ? 1 : 0.55} />
              ) : null}
              {i % labelEvery === 0 ? (
                <text x={x + barW / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--lx-ink-3)">{shortDay(p.date)}</text>
              ) : null}
            </g>
          );
        })}
      </svg>
      {h ? (
        <figcaption className="absolute top-0 right-0 panel px-3 py-1.5 text-xs pointer-events-none">
          <span className="text-ink-2">{shortDay(h.date)}</span> <span className="text-ink font-semibold">{num(h.value)} {unit}</span>
        </figcaption>
      ) : null}
    </figure>
  );
}

const HEAT = ["var(--lx-heat-0)", "var(--lx-heat-1)", "var(--lx-heat-2)", "var(--lx-heat-3)", "var(--lx-heat-4)"];

export function heatLevel(v: number): number {
  if (v <= 0) return 0;
  if (v === 1) return 1;
  if (v === 2) return 2;
  if (v <= 4) return 3;
  return 4;
}

/** Activity heatmap: columns are weeks (Mon..Sun rows), cells are local days. */
export function Heatmap({ points }: { points: Point[] }) {
  const [hover, setHover] = useState<Point | null>(null);
  if (points.length === 0) return null;
  const first = parseDay(points[0].date).weekday;
  const cell = 18, gap = 4, left = 30;
  const weeks = Math.ceil((points.length + first) / 7);
  const W = left + weeks * (cell + gap), H = 7 * (cell + gap) + 4;
  return (
    <figure className="m-0 grid gap-2">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="max-w-full h-auto" role="img" aria-label="Activity per day">
        {[0, 2, 4].map((r) => (
          <text key={r} x={0} y={r * (cell + gap) + cell - 3} fontSize="10" fill="var(--lx-ink-3)">{weekdayName(r)}</text>
        ))}
        {points.map((p, i) => {
          const idx = i + first;
          return (
            <rect
              key={p.date}
              x={left + Math.floor(idx / 7) * (cell + gap)}
              y={(idx % 7) * (cell + gap)}
              width={cell}
              height={cell}
              rx={3}
              fill={HEAT[heatLevel(p.value)]}
              onMouseEnter={() => setHover(p)}
              onMouseLeave={() => setHover(null)}
            >
              <title>{`${shortDay(p.date)}: ${p.value} ${p.value === 1 ? "activity" : "activities"}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="flex items-center gap-2 text-xs text-ink-3">
        <span>Less</span>
        {HEAT.map((c) => (
          <svg key={c} width="12" height="12" aria-hidden="true"><rect width="12" height="12" rx="3" fill={c} /></svg>
        ))}
        <span>More</span>
        <span className="ml-3 text-ink-2" aria-live="polite">{hover ? `${shortDay(hover.date)}: ${hover.value}` : ""}</span>
      </figcaption>
    </figure>
  );
}

/** Horizontal magnitude bars with the value at the tip. */
export function BarList({ rows, unit }: { rows: { label: string; value: number }[]; unit: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="grid gap-2.5">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(7rem,10rem)_1fr] items-center gap-3 text-sm">
          <span className="text-ink-2 truncate">{r.label}</span>
          <span className="flex items-center gap-2">
            <span
              className="h-3 rounded-r-[4px] bg-gold"
              style={{ width: `${(Math.max(r.value, 0) / max) * 100}%`, minWidth: r.value > 0 ? 2 : 0 }}
              aria-hidden="true"
            />
            <span className="text-ink tabular-nums whitespace-nowrap">{num(r.value)}{unit ? ` ${unit}` : ""}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function DataTable({ points, unit }: { points: Point[]; unit: string }) {
  return (
    <div className="max-h-64 overflow-auto">
      <table className="w-full text-sm">
        <thead className="text-ink-3 text-left">
          <tr><th className="py-1 font-normal">Day</th><th className="py-1 font-normal text-right">{humanize(unit)}</th></tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.date} className="row">
              <td className="py-1 text-ink-2">{weekdayName(parseDay(p.date).weekday)} {shortDay(p.date)}</td>
              <td className="py-1 text-right tabular-nums">{num(p.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
