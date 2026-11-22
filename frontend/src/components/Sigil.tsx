// The character sigil: level numeral inside an XP ring. The ring shows progress
// *within* the current level using server-computed values only.
import { useEffect, useState } from "react";
import type { Progress } from "../lib/types";
import { num } from "../lib/format";

export function Sigil({ progress, size = 168 }: { progress: Progress; size?: number }) {
  const stroke = Math.max(6, Math.round(size / 22));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    // one orchestrated motion: the arc draws to its value on load/level change
    const id = requestAnimationFrame(() => setShown(progress.progress_ratio));
    return () => cancelAnimationFrame(id);
  }, [progress.progress_ratio]);
  const label = `Level ${progress.level}. ${num(progress.xp_into_level)} of ${num(progress.xp_span)} XP into this level.`;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--lx-gold-track)" strokeWidth={stroke} />
        <circle
          className="sigil-arc"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--lx-gold)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - Math.min(Math.max(shown, 0), 1))}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute inset-0 grid place-content-center text-center">
        <span className="text-ink-3 text-xs">Level</span>
        <span className="font-display text-gold-ink leading-none" style={{ fontSize: size * 0.42 }}>
          {progress.level}
        </span>
      </div>
    </div>
  );
}

export function XpLine({ progress }: { progress: Progress }) {
  return (
    <p className="text-sm text-ink-2">
      <span className="xp">{num(progress.total_xp)} XP</span> total. {num(progress.xp_to_next_level)} XP to level{" "}
      {progress.level + 1}.
    </p>
  );
}
