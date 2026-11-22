# ADR-002: Starlette + Pydantic with a small typed routing layer (instead of FastAPI)

- Status: Accepted (2026-11-22). Revisit when dependencies can be installed.

## Context
The brief recommends FastAPI. The build environment had no package-install access, and FastAPI, SQLAlchemy and Alembic were not installed. Starlette (the ASGI framework FastAPI is built on), Pydantic v2 and Uvicorn were.

## Decision
Use Starlette directly, plus `lifeexe/api/routing.py` (~250 lines) that provides the FastAPI features this project needs: Pydantic validation of bodies and query strings, response-model validation, consistent error JSON, cookie authentication, a CSRF check, per-route rate limits and OpenAPI 3.1 generation from the registered routes.

## Consequences
- Behaviour that FastAPI would hide is explicit and tested, which is useful for explaining the system in interviews.
- We own a little framework code. If FastAPI becomes available, migration is mechanical: route functions already take validated Pydantic models and return dicts validated by response models; domain, services and repositories are untouched.
- Handlers are synchronous and run in Starlette's threadpool because `sqlite3` is synchronous.
