/**
 * Thin wrapper around localStorage for JWT storage. Isolated here so that
 * if we later move to httpOnly cookies (preferable for XSS resistance once
 * a same-site backend is in place), only this file changes.
 */
const ACCESS_TOKEN_KEY = "stackerbee_access_token";
const REFRESH_TOKEN_KEY = "stackerbee_refresh_token";

export const tokenStorage = {
  getAccessToken: (): string | null => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clear: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};
