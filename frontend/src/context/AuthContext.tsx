/**
 * Global auth state for the React app.
 *
 * On first load we check localStorage for a JWT and call /auth/me if it exists.
 * Login/signup store the token; logout clears it. Pages use useAuth() instead of
 * touching localStorage directly.
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { authApi } from "../api/authApi";
import { tokenStorage } from "../api/client";
import type { User } from "../types/user";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Provides login state and auth actions to the whole app. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Try to restore session from a saved token (page refresh case).
  useEffect(() => {
    /** Try to restore the session from a token saved in localStorage. */
    const restore = async () => {
      if (tokenStorage.get()) {
        try {
          setUser(await authApi.me());
        } catch {
          // Token expired or invalid — wipe it so we don't retry forever.
          tokenStorage.clear();
        }
      }
      setLoading(false);
    };
    void restore();
  }, []);

  /** Log in, save the token, and load the current user. */
  const login = async (email: string, password: string) => {
    const token = await authApi.login(email, password);
    tokenStorage.set(token.access_token);
    setUser(await authApi.me());
  };

  /** Sign up then log in so the user lands on the dashboard ready to go. */
  const signup = async (email: string, password: string) => {
    await authApi.signup(email, password);
    // Signup doesn't return a token in our API, so log them in right after.
    await login(email, password);
  };

  /** Clear the token and drop the user back to logged-out state. */
  const logout = () => {
    tokenStorage.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: Boolean(user),
        login,
        signup,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
/** Read auth state — must be used inside AuthProvider. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
