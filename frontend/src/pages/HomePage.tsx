/**
 * Landing page — short intro + how-it-works steps.
 * CTAs change depending on whether you're logged in (Dashboard/Chat vs Sign up/Log in).
 */

import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const STEPS = [
  "Upload a document",
  "The system extracts, chunks, and indexes the content",
  "Ask questions about one selected document",
  "View answers with source citations",
];

/** Landing page with intro text and how-it-works steps. */
export default function HomePage() {
  const { isAuthenticated, loading } = useAuth();

  return (
    <div className="mx-auto max-w-3xl animate-fade-in px-4 py-12 sm:py-16">
      <section className="glass-panel space-y-6 p-8 text-center sm:p-10">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Ask questions grounded in your documents
        </h1>
        <p className="mx-auto max-w-xl text-sm leading-relaxed text-slate-600 sm:text-base">
          Upload PDF, TXT, or DOCX files and get AI-generated answers with source
          snippets from your own documents.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          {loading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : isAuthenticated ? (
            <>
              <Link to="/dashboard" className="btn-primary">
                Go to Dashboard
              </Link>
              <Link
                to="/chat"
                className="rounded-xl border border-white/60 bg-white/50 px-4 py-2.5 text-sm font-medium text-indigo-700 backdrop-blur-sm transition hover:bg-white/70"
              >
                Start Chatting
              </Link>
            </>
          ) : (
            <>
              <Link to="/signup" className="btn-primary">
                Sign Up
              </Link>
              <Link
                to="/login"
                className="rounded-xl border border-white/60 bg-white/50 px-4 py-2.5 text-sm font-medium text-indigo-700 backdrop-blur-sm transition hover:bg-white/70"
              >
                Log In
              </Link>
            </>
          )}
        </div>
      </section>

      <section className="mt-8 glass-panel p-8 sm:p-10">
        <h2 className="mb-5 text-sm font-semibold uppercase tracking-wider text-slate-500">
          How it works
        </h2>
        <ol className="space-y-4">
          {STEPS.map((step, index) => (
            <li key={step} className="flex gap-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                {index + 1}
              </span>
              <p className="pt-0.5 text-sm leading-relaxed text-slate-700">{step}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
