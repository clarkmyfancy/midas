"use client";

import type {
  AuthLoginRequest,
  AuthRegisterRequest,
  AuthUserResponse,
} from "@midas/types";
import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearAuthSession,
  getBrowserStorage,
  loadAuthSession,
  saveAuthSession,
  type AuthSession,
} from "../lib/auth-session";
import { getCurrentUser, loginWithApi, registerWithApi } from "../lib/auth-api";

type AuthContextValue = {
  isReady: boolean;
  session: AuthSession | null;
  user: AuthUserResponse | null;
  login: (payload: AuthLoginRequest) => Promise<AuthSession>;
  register: (payload: AuthRegisterRequest) => Promise<AuthSession>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const storage = getBrowserStorage();
    const storedSession = loadAuthSession(storage);

    if (!storedSession) {
      setIsReady(true);
      return;
    }

    let cancelled = false;

    void getCurrentUser(storedSession.accessToken)
      .then((user) => {
        if (cancelled) {
          return;
        }

        const nextSession = { ...storedSession, user };
        saveAuthSession(storage, nextSession);
        startTransition(() => setSession(nextSession));
      })
      .catch(() => {
        if (cancelled) {
          return;
        }

        clearAuthSession(storage);
        startTransition(() => setSession(null));
      })
      .finally(() => {
        if (!cancelled) {
          setIsReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function persistSession(nextSession: AuthSession) {
    const storage = getBrowserStorage();
    saveAuthSession(storage, nextSession);
    startTransition(() => setSession(nextSession));
    return nextSession;
  }

  async function login(payload: AuthLoginRequest) {
    const nextSession = await loginWithApi(payload);
    return persistSession(nextSession);
  }

  async function register(payload: AuthRegisterRequest) {
    const nextSession = await registerWithApi(payload);
    return persistSession(nextSession);
  }

  function logout() {
    const storage = getBrowserStorage();
    clearAuthSession(storage);
    startTransition(() => setSession(null));
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      isReady,
      session,
      user: session?.user ?? null,
      login,
      register,
      logout,
    }),
    [isReady, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
