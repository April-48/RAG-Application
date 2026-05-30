/**
 * Top navigation — only visible when logged in.
 * Home / Dashboard / Chat links on the left; account dropdown (Profile + Logout) on the right.
 */

import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

/** Top nav with page links and an account dropdown. */
export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;

    /** Close the menu when clicking outside it. */
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    /** Close the menu on Escape. */
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [menuOpen]);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  if (!isAuthenticated) return null;

  /** Log out and go to the login page. */
  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate("/login");
  };

  /** Go to the profile page. */
  const handleProfile = () => {
    setMenuOpen(false);
    navigate("/profile");
  };

  /** Pick active vs inactive styles for a nav link. */
  const linkClass = (path: string) =>
    location.pathname === path ? "nav-link-active" : "nav-link";

  return (
    <nav className="glass-nav sticky top-0 z-50">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-xs font-bold text-white shadow-md shadow-indigo-500/30">
              R
            </span>
            <span className="font-semibold tracking-tight text-slate-900">
              RAG Q&amp;A
            </span>
          </Link>
          <div className="flex gap-1">
            <Link to="/" className={linkClass("/")}>
              Home
            </Link>
            <Link to="/dashboard" className={linkClass("/dashboard")}>
              Dashboard
            </Link>
            <Link to="/chat" className={linkClass("/chat")}>
              Chat
            </Link>
          </div>
        </div>

        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label="Account menu"
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="inline-flex items-center gap-1 rounded-full border border-white/60 bg-white/40 px-3 py-1 text-xs text-slate-600 backdrop-blur-sm transition hover:bg-white/55"
          >
            <span className="max-w-[12rem] truncate">{user?.email}</span>
            <span aria-hidden="true" className="text-slate-400">
              ▾
            </span>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-full z-50 mt-2 min-w-[10rem] overflow-hidden rounded-xl border border-white/70 bg-white/95 py-1 shadow-lg shadow-indigo-500/10 backdrop-blur-md"
            >
              <button
                type="button"
                role="menuitem"
                onClick={handleProfile}
                className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 transition hover:bg-indigo-50/80"
              >
                Profile
              </button>
              <div className="my-1 border-t border-slate-100" role="separator" />
              <button
                type="button"
                role="menuitem"
                onClick={handleLogout}
                className="block w-full px-4 py-2.5 text-left text-sm text-red-600 transition hover:bg-red-50/80"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
