// Accessible modal built on the native <dialog> element (focus trapping,
// Escape to close and inert background come from the browser).
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

export function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      aria-labelledby="dialog-title"
      className="panel w-[min(560px,calc(100vw-1.5rem))] max-h-[90vh] p-0 text-ink backdrop:bg-black/60 m-auto"
    >
      {open ? (
        <div className="p-5 md:p-6 grid gap-5">
          <div className="flex items-center justify-between gap-4">
            <h2 id="dialog-title">{title}</h2>
            <button className="btn btn-ghost" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
          {children}
        </div>
      ) : null}
    </dialog>
  );
}
