/**
 * Login form — redirects to /dashboard if you're already authenticated.
 */

import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

/** Login form — redirects away if you're already signed in. */
export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  /** Log in and send the user to the dashboard. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-[85vh] animate-fade-in items-center justify-center px-4 py-12">
      <form onSubmit={handleSubmit} className="glass w-full max-w-md space-y-5 p-8">
        <div className="space-y-1 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-lg font-bold text-white shadow-lg shadow-indigo-500/30">
            R
          </div>
          <h1 className="text-xl font-bold text-slate-900">Welcome back</h1>
          <p className="text-sm text-slate-500">Sign in to ask questions about your documents</p>
        </div>

        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-600">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="glass-input"
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-600">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="glass-input"
          />
        </div>

        {error && (
          <p className="rounded-xl border border-red-200/80 bg-red-50/80 px-3 py-2 text-sm text-red-700 backdrop-blur-sm">
            {error}
          </p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? "Logging in…" : "Log in"}
        </button>

        <p className="text-center text-sm text-slate-500">
          No account?{" "}
          <Link to="/signup" className="font-semibold text-indigo-600 hover:text-indigo-500">
            Sign up
          </Link>
        </p>
      </form>
    </div>
  );
}
