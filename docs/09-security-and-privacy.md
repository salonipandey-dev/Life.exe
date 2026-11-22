# 09 Security and privacy design

## 1. Assets and threats
| Asset | Threats considered |
|---|---|
| Account credentials | Credential stuffing, brute force, hash theft, user enumeration |
| Session | Theft via XSS, CSRF, replay after logout |
| Personal records (quests, habits, skills; later finance and wellness) | Cross-user access (IDOR), injection, over-logging, export leaks |
| Progression integrity | Duplicate rewards, client-forged XP, race conditions |

## 2. Controls (implemented and tested)
| Area | Control | Where | Test |
|---|---|---|---|
| Passwords | scrypt n=2^14 r=8 p=1, 16-byte salt, constant-time compare, rehash on parameter upgrade, length 10-128 | `core/security.py` | test_password_hash_roundtrip, test_malformed_hashes_fail_closed, test_needs_rehash_on_weaker_params |
| Enumeration | Same 401 message for unknown email and wrong password; dummy hash verified for unknown emails | `services/auth.py` | test_login_logout_and_generic_errors |
| Brute force | Per-IP sliding-window limit on register, login, password change, account deletion → 429 + Retry-After | `core/ratelimit.py` | test_login_rate_limited |
| Sessions | 256-bit opaque token; only SHA-256 stored; HttpOnly, SameSite=Lax, Secure in production; 14-day expiry; logout and password change revoke server-side | `services/auth.py`, `api/routing.py` | test_register_sets_secure_session_cookie, test_session_expiry, test_change_password_revokes_other_sessions |
| CSRF | Required `X-LifeExe-CSRF` header and same-origin `Origin` on state-changing requests | `api/routing._check_csrf` | test_csrf_protections |
| Authorization | Every repository query filters by `user_id`; foreign ids → 404; composite FKs make cross-user links impossible in the schema | repositories, migrations | test_user_isolation.py, test_composite_fk_blocks_cross_user_links |
| Input validation | Pydantic models with `extra="forbid"`, length and range limits, enum values, URL scheme check (http/https only), 64 KiB body cap, JSON content type | `api/schemas.py`, `api/routing.py` | test_registration_validation, test_content_type_size_and_json_validation, test_client_cannot_supply_xp_or_coins |
| Injection | Parameterised SQL; dynamic SQL only from code whitelists (columns, sort keys, export tables); LIKE wildcards escaped | repositories | test_sql_injection_payloads_are_inert, test_list_filter_search_sort_paginate |
| XSS | React escapes output; strict CSP `default-src 'self'` with no inline scripts or styles; evidence links rendered with `rel="noopener noreferrer"` | `api/middleware.py` | test_security_headers_and_error_shape |
| Headers | CSP, X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy no-referrer, Permissions-Policy, COOP, HSTS when secure cookies are on, `Cache-Control: no-store` on API | `api/middleware.py` | test_security_headers_and_error_shape |
| Errors | Generic 500 body; stack traces only in server logs | `main.py` | test_failed_transaction_leaves_no_partial_rows |
| Logging | Structured JSON: method, path, status, duration, request id; no bodies, cookies or query strings; sensitive keys redacted | `core/logging.py`, middleware | code review |
| Reward abuse | Server-side rewards only, idempotency keys, unique indexes, serialised writes, daily cap | services, schema | test_concurrency.py |
| Secrets | No secrets in code; configuration from environment; `.env` git-ignored; `.env.example` documents keys | `core/config.py` | repository review |
| Least privilege | Container runs as a non-root user; the app needs only read/write on its data file. On PostgreSQL, use a role with DML rights on the app schema only and a separate migration role | `docker/Dockerfile`, deployment guide | not executed (Docker not built here) |

## 3. Privacy design
- **Data minimisation:** email, display name, time zone and the user's own records. No analytics trackers, no third-party scripts or fonts (fonts are self-hosted), no IP addresses stored.
- **Purpose limitation:** data is used only to run the user's own account.
- **User control:** full JSON export (`/account/export`, excludes password and token hashes) and permanent deletion (`/account/delete`, cascades through every table; verified per table).
- **No AI or third-party processing:** nothing leaves the server. Future AI features must be opt-in per feature, show what is sent, and exclude finance, wellness and journal data unless explicitly allowed.
- **Sensitive future modules** (finance, wellness) will be optional, separately exportable and deletable.

## 4. Known gaps
- In-process rate limiter (single process only).
- No account lockout notifications, email verification or password reset (no email service).
- No MFA.
- No automated dependency vulnerability scan in CI yet (add `pip-audit` / `npm audit`).
- Security review of the deployed environment (TLS configuration, proxy headers) pending deployment.
