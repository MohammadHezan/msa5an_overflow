import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { BookingPayload, configuredApiUrl, Student } from './api';

const STORAGE_KEY = 'campus-connect/session/v1';

/**
 * What the phone remembers between launches.
 * - `token` is the student bearer token from the join code.
 * - `clientRequestId` is created once per session and reused for every booking attempt,
 *   so a retry after a lost response returns the same rider instead of booking twice.
 * - `sentPayload` is the last booking sent while the outcome was unknown; it lets the
 *   student resend exactly those details if the server already saved them.
 * - `verified`/`student` record a confirmed university email; `verification` is a code that was
 *   sent but not yet confirmed, so reopening the app returns to the code screen.
 */
export type PendingVerification = {
  universityId: number;
  universityName: string;
  maskedEmail: string;
  expiresAt: string;
  resendAvailableAt: string;
};

export type Session = {
  apiUrl: string;
  token: string;
  batchId: string;
  tripDate: string;
  clientRequestId: string;
  riderId: number | null;
  sentPayload: BookingPayload | null;
  verified: boolean;
  student: Student | null;
  verification: PendingVerification | null;
};

type SessionContextValue = {
  apiUrl: string | null;
  session: Session | null;
  loaded: boolean;
  save: (session: Session) => Promise<void>;
  update: (changes: Partial<Session>) => Promise<void>;
  clear: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const apiUrl = configuredApiUrl();
  const [session, setSession] = useState<Session | null>(null);
  const [loaded, setLoaded] = useState<boolean>(false);
  // Latest saved session, so consecutive updates inside one async flow never merge into a stale copy.
  const current = useRef<Session | null>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (cancelled || !raw) return;
        const parsed = JSON.parse(raw) as Partial<Session>;
        // Sessions saved before verification existed have no verification fields.
        const stored = {
          ...parsed,
          verified: parsed.verified ?? false,
          student: parsed.student ?? null,
          verification: parsed.verification ?? null,
        } as Session;
        // A session belongs to one backend; drop it if the app now points somewhere else.
        if (stored.apiUrl === apiUrl) {
          current.current = stored;
          setSession(stored);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  const save = useCallback(async (next: Session) => {
    current.current = next;
    setSession(next);
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const update = useCallback(
    async (changes: Partial<Session>) => {
      if (!current.current) return;
      await save({ ...current.current, ...changes });
    },
    [save],
  );

  const clear = useCallback(async () => {
    current.current = null;
    setSession(null);
    await AsyncStorage.removeItem(STORAGE_KEY);
  }, []);

  const value = useMemo(() => ({ apiUrl, session, loaded, save, update, clear }), [apiUrl, session, loaded, save, update, clear]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}
