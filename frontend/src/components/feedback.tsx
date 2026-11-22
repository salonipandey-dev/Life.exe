// Loading, empty and error states, plus the toast system.
import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import type { ApiError } from "../lib/api";

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="grid gap-3" role="status" aria-live="polite">
      <span className="sr-only">Loading</span>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton h-12" />
      ))}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="px-5 py-8 text-center grid gap-2 justify-items-center">
      <h3 className="text-ink">{title}</h3>
      {children ? <p className="text-ink-2 max-w-[46ch] text-sm">{children}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="panel px-5 py-6 grid gap-3 justify-items-start">
      <h3>That didn't load</h3>
      <p className="text-ink-2 text-sm">{error.message}</p>
      {onRetry ? (
        <button className="btn btn-quiet" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function InlineError({ error }: { error: ApiError | null }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-danger">
      {error.message}
    </p>
  );
}

/** Form-level error: hides only messages already shown next to a field, so a
 * rejected field without its own input (e.g. time zone) is never silent. */
export function FormError({ error, shown }: { error: ApiError | null; shown: string[] }) {
  if (!error) return null;
  const fields = error.fieldErrors();
  const extra = Object.entries(fields).filter(([k]) => !shown.includes(k));
  if (Object.keys(fields).length > 0 && extra.length === 0) return null;
  return (
    <p role="alert" className="text-sm text-danger">
      {extra.length ? extra.map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" ") : error.message}
    </p>
  );
}

// --- toasts -----------------------------------------------------------------

export interface Toast {
  id: number;
  tone: "reward" | "info" | "error";
  title: string;
  body?: string;
}

let toasts: Toast[] = [];
let nextId = 1;
const subs = new Set<() => void>();

function emit() {
  for (const s of subs) s();
}

export function toast(t: Omit<Toast, "id">, ms = 5000): void {
  const id = nextId++;
  toasts = [...toasts, { ...t, id }].slice(-4);
  emit();
  window.setTimeout(() => dismiss(id), ms);
}

function dismiss(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

export function Toaster() {
  const list = useSyncExternalStore(
    (cb) => {
      subs.add(cb);
      return () => subs.delete(cb);
    },
    () => toasts,
  );
  return (
    <div className="fixed z-50 right-4 bottom-24 md:bottom-6 grid gap-2 w-[min(360px,calc(100vw-2rem))]" aria-live="polite">
      {list.map((t) => (
        <div
          key={t.id}
          role={t.tone === "error" ? "alert" : "status"}
          className={`toast-in px-4 py-3 grid gap-0.5 ${t.tone === "reward" ? "panel-reward" : "panel"}`}
        >
          <div className="flex items-start justify-between gap-3">
            <p className={`font-semibold ${t.tone === "reward" ? "text-gold-ink" : t.tone === "error" ? "text-danger" : "text-ink"}`}>
              {t.title}
            </p>
            <button className="text-ink-3 hover:text-ink text-sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              ✕
            </button>
          </div>
          {t.body ? <p className="text-sm text-ink-2">{t.body}</p> : null}
        </div>
      ))}
    </div>
  );
}
