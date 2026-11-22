import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import { useMutation } from "../lib/query";
import { FormError } from "../components/feedback";

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function AuthPage({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const submit = useMutation(async () => {
    if (mode === "register") {
      await api.post("/auth/register", { email, password, display_name: name.trim() || "Player", timezone: browserTimezone() });
    } else {
      await api.post("/auth/login", { email, password });
    }
    return true;
  });
  const fields = submit.error instanceof ApiError ? submit.error.fieldErrors() : {};

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (await submit.run()) onSignedIn();
  }

  return (
    <main className="min-h-screen grid md:grid-cols-[1.1fr_1fr]">
      <section className="hidden md:flex flex-col justify-between p-12 border-r border-line">
        <p className="font-display text-2xl">LIFE<span className="text-gold">.</span>EXE</p>
        <div className="grid gap-6 max-w-[34rem]">
          <p className="font-display text-6xl leading-[1.02] text-ink">Level up your reality.</p>
          <p className="text-ink-2 text-lg max-w-[46ch]">
            Turn study sessions, projects and habits into quests. Progress comes from what you actually log, rests are allowed,
            and a missed day never costs you anything.
          </p>
        </div>
        <p className="text-ink-3 text-sm">Your data stays in your account. Export or delete it any time.</p>
      </section>

      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-[400px] grid gap-6">
          <div className="md:hidden grid gap-2">
            <p className="font-display text-2xl">LIFE<span className="text-gold">.</span>EXE</p>
            <p className="font-display text-4xl leading-tight">Level up your reality.</p>
          </div>
          <div className="grid grid-cols-2 p-1 rounded-[12px] bg-surface border border-line" role="tablist" aria-label="Account">
            {(["signin", "register"] as const).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m}
                className={`py-2 rounded-[9px] text-sm ${mode === m ? "bg-raised text-ink" : "text-ink-3 hover:text-ink"}`}
                onClick={() => { setMode(m); submit.reset(); }}>
                {m === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>
          <form className="grid gap-4" onSubmit={onSubmit} noValidate>
            {mode === "register" ? (
              <label className="field">
                Display name
                <input className="input" value={name} maxLength={40} autoComplete="nickname"
                  aria-invalid={Boolean(fields.display_name)}
                  onChange={(e: { target: { value: string } }) => setName(e.target.value)} />
                {fields.display_name ? <span className="text-danger text-xs">{fields.display_name}</span> : null}
              </label>
            ) : null}
            <label className="field">
              Email
              <input className="input" type="email" value={email} autoComplete="email" required
                aria-invalid={Boolean(fields.email)}
                onChange={(e: { target: { value: string } }) => setEmail(e.target.value)} />
              {fields.email ? <span className="text-danger text-xs">{fields.email}</span> : null}
            </label>
            <label className="field">
              Password
              <input className="input" type="password" value={password} required minLength={mode === "register" ? 10 : 1}
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                aria-invalid={Boolean(fields.password)}
                onChange={(e: { target: { value: string } }) => setPassword(e.target.value)} />
              {mode === "register" ? <span className="text-xs text-ink-3">At least 10 characters. A short phrase works well.</span> : null}
              {fields.password ? <span className="text-danger text-xs">{fields.password}</span> : null}
            </label>
            <FormError error={submit.error} shown={["display_name", "email", "password"]} />
            <button className="btn btn-primary min-h-11" disabled={submit.pending}>
              {mode === "register" ? "Create account" : "Sign in"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
