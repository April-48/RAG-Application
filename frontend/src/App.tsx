/**
 * Root app shell: routes + auth gate for private pages.
 *
 * Public routes: Home, Login, Signup.
 * Everything else (Dashboard, Chat, Profile) goes through ProtectedRoute,
 * which waits for auth to finish loading then redirects to /login if needed.
 */

import { type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Navbar from "./components/Navbar";
import { useAuth } from "./context/AuthContext";
import ChatPage from "./pages/ChatPage";
import DashboardPage from "./pages/DashboardPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import ProfilePage from "./pages/ProfilePage";
import SignupPage from "./pages/SignupPage";

/** Wrapper that blocks unauthenticated users from seeing protected pages. */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="glass px-6 py-4 text-sm text-slate-500">Loading…</div>
      </div>
    );
  }
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

/** Main layout with navbar and all app routes. */
export default function App() {
  return (
    <div className="app-shell font-sans">
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        {/* Anything unknown sends you back home instead of a random 404. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
