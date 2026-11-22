// A deliberately small data-fetching layer (TanStack Query was not installable;
// see ADR-004). Features: keyed cache shared between components, request
// de-duplication, prefix invalidation after mutations, loading/error state.
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { ApiError } from "./api";

interface Entry<T = unknown> {
  data?: T;
  error?: ApiError;
  promise?: Promise<void>;
  stale: boolean;
}

const cache = new Map<string, Entry>();
const listeners = new Set<() => void>();
let version = 0;

function notify() {
  version += 1;
  for (const l of listeners) l();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function load<T>(key: string, fetcher: () => Promise<T>): void {
  const entry = (cache.get(key) as Entry<T> | undefined) ?? { stale: true };
  if (entry.promise) return;
  entry.promise = fetcher()
    .then((data) => {
      entry.data = data;
      entry.error = undefined;
    })
    .catch((err: unknown) => {
      entry.error = err instanceof ApiError ? err : new ApiError(0, "client_error", String(err));
    })
    .finally(() => {
      entry.promise = undefined;
      entry.stale = false;
      notify();
    });
  cache.set(key, entry as Entry);
}

/** Mark every key starting with one of the prefixes stale; mounted queries refetch. */
export function invalidate(...prefixes: string[]): void {
  for (const [key, entry] of cache) if (prefixes.some((p) => key.startsWith(p))) entry.stale = true;
  notify();
}

export function clearCache(): void {
  cache.clear();
  notify();
}

export function useQuery<T>(key: string, fetcher: () => Promise<T>) {
  useSyncExternalStore(subscribe, () => version);
  const entry = cache.get(key) as Entry<T> | undefined;
  useEffect(() => {
    const e = cache.get(key);
    if (!e || (e.stale && !e.promise)) load(key, fetcher);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, entry?.stale]);
  const refetch = useCallback(() => invalidate(key), [key]);
  return {
    data: entry?.data,
    error: entry?.error,
    loading: !entry || (entry.data === undefined && entry.error === undefined),
    refreshing: Boolean(entry?.promise) && entry?.data !== undefined,
    refetch,
  };
}

export function useMutation<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setPending(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (err) {
        const e = err instanceof ApiError ? err : new ApiError(0, "client_error", String(err));
        setError(e);
        return undefined;
      } finally {
        setPending(false);
      }
    },
    [fn],
  );
  return { run, pending, error, reset: () => setError(null) };
}
