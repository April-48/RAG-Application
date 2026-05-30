/**
 * Auth API wrappers — signup, login, and "who am I".
 * Login/signup don't send a JWT yet (auth: false); /me requires one.
 */

import type { User } from "../types/user";
import { apiRequest } from "./client";

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export const authApi = {
  /** Create a new user account. */
  signup: (email: string, password: string): Promise<User> =>
    apiRequest<User>("/auth/signup", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    }),

  /** Log in and get a JWT back. */
  login: (email: string, password: string): Promise<TokenResponse> =>
    apiRequest<TokenResponse>("/auth/login", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    }),

  /** Fetch the current user from a saved token. */
  me: (): Promise<User> => apiRequest<User>("/auth/me"),
};
