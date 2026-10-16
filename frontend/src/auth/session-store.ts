import { useSyncExternalStore } from "react";
import type { MeOut } from "../services/identity";

interface SessionSnapshot {
  me: MeOut | null;
  companyId: string | null;
  status: "unknown" | "authenticating" | "authenticated" | "guest";
}

let snapshot: SessionSnapshot = { me: null, companyId: null, status: "unknown" };
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function setSession(next: Partial<SessionSnapshot>) {
  snapshot = { ...snapshot, ...next };
  emit();
}

export function getSession(): SessionSnapshot {
  return snapshot;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSession(): SessionSnapshot {
  return useSyncExternalStore(subscribe, getSession, getSession);
}
