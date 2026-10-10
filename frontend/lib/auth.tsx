"use client";

/**
 * Authentication context.
 *
 * The bearer token lives in localStorage (the API is cross-origin and uses an
 * Authorization header). A same-site cookie mirrors the token only so the edge
 * middleware can redirect unauthenticated page loads; it grants no API access.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api, AUTH_EVENT, TOKEN_KEY, USER_KEY, type LoginResult } from "./api-client";
import { decodeTokenClaims, isAdminRole, isManagerRole, isTokenExpired } from "./session";
import type { SessionUser, User } from "@/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: SessionUser | User | null;
  status: AuthStatus;
  isManager: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  setSession: (result: Pick<LoginResult, "access_token" | "user">) => void;
  logout: (reason?: "expired") => void;
  refreshProfile: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function writeCookie(token: string | null) {
  if (typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  if (!token) {
    document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax${secure}`;
    return;
  }
  const exp = decodeTokenClaims(token)?.exp;
  const maxAge = exp ? Math.max(0, Math.floor(exp - Date.now() / 1000)) : 3600;
  document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${maxAge}; SameSite=Lax${secure}`;
}

function clearStorage() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  writeCookie(null);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [user, setUser] = useState<SessionUser | User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const logout = useCallback(
    (reason?: "expired") => {
      api.auth.logout().catch(() => undefined);
      clearStorage();
      queryClient.clear();
      setUser(null);
      setStatus("anonymous");
      router.replace(reason === "expired" ? "/login?expired=1" : "/login");
    },
    [queryClient, router],
  );

  // Restore the session once on mount.
  useEffect(() => {
    const token = window.localStorage.getItem(TOKEN_KEY);
    const saved = window.localStorage.getItem(USER_KEY);
    if (!token || !saved || isTokenExpired(token)) {
      if (token) clearStorage();
      setStatus("anonymous");
      return;
    }
    try {
      setUser(JSON.parse(saved) as SessionUser);
      writeCookie(token);
      setStatus("authenticated");
    } catch {
      clearStorage();
      setStatus("anonymous");
    }
  }, []);

  // Any 401 from the API ends the session.
  useEffect(() => {
    const onExpired = () => logout("expired");
    window.addEventListener(AUTH_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EVENT, onExpired);
  }, [logout]);

  // Sign out at the moment the token expires, not on the next failed request.
  useEffect(() => {
    if (status !== "authenticated") return;
    const exp = decodeTokenClaims(window.localStorage.getItem(TOKEN_KEY))?.exp;
    if (!exp) return;
    const delay = Math.min(exp * 1000 - Date.now(), 2 ** 31 - 1);
    const timer = window.setTimeout(() => logout("expired"), Math.max(delay, 0));
    return () => window.clearTimeout(timer);
  }, [status, logout]);

  const setSession = useCallback<AuthContextValue["setSession"]>(
    ({ access_token, user: sessionUser }) => {
      window.localStorage.setItem(TOKEN_KEY, access_token);
      window.localStorage.setItem(USER_KEY, JSON.stringify(sessionUser));
      writeCookie(access_token);
      queryClient.clear();
      setUser(sessionUser);
      setStatus("authenticated");
      router.replace("/");
    },
    [queryClient, router],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await api.auth.login(email, password);
      setSession(result);
    },
    [setSession],
  );

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await api.auth.me();
      window.localStorage.setItem(USER_KEY, JSON.stringify(profile));
      setUser(profile);
      return profile;
    } catch {
      return null;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isManager: isManagerRole(user?.role),
      isAdmin: isAdminRole(user?.role),
      login,
      setSession,
      logout,
      refreshProfile,
    }),
    [user, status, login, setSession, logout, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
