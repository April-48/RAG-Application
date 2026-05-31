/**
 * Client-side signup validation and user-facing API error messages.
 */

import { ApiError } from "../api/client";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Run before submit. Returns an error message or null when the form is valid. */
export function validateSignupForm(
  email: string,
  password: string,
  confirmPassword?: string,
): string | null {
  const trimmedEmail = email.trim();
  if (!trimmedEmail || !EMAIL_RE.test(trimmedEmail)) {
    return "Please enter a valid email address.";
  }
  if (password.length < 8) {
    return "Password must be at least 8 characters.";
  }
  if (password.length > 128) {
    return "Password must be under 128 characters.";
  }
  if (confirmPassword !== undefined && password !== confirmPassword) {
    return "Passwords do not match.";
  }
  return null;
}

/** Map API/network failures to actionable signup messages (no raw backend details). */
export function mapSignupError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return "An account with this email already exists. Try logging in instead.";
    }
    if (err.status === 400 || err.status === 422) {
      return "Please check your email and password and try again.";
    }
    if (err.status >= 500) {
      return "Something went wrong. Please try again in a moment.";
    }
    if (err.status >= 400) {
      return "Please check your email and password and try again.";
    }
  }
  return "Something went wrong. Please try again in a moment.";
}
