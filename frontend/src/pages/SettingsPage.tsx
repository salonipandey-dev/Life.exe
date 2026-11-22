import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { api } from "../lib/api";
import { clearCache, invalidate, useMutation, useQuery } from "../lib/query";
import type { Profile } from "../lib/types";
import { avatarGlyph, humanize, num } from "../lib/format";
import { PageHeader } from "../components/Shell";
import { ErrorState, InlineError, Skeleton, toast } from "../components/feedback";

/** Browser zone list plus the saved zone. Browsers may list legacy names
 * (Chromium: "Asia/Calcutta") while the server stores canonical ones
 * ("Asia/Kolkata"), so the saved value is always added to keep it selected. */
function timezones(current: string): string[] {
  let list = ["UTC", "Asia/Kolkata", "Europe/London", "America/New_York"];
  try {
    const fn = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf;
    if (fn) list = fn("timeZone");
  } catch { /* keep fallback */ }
  return [...new Set([current, ...list])].sort();
}

function Section({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <section className="panel px-5 py-5 grid gap-4">
      <div className="grid gap-1">
        <h2>{title}</h2>
        {note ? <p className="text-sm text-ink-3 max-w-[62ch]">{note}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function SettingsPage({ onSignedOut }: { onSignedOut: () => void }) {
  const p = useQuery("profile", () => api.get<Profile>("/profile"));
  if (p.error) return <ErrorState error={p.error} onRetry={p.refetch} />;
  if (!p.data) return <Skeleton lines={6} />;
  return <SettingsForms profile={p.data} onSignedOut={onSignedOut} />;
}

function SettingsForms({ profile, onSignedOut }: { profile: Profile; onSignedOut: () => void }) {
  const [form, setForm] = useState({
    display_name: profile.display_name,
    title: profile.title,
    avatar: profile.avatar,
    theme: profile.theme,
    timezone: profile.timezone,
    day_start_hour: profile.day_start_hour,
  });
  const save = useMutation(async () => api.patch<Profile>("/profile", form));
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const changePw = useMutation(async () => api.post("/account/password", pw));
  const [del, setDel] = useState({ password: "", confirm: "" });
  const remove = useMutation(async () => api.post("/account/delete", del));
  const logout = useMutation(async () => api.post("/auth/logout"));

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    if (await save.run()) {
      invalidate("profile", "dashboard", "me", "analytics", "quests", "habits");
      toast({ tone: "info", title: "Settings saved" });
    }
  }

  return (
    <div className="grid gap-6 max-w-[760px]">
      <PageHeader title="Settings" />

      <Section title="Character" note="Cosmetic only: titles and avatars never change how much XP anything is worth.">
        <form className="grid gap-4" onSubmit={saveProfile}>
          <label className="field">
            Display name
            <input className="input" value={form.display_name} maxLength={40} onChange={(e: { target: { value: string } }) => setForm({ ...form, display_name: e.target.value })} />
          </label>
          <fieldset className="grid gap-2">
            <legend className="text-sm text-ink-2 mb-1">Avatar</legend>
            <div className="flex flex-wrap gap-2">
              {profile.options.avatars.map((a) => (
                <button type="button" key={a} aria-pressed={form.avatar === a} aria-label={humanize(a)} onClick={() => setForm({ ...form, avatar: a })}
                  className={`size-11 rounded-full grid place-items-center text-xl border ${form.avatar === a ? "border-gold text-gold bg-coffee" : "border-line-strong text-ink-2"}`}>
                  {avatarGlyph(a)}
                </button>
              ))}
            </div>
          </fieldset>
          <div className="grid sm:grid-cols-2 gap-3">
            <label className="field">
              Title
              <select className="input" value={form.title} onChange={(e: { target: { value: string } }) => setForm({ ...form, title: e.target.value })}>
                {profile.options.titles.map((t) => (
                  <option key={t.title} value={t.title} disabled={!t.unlocked}>
                    {t.unlocked ? t.title : `${t.title} (level ${t.unlock_level})`}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Theme
              <select className="input" value={form.theme} onChange={(e: { target: { value: string } }) => setForm({ ...form, theme: e.target.value })}>
                {profile.options.themes.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
              </select>
            </label>
            <label className="field">
              Time zone
              <select className="input" value={form.timezone} onChange={(e: { target: { value: string } }) => setForm({ ...form, timezone: e.target.value })}>
                {timezones(profile.timezone).map((tz) => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </label>
            <label className="field">
              My day starts at
              <select className="input" value={form.day_start_hour} onChange={(e: { target: { value: string } }) => setForm({ ...form, day_start_hour: Number(e.target.value) })}>
                {[0, 1, 2, 3, 4, 5, 6].map((h) => <option key={h} value={h}>{h === 0 ? "Midnight" : `${h}:00`}</option>)}
              </select>
              <span className="text-xs text-ink-3">Work done before this hour counts toward the previous day.</span>
            </label>
          </div>
          <InlineError error={save.error} />
          <div><button className="btn btn-primary" disabled={save.pending}>Save settings</button></div>
        </form>
      </Section>

      <Section title="How rewards work" note="The server calculates every reward. These are the current rules.">
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          {Object.entries(profile.game.xp_by_difficulty).map(([d, xp]) => (
            <div key={d}><dt className="text-ink-3">{humanize(d)} quest</dt><dd className="xp">{xp} XP</dd></div>
          ))}
          <div><dt className="text-ink-3">Habit day</dt><dd className="xp">{profile.game.habit_checkin_xp} XP</dd></div>
          <div><dt className="text-ink-3">Daily XP limit</dt><dd className="text-ink">{num(profile.game.daily_xp_cap)} XP</dd></div>
          <div><dt className="text-ink-3">Coins</dt><dd className="text-ink">1 per {profile.game.coin_divisor} XP</dd></div>
        </dl>
        <p className="text-sm text-ink-3">Reaching level L takes 100 × (L − 1)^1.5 XP in total, rounded. Reopening a quest returns its XP; missing a habit never does.</p>
      </Section>

      <Section title="Password" note="Changing your password signs out your other devices.">
        <form className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end" onSubmit={async (e: FormEvent) => {
          e.preventDefault();
          if (await changePw.run()) { setPw({ current_password: "", new_password: "" }); toast({ tone: "info", title: "Password changed" }); }
        }}>
          <label className="field">Current password<input className="input" type="password" autoComplete="current-password" value={pw.current_password} onChange={(e: { target: { value: string } }) => setPw({ ...pw, current_password: e.target.value })} /></label>
          <label className="field">New password<input className="input" type="password" autoComplete="new-password" minLength={10} value={pw.new_password} onChange={(e: { target: { value: string } }) => setPw({ ...pw, new_password: e.target.value })} /></label>
          <button className="btn btn-quiet min-h-10" disabled={changePw.pending || pw.new_password.length < 10}>Change password</button>
        </form>
        <InlineError error={changePw.error} />
      </Section>

      <Section title="Your data" note="Download everything LIFE.EXE stores about you as JSON, or delete your account and all of its data.">
        <div className="flex flex-wrap gap-2">
          <a className="btn btn-quiet" href="/api/v1/account/export" download="lifeexe-export.json">Download my data</a>
          <button className="btn btn-quiet" disabled={logout.pending} onClick={async () => { await logout.run(); clearCache(); onSignedOut(); }}>Sign out</button>
        </div>
        <form className="grid gap-3 border-t border-line pt-4" onSubmit={async (e: FormEvent) => {
          e.preventDefault();
          if (await remove.run()) { clearCache(); onSignedOut(); }
        }}>
          <p className="text-sm text-ink-2">To delete your account permanently, enter your password and type DELETE.</p>
          <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
            <label className="field">Password<input className="input" type="password" autoComplete="current-password" value={del.password} onChange={(e: { target: { value: string } }) => setDel({ ...del, password: e.target.value })} /></label>
            <label className="field">Type DELETE<input className="input" value={del.confirm} onChange={(e: { target: { value: string } }) => setDel({ ...del, confirm: e.target.value })} /></label>
            <button className="btn btn-danger min-h-10" disabled={remove.pending || del.confirm !== "DELETE" || !del.password}>Delete account</button>
          </div>
          <InlineError error={remove.error} />
        </form>
      </Section>
    </div>
  );
}
