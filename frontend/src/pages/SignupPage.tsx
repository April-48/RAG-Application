/**
 * Sign-up form — creates account then auto-logs in via AuthContext.signup().
 */

import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { mapSignupError, validateSignupForm } from "../utils/signupValidation";

/** Sign-up form that creates an account and logs you in. */
export default function SignupPage() {
  const { signup, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  /** Validate locally, sign up, then redirect to dashboard. */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validateSignupForm(email, password);
    if (validationError) {
      setError(validationError);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signup(email.trim(), password);
      navigate("/dashboard");
    } catch (err) {
      setError(mapSignupError(err));
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
          <h1 className="text-xl font-bold text-slate-900">Create account</h1>
          <p className="text-sm text-slate-500">Upload documents and chat with grounded AI answers</p>
        </div>

        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-600">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
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
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="glass-input"
          />
          <p className="mt-1.5 text-xs text-slate-400">8–128 characters.</p>
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-xl border border-red-200/80 bg-red-50/80 px-3 py-2 text-sm text-red-700 backdrop-blur-sm"
          >
            {error}
          </p>
        )}

        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? "Creating…" : "Sign up"}
        </button>

        <p className="text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-indigo-600 hover:text-indigo-500">
            Log in
          </Link>
        </p>
      </form>
    </div>
  );
}
