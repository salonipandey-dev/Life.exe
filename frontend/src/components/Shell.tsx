import type { ReactNode } from "react";
import type { Route } from "../lib/router";
import { avatarGlyph } from "../lib/format";

type Page = Route["page"];

const ICONS: Record<Page, ReactNode> = {
  command: <path d="M4 12a8 8 0 1 0 16 0a8 8 0 1 0-16 0M12 8v4l3 2" />,
  quests: <path d="M6 4h12v16l-6-4-6 4z" />,
  habits: <path d="M5 12l4 4L19 6" />,
  skills: <path d="M12 3l3 6 6 1-4.5 4 1 6L12 17l-5.5 3 1-6L3 10l6-1z" />,
  analytics: <path d="M5 20V10M12 20V4M19 20v-7" />,
  achievements: <path d="M8 4h8v5a4 4 0 0 1-8 0zM12 13v4M8 20h8M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4" />,
  settings: <path d="M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />,
};

const NAV: { page: Page; href: string; label: string; short: string; mobile: boolean }[] = [
  { page: "command", href: "#/", label: "Command Center", short: "Today", mobile: true },
  { page: "quests", href: "#/quests", label: "Quest Board", short: "Quests", mobile: true },
  { page: "habits", href: "#/habits", label: "Habits", short: "Habits", mobile: true },
  { page: "skills", href: "#/skills", label: "Skill Tree", short: "Skills", mobile: true },
  { page: "analytics", href: "#/analytics", label: "Analytics", short: "Stats", mobile: true },
  { page: "achievements", href: "#/achievements", label: "Achievements", short: "Badges", mobile: false },
  { page: "settings", href: "#/settings", label: "Settings", short: "Settings", mobile: false },
];

function Icon({ page }: { page: Page }) {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[page]}
    </svg>
  );
}

export function Shell({ route, name, avatar, level, children }: { route: Route; name: string; avatar: string; level: number; children: ReactNode }) {
  return (
    <div className="min-h-screen md:grid md:grid-cols-[236px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 btn btn-primary z-50">Skip to content</a>
      <aside className="hidden md:flex flex-col gap-8 sticky top-0 h-screen border-r border-line px-4 py-6">
        <a href="#/" className="px-2 font-display text-2xl tracking-tight text-ink" aria-label="LIFE.EXE home">
          LIFE<span className="text-gold">.</span>EXE
        </a>
        <nav aria-label="Main" className="grid gap-1">
          {NAV.map((n) => {
            const active = route.page === n.page;
            return (
              <a key={n.page} href={n.href} aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-[10px] px-3 py-2 text-sm ${active ? "bg-accent-deep text-ink" : "text-ink-2 hover:text-ink hover:bg-raised"}`}>
                <Icon page={n.page} />
                {n.label}
              </a>
            );
          })}
        </nav>
        <a href="#/settings" className="mt-auto flex items-center gap-3 rounded-[10px] px-3 py-2 hover:bg-raised">
          <span className="size-9 grid place-items-center rounded-full bg-raised text-gold text-lg" aria-hidden="true">{avatarGlyph(avatar)}</span>
          <span className="min-w-0">
            <span className="block text-sm text-ink truncate">{name}</span>
            <span className="block text-xs text-ink-3">Level {level}</span>
          </span>
        </a>
      </aside>

      <header className="md:hidden sticky top-0 z-30 flex items-center justify-between px-4 py-3 bg-bg/90 backdrop-blur border-b border-line">
        <a href="#/" className="font-display text-xl text-ink">LIFE<span className="text-gold">.</span>EXE</a>
        <div className="flex items-center gap-1">
          <a href="#/achievements" className="btn btn-ghost" aria-label="Achievements"><Icon page="achievements" /></a>
          <a href="#/settings" className="btn btn-ghost" aria-label="Settings"><Icon page="settings" /></a>
        </div>
      </header>

      <main id="main" className="px-4 md:px-10 py-6 md:py-10 pb-28 md:pb-12 max-w-[1180px] w-full">{children}</main>

      <nav aria-label="Main" className="md:hidden fixed bottom-0 inset-x-0 z-30 grid grid-cols-5 border-t border-line bg-bg/95 backdrop-blur pb-[env(safe-area-inset-bottom)]">
        {NAV.filter((n) => n.mobile).map((n) => {
          const active = route.page === n.page;
          return (
            <a key={n.page} href={n.href} aria-current={active ? "page" : undefined}
              className={`flex flex-col items-center gap-0.5 py-2 text-[11px] ${active ? "text-accent-ink" : "text-ink-3"}`}>
              <Icon page={n.page} />
              {n.short}
            </a>
          );
        })}
      </nav>
    </div>
  );
}

export function PageHeader({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6 md:mb-8">
      <div className="grid gap-1.5">
        <h1>{title}</h1>
        {children ? <p className="text-ink-2 max-w-[62ch]">{children}</p> : null}
      </div>
      {action}
    </div>
  );
}
