// Hash router: #/quests, #/skills/12 … Works from any static host with no
// server-side rewrites (React Router was not installable; see ADR-004).
import { useSyncExternalStore } from "react";

export type Route =
  | { page: "command" }
  | { page: "quests" }
  | { page: "habits" }
  | { page: "skills"; skillId?: number }
  | { page: "analytics" }
  | { page: "achievements" }
  | { page: "settings" };

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  switch (parts[0]) {
    case "quests":
      return { page: "quests" };
    case "habits":
      return { page: "habits" };
    case "skills": {
      const id = Number(parts[1]);
      return Number.isInteger(id) && id > 0 ? { page: "skills", skillId: id } : { page: "skills" };
    }
    case "analytics":
      return { page: "analytics" };
    case "achievements":
      return { page: "achievements" };
    case "settings":
      return { page: "settings" };
    default:
      return { page: "command" };
  }
}

function subscribe(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash);
  return parseHash(hash);
}

export function navigate(path: string): void {
  window.location.hash = path;
}
