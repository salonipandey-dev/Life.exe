# 06 API specification

Base path `/api/v1`. The machine-readable OpenAPI 3.1 document is generated from the route registry: served at `GET /api/v1/openapi.json` and committed as `docs/api/openapi.json` (regenerate with `python backend/scripts/export_openapi.py`).

## Conventions
- **Format:** JSON request and response bodies; `Content-Type: application/json` is required for bodies (400 otherwise). Bodies over 64 KiB return 413.
- **Authentication:** `lifeexe_session` HttpOnly cookie set by register/login. Missing, forged or expired sessions return 401.
- **CSRF:** every POST/PATCH/DELETE must send `X-LifeExe-CSRF: 1`; a present `Origin` must be the API's own origin (or listed in `LIFEEXE_ALLOWED_ORIGINS`). Otherwise 403.
- **Validation:** unknown fields are rejected (`extra="forbid"`), so clients cannot send XP, coins, totals or status. Errors return 422 with field details; submitted values are never echoed.
- **Authorization:** every resource is scoped to the signed-in user. Another user's id returns 404, not 403.
- **Pagination:** `limit` (1-100, default 50) and `offset`; responses include `total`.
- **Rate limits:** register, login, password change and account deletion share a per-IP limit (default 10/min). Exceeding it returns 429 with `Retry-After`.
- **Errors:**
  ```json
  { "error": { "code": "already_completed", "message": "This quest occurrence is already completed.", "details": null } }
  ```
  | Status | Codes |
  |---|---|
  | 400 | bad_request |
  | 401 | unauthorized |
  | 403 | forbidden |
  | 404 | not_found |
  | 409 | conflict, invalid_transition, already_completed |
  | 413 | payload_too_large |
  | 422 | validation_error |
  | 429 | rate_limited |
  | 500 | internal_error (no internals in the body) |

## Endpoints (43 operations)
| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | /auth/register | Create an account and sign in (201) | no |
| POST | /auth/login | Sign in | no |
| POST | /auth/logout | Revoke the session (204) | no |
| GET | /auth/me | Current player profile | yes |
| GET | /profile | Profile, `today`, progress, coins, attributes, cosmetic options, current game rules | yes |
| PATCH | /profile | Display name, title, avatar, theme, time zone, day start | yes |
| POST | /account/password | Change password, revoke other sessions (204) | yes |
| GET | /account/export | Download all personal data (JSON attachment) | yes |
| POST | /account/delete | Delete account and all data; body `{password, confirm: "DELETE"}` (204) | yes |
| GET | /dashboard | Command Center data | yes |
| GET | /quests | List with `status` (comma list), `category`, `difficulty`, `q`, `include_archived`, `sort`, `limit`, `offset` | yes |
| POST | /quests | Create (201) | yes |
| GET | /quests/{id} | Detail with completion history | yes |
| PATCH | /quests/{id} | Edit or reschedule (partial; `null` clears optional fields) | yes |
| DELETE | /quests/{id} | Delete a quest without completion history (204) | yes |
| POST | /quests/{id}/complete | Complete current occurrence; awards XP once | yes |
| POST | /quests/{id}/reopen | Reverse current occurrence's XP | yes |
| POST | /quests/{id}/actions/{action} | publish, start, pause, resume, cancel, expire, restore | yes |
| POST | /quests/{id}/archive, /unarchive | Hide/show a finished quest | yes |
| GET | /habits | Habits with stats and 28-day calendar (`include_archived`) | yes |
| POST | /habits | Create (201) | yes |
| GET, PATCH | /habits/{id} | Read, edit | yes |
| POST | /habits/{id}/logs | Record or correct a day `{date?, entry_type: ENTRY or REST, value?, note?}` | yes |
| DELETE | /habits/{id}/logs/{YYYY-MM-DD} | Remove a day (reverses its XP) | yes |
| POST | /habits/{id}/pause, /resume, /archive, /unarchive | State changes | yes |
| GET | /skills | All skills in roadmap order with status, XP, evidence, tier | yes |
| POST | /skills | Create (201) | yes |
| GET, PATCH | /skills/{id} | Detail with evidence, edit | yes |
| POST | /skills/{id}/archive | Archive (204) | yes |
| POST | /skills/{id}/prerequisites | Add `{prerequisite_id}`; 409 with cycle path if cyclic (201) | yes |
| DELETE | /skills/{id}/prerequisites/{pid} | Remove (204) | yes |
| POST | /skills/{id}/evidence | Add `{title, url?, notes?}` (201) | yes |
| DELETE | /skills/{id}/evidence/{eid} | Remove (204) | yes |
| GET | /analytics/summary | `from`, `to` (local dates, <= 366 days, default last 28) | yes |
| GET | /achievements | Gallery (hidden ones masked until unlocked) | yes |
| GET | /health | Liveness and DB check | no |
| GET | /openapi.json | This specification | no |

## Example: complete a quest
```http
POST /api/v1/quests/42/complete
Cookie: lifeexe_session=...
X-LifeExe-CSRF: 1
```
```json
{
  "quest": { "id": 42, "status": "COMPLETED", "xp_reward": 150, "allowed_actions": ["reopen"], "...": "..." },
  "reward": { "xp_awarded": 150, "base_xp": 150, "coins_awarded": 30, "capped": false, "daily_cap": 1500, "occurrence_key": "once" },
  "progress": { "level": 2, "total_xp": 150, "level_floor_xp": 100, "next_level_xp": 283, "xp_into_level": 50, "xp_span": 183, "xp_to_next_level": 133, "progress_ratio": 0.2732 },
  "level_before": 1,
  "leveled_up": true,
  "achievements_unlocked": [{ "key": "first_quest", "title": "First Quest Completed", "description": "Complete your first quest." }]
}
```
A second call returns `409 already_completed` and changes nothing.

## Not implemented
Endpoint groups from the brief for later milestones (`/goals`, `/study-sessions`, `/projects`, `/finance`, `/career`, `/settings` as a separate resource) do not exist yet; settings live under `/profile`.
