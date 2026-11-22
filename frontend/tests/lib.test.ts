// Frontend unit tests: pure modules only (run with `node --import tsx --test`).
import { test } from "node:test";
import assert from "node:assert/strict";
import { addDays, dueLabel, humanize, parseDay, pct, shortDay, signedXp, streakLabel } from "../src/lib/format.ts";
import { ApiError, createClient, parseError, query } from "../src/lib/api.ts";
import { parseHash } from "../src/lib/router.ts";
import { draftFrom, toPayload } from "../src/lib/questForm.ts";

test("format: signed XP uses a real minus sign and grouping", () => {
  assert.equal(signedXp(35), "+35 XP");
  assert.equal(signedXp(-150), "−150 XP");
  assert.equal(signedXp(0), "0 XP");
  assert.equal(signedXp(1200), "+1,200 XP");
});

test("format: unknown rates are explained, never shown as 0%", () => {
  assert.equal(pct(null), "Not enough data");
  assert.equal(pct(0), "0%");
  assert.equal(pct(0.833), "83%");
});

test("format: calendar-day helpers do not shift across time zones", () => {
  assert.deepEqual(parseDay("2026-11-22"), { y: 2026, m: 11, d: 22, weekday: 6 });
  assert.equal(shortDay("2026-03-08"), "8 Mar");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
});

test("format: due labels", () => {
  const today = "2026-11-22";
  assert.equal(dueLabel(null, today), null);
  assert.equal(dueLabel("2026-11-22", today), "Due today");
  assert.equal(dueLabel("2026-11-23", today), "Due tomorrow");
  assert.equal(dueLabel("2026-11-21", today), "Was due yesterday");
  assert.equal(dueLabel("2026-11-10", today), "Was due 10 Nov");
  assert.equal(dueLabel("2026-11-26", today), "Due Thu");
  assert.equal(dueLabel("2026-12-25", today), "Due 25 Dec");
});

test("format: humanize and streak wording", () => {
  assert.equal(humanize("FINANCIAL_LITERACY"), "Financial literacy");
  assert.equal(streakLabel(0, "day"), "No current streak");
  assert.equal(streakLabel(3, "week"), "3-week streak");
});

test("questForm: payload never carries XP, coins or status", () => {
  const payload = toPayload({ ...draftFrom(), title: "  Solve two SQL join problems ", difficulty: "EPIC", due_date: "2026-11-30" });
  assert.equal(payload.title, "Solve two SQL join problems");
  for (const forbidden of ["xp", "xp_reward", "coins", "coin_reward", "status", "total_xp"]) {
    assert.equal(forbidden in payload, false, forbidden);
  }
  assert.equal(payload.due_date, "2026-11-30");
  assert.equal(payload.skill_id, null);
});

test("questForm: recurring quests drop the due date", () => {
  const payload = toPayload({ ...draftFrom(), title: "x", recurrence: "DAILY", due_date: "2026-11-30" });
  assert.equal(payload.due_date, null);
});

test("router: hash parsing", () => {
  assert.deepEqual(parseHash(""), { page: "command" });
  assert.deepEqual(parseHash("#/quests"), { page: "quests" });
  assert.deepEqual(parseHash("#/skills/12"), { page: "skills", skillId: 12 });
  assert.deepEqual(parseHash("#/skills/abc"), { page: "skills" });
  assert.deepEqual(parseHash("#/nope"), { page: "command" });
});

test("api: query strings skip empty values", () => {
  assert.equal(query({ a: 1, b: "", c: null, d: undefined, e: false }), "?a=1&e=false");
  assert.equal(query({}), "");
});

test("api: unsafe methods send the CSRF header; GET does not", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  const client = createClient(async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  await client.get("/quests");
  await client.post("/quests", { title: "x" });
  const getHeaders = calls[0].init?.headers as Record<string, string>;
  const postHeaders = calls[1].init?.headers as Record<string, string>;
  assert.equal(calls[0].url, "/api/v1/quests");
  assert.equal(getHeaders["X-LifeExe-CSRF"], undefined);
  assert.equal(postHeaders["X-LifeExe-CSRF"], "1");
  assert.equal(postHeaders["Content-Type"], "application/json");
  assert.equal(calls[1].init?.credentials, "same-origin");
});

test("api: server errors become ApiError with field messages", async () => {
  const res = new Response(
    JSON.stringify({ error: { code: "validation_error", message: "Some fields are invalid.", details: [{ loc: ["title"], msg: "String should have at least 1 character" }, { loc: ["timezone"], msg: "Value error, Unknown time zone." }] } }),
    { status: 422 },
  );
  const err = await parseError(res);
  assert.ok(err instanceof ApiError);
  assert.equal(err.status, 422);
  assert.equal(err.code, "validation_error");
  assert.deepEqual(err.fieldErrors(), { title: "String should have at least 1 character", timezone: "Unknown time zone." });
});

test("api: network failures are reported plainly", async () => {
  const client = createClient(async () => { throw new TypeError("fetch failed"); });
  await assert.rejects(client.get("/x"), (e: unknown) => e instanceof ApiError && e.code === "network_error");
});

test("api: 204 responses resolve to undefined", async () => {
  const client = createClient(async () => new Response(null, { status: 204 }));
  assert.equal(await client.post("/auth/logout"), undefined);
});
