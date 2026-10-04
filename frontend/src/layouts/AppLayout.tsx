import LogoutIcon from "@mui/icons-material/Logout";
import { AppBar, Box, Chip, IconButton, Stack, Toolbar, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { Link as RouterLink, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

const NAV_LINKS: { to: string; label: string; roles?: string[] }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/tenders", label: "Tenders" },
  { to: "/sources", label: "Sources", roles: ["admin", "technical"] },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <Box minHeight="100vh" bgcolor="background.default">
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Stackerbee Tender Intelligence
          </Typography>

          <Stack direction="row" spacing={0.5} sx={{ flexGrow: 1, ml: 2 }}>
            {NAV_LINKS.filter((link) => !link.roles || (user && link.roles.includes(user.role.name))).map((link) => (
              <Box
                key={link.to}
                component={RouterLink}
                to={link.to}
                sx={{
                  color: "inherit",
                  textDecoration: "none",
                  px: 1.5,
                  py: 0.75,
                  borderRadius: 1,
                  fontSize: "0.875rem",
                  fontWeight: location.pathname === link.to ? 700 : 400,
                  bgcolor: location.pathname === link.to ? "rgba(255,255,255,0.15)" : "transparent",
                }}
              >
                {link.label}
              </Box>
            ))}
          </Stack>

          {user && (
            <>
              <Typography variant="body2">{user.full_name}</Typography>
              <Chip label={user.role.name} size="small" color="secondary" />
              <IconButton color="inherit" onClick={handleLogout} aria-label="log out">
                <LogoutIcon />
              </IconButton>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Box component="main" p={{ xs: 2, md: 4 }}>
        {children}
      </Box>
    </Box>
  );
}
