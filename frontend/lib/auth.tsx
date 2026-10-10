"use client";

/**
 * Authentication Context and State Management
 */

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User } from "@/types";
import { api } from "./api-client";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  setSession: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  useEffect(() => {
    // Restore session from localStorage
    const savedToken = localStorage.getItem("orbit_token");
    const savedUser = localStorage.getItem("orbit_user");

    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
        document.cookie = `orbit_token=${savedToken}; path=/; max-age=86400`;
      } catch {
        localStorage.removeItem("orbit_token");
        localStorage.removeItem("orbit_user");
        document.cookie = "orbit_token=; path=/; max-age=0";
      }
    } else if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      router.push("/login");
    }
    setIsLoading(false);
  }, [router]);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const data = await api.auth.login(email, password);
      localStorage.setItem("orbit_token", data.access_token);
      localStorage.setItem("orbit_user", JSON.stringify(data.user));
      document.cookie = `orbit_token=${data.access_token}; path=/; max-age=86400`;
      setToken(data.access_token);
      setUser(data.user);
      router.push("/");
    } catch (err) {
      setIsLoading(false);
      throw err; // Re-throw so login page can display the error
    }
    setIsLoading(false);
  };

  const setSession = (token: string, user: User) => {
    localStorage.setItem("orbit_token", token);
    localStorage.setItem("orbit_user", JSON.stringify(user));
    document.cookie = `orbit_token=${token}; path=/; max-age=86400`;
    setToken(token);
    setUser(user);
    router.push("/");
  };

  const logout = () => {
    try {
      api.auth.logout().catch(() => {});
    } catch {}
    localStorage.removeItem("orbit_token");
    localStorage.removeItem("orbit_user");
    document.cookie = "orbit_token=; path=/; max-age=0";
    setToken(null);
    setUser(null);
    router.push("/login");
  };

  const refreshUser = async () => {
    try {
      const updatedUser = await api.auth.me();
      localStorage.setItem("orbit_user", JSON.stringify(updatedUser));
      setUser(updatedUser);
    } catch (err) {
      console.error("Failed to refresh user profile", err);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        setSession,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
