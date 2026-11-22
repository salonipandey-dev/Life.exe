# ADR-006: Server-side opaque sessions in HttpOnly cookies, custom-header CSRF defence

- Status: Accepted (2026-11-22)

## Context
The browser app and API are served from the same origin. Options were JWTs (stateless, hard to revoke) or opaque server sessions.

## Decision
- Login issues a 256-bit random token in an `HttpOnly; SameSite=Lax` cookie (`Secure` in production). Only the token's SHA-256 is stored, so a database leak does not yield usable sessions.
- Logout and password changes revoke sessions server-side; sessions expire after 14 days.
- Passwords use scrypt (n=2^14, r=8, p=1) with per-password salts; unknown emails are checked against a dummy hash so timing does not reveal which accounts exist.
- State-changing requests must carry `X-LifeExe-CSRF: 1` and, if present, a same-origin `Origin` header. Browsers cannot add custom headers cross-site without a CORS preflight, which the API never approves.

## Consequences
- Revocation is immediate and simple. Each authenticated request costs one indexed lookup.
- The rate limiter is in-process; a multi-process deployment needs a shared store (technical-debt register).
