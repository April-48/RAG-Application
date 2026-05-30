/**
 * Simple profile page — just shows the logged-in email for now.
 * Linked from the Navbar account dropdown.
 */

import { useAuth } from "../context/AuthContext";

/** Simple page showing the logged-in user's email. */
export default function ProfilePage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-lg animate-fade-in px-4 py-8">
      <header className="space-y-1">
        <h1 className="page-title">Profile</h1>
        <p className="page-subtitle">Your account information.</p>
      </header>

      <div className="glass-panel mt-6 p-5">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
          Email
        </p>
        <p className="mt-1 text-sm font-medium text-slate-800">{user?.email}</p>
      </div>
    </div>
  );
}
