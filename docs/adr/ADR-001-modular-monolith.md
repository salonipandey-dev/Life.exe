# ADR-001: Modular monolith with a pure domain layer

- Status: Accepted (2026-11-22)

## Context
LIFE.EXE has many modules (quests, habits, skills, analytics, later finance, career, wellness) but one primary user and modest load. Distributed systems would add network failure modes, deployment work and cost with no benefit at this scale.

## Decision
One deployable backend, organised in layers with dependencies pointing inward:

```
api (HTTP, schemas, middleware) -> services (use cases, one transaction each) -> domain (pure rules)
                                         \-> repositories (SQL only)
```

`lifeexe.domain` performs no I/O, so every game rule (levels, rewards, quest transitions, streaks, skill graph) is unit-tested in milliseconds and can be explained without a database. The frontend never re-implements these rules; the API returns derived values such as `allowed_actions` and `progress`.

## Consequences
- Simple local run (`python -m lifeexe`), one process to deploy.
- Module boundaries are enforced by convention and review, not by the network. New modules (finance, career) get their own `domain/`, `repositories/`, `services/` and `api/routes/` files.
- Microservices, Redis and message brokers are explicitly out of scope until a measured need appears.
