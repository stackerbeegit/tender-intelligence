import { api } from "./api";
import { tokenStorage } from "./tokenStorage";
import type { LoginRequest, TokenResponse, User } from "@/types/auth";

export const authService = {
  async login(credentials: LoginRequest): Promise<User> {
    const { data } = await api.post<TokenResponse>("/auth/login", credentials);
    tokenStorage.setTokens(data.access_token, data.refresh_token);
    return authService.me();
  },

  async me(): Promise<User> {
    const { data } = await api.get<User>("/auth/me");
    return data;
  },

  logout(): void {
    tokenStorage.clear();
  },

  isAuthenticated(): boolean {
    return tokenStorage.getAccessToken() !== null;
  },
};
