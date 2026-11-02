/** Auth API calls + session types. */

import { api } from "./api";
import type { UserOut } from "./types";

export type { UserOut };

export function me(): Promise<UserOut | null> {
  return api.get<UserOut>("/api/v1/auth/me").catch(() => null);
}

export function login(username: string, password: string): Promise<UserOut> {
  return api.post<UserOut>("/api/v1/auth/login", { username, password });
}

export function register(
  username: string,
  password: string,
  display_name?: string,
): Promise<UserOut> {
  return api.post<UserOut>("/api/v1/auth/register", {
    username,
    password,
    display_name: display_name || null,
  });
}

export function logout(): Promise<void> {
  return api.post<void>("/api/v1/auth/logout", {});
}
