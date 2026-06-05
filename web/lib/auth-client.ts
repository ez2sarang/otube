"use client";

import { useState, useEffect } from "react";

interface AdminState {
  isAdmin: boolean;
  loading: boolean;
}

// Module-level cache so repeated hook calls don't re-fetch
let cachedState: AdminState | null = null;
let fetchPromise: Promise<AdminState> | null = null;

async function fetchAdminState(): Promise<AdminState> {
  if (fetchPromise) return fetchPromise;
  fetchPromise = fetch("/api/auth/me", { credentials: "same-origin" })
    .then((res) => res.json() as Promise<{ isAdmin: boolean }>)
    .then((data) => {
      cachedState = { isAdmin: data.isAdmin, loading: false };
      return cachedState;
    })
    .catch(() => {
      cachedState = { isAdmin: false, loading: false };
      return cachedState;
    })
    .finally(() => {
      fetchPromise = null;
    });
  return fetchPromise;
}

export function useAdmin(): AdminState {
  const [state, setState] = useState<AdminState>(
    cachedState ?? { isAdmin: false, loading: true }
  );

  useEffect(() => {
    if (cachedState) {
      setState(cachedState);
      return;
    }
    fetchAdminState().then(setState);
  }, []);

  return state;
}

/** Call after login/logout to force a re-check on next useAdmin() mount. */
export function invalidateAdminCache() {
  cachedState = null;
  fetchPromise = null;
}
