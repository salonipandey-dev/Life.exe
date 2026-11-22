from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from lifeexe.core.db import Connection, Database, is_unique_violation
from lifeexe.core.errors import Conflict, Unauthorized
from lifeexe.core.security import (
    DUMMY_HASH,
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from lifeexe.core.timeutil import Clock, from_iso, to_iso
from lifeexe.domain.character import AVATARS, TITLES
from lifeexe.repositories import users as users_repo
from lifeexe.services.seed import seed_default_skills


@dataclass(frozen=True)
class SessionIssued:
    user_id: int
    token: str
    expires_at: str


class AuthService:
    def __init__(self, db: Database, clock: Clock, session_ttl_hours: int) -> None:
        self.db = db
        self.clock = clock
        self.ttl = timedelta(hours=session_ttl_hours)

    def register(self, email: str, password: str, display_name: str, timezone: str) -> SessionIssued:
        now = self.clock.now()
        password_hash = hash_password(password)  # slow KDF outside the write lock
        try:
            with self.db.transaction() as conn:
                user_id = users_repo.create_user(conn, email, password_hash, to_iso(now))
                users_repo.create_profile(conn, user_id, display_name, TITLES[0][1], AVATARS[0], timezone, to_iso(now))
                seed_default_skills(conn, user_id, to_iso(now))
                return self._issue(conn, user_id)
        except Exception as exc:
            if is_unique_violation(exc):
                raise Conflict("An account with this email already exists.") from None
            raise

    def login(self, email: str, password: str) -> SessionIssued:
        with self.db.transaction(write=False) as conn:
            user = users_repo.get_user_by_email(conn, email)
        stored = user["password_hash"] if user else DUMMY_HASH
        valid = verify_password(password, stored)  # always runs: no timing oracle
        if user is None or not valid:
            raise Unauthorized("Email or password is incorrect.")
        with self.db.transaction() as conn:
            if needs_rehash(stored):
                users_repo.update_password(conn, user["id"], hash_password(password), to_iso(self.clock.now()))
            return self._issue(conn, int(user["id"]))

    def logout(self, token: str) -> None:
        with self.db.transaction() as conn:
            users_repo.delete_session(conn, hash_token(token))

    def authenticate(self, token: str | None) -> int | None:
        if not token or len(token) > 200:
            return None
        now = self.clock.now()
        with self.db.transaction(write=False) as conn:
            session = users_repo.get_session(conn, hash_token(token))
        if session is None:
            return None
        if from_iso(session["expires_at"]) <= now:
            with self.db.transaction() as conn:
                users_repo.delete_session(conn, hash_token(token))
            return None
        return int(session["user_id"])

    def _issue(self, conn: Connection, user_id: int) -> SessionIssued:
        now = self.clock.now()
        token = new_session_token()
        expires = to_iso(now + self.ttl)
        users_repo.purge_expired_sessions(conn, to_iso(now))
        users_repo.create_session(conn, user_id, hash_token(token), to_iso(now), expires)
        return SessionIssued(user_id=user_id, token=token, expires_at=expires)
