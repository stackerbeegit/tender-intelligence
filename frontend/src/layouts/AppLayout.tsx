import LogoutIcon from "@mui/icons-material/Logout";
import { AppBar, Box, Chip, IconButton, Toolbar, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <Box minHeight="100vh" bgcolor="background.default">
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 600 }}>
            Stackerbee Tender Intelligence
          </Typography>
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
