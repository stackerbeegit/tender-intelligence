import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/hooks/useAuth";
import { Login } from "@/pages/Login";
import { authService } from "@/services/authService";

vi.mock("@/services/authService", () => ({
  authService: {
    isAuthenticated: vi.fn(() => false),
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

describe("Login page", () => {
  beforeEach(() => {
    vi.mocked(authService.isAuthenticated).mockReturnValue(false);
  });

  it("renders the sign-in form when not authenticated", async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});
