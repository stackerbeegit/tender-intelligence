import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import BusinessOutlinedIcon from "@mui/icons-material/BusinessOutlined";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import RadarIcon from "@mui/icons-material/Radar";
import {
  AppBar,
  Avatar,
  Box,
  Drawer,
  IconButton,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { type ReactNode, useState } from "react";
import { Link as RouterLink, matchPath, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { brand } from "@/theme";
import { initials } from "@/utils/format";

const SIDEBAR_WIDTH = 248;

const NAV_LINKS: { to: string; label: string; icon: ReactNode; roles?: string[]; exact?: boolean }[] = [
  { to: "/", label: "Dashboard", icon: <DashboardOutlinedIcon />, exact: true },
  { to: "/tenders", label: "Tenders", icon: <DescriptionOutlinedIcon /> },
  { to: "/tenders/new", label: "Add Tender", icon: <AddCircleOutlineIcon />, exact: true },
  { to: "/profile", label: "Company Profile", icon: <BusinessOutlinedIcon /> },
  { to: "/sources", label: "Sources", icon: <HubOutlinedIcon />, roles: ["admin", "technical"] },
];

function isActive(pathname: string, to: string, exact?: boolean): boolean {
  if (exact) return pathname === to;
  // "/tenders" stays highlighted on a tender's detail page, but not on "Add Tender".
  return Boolean(matchPath({ path: `${to}/*` }, pathname)) && pathname !== "/tenders/new";
}

function Brand() {
  return (
    <Stack direction="row" spacing={1.5} alignItems="center" px={2.5} py={3}>
      <Box
        sx={{
          width: 38,
          height: 38,
          borderRadius: 2.5,
          background: brand.gradient,
          display: "grid",
          placeItems: "center",
          boxShadow: "0 6px 18px rgba(124,58,237,0.45)",
        }}
      >
        <RadarIcon sx={{ color: "#fff", fontSize: 22 }} />
      </Box>
      <Box>
        <Typography fontWeight={800} color="#fff" lineHeight={1.1}>
          Stackerbee
        </Typography>
        <Typography variant="caption" sx={{ color: alpha("#fff", 0.6) }}>
          Tender Intelligence
        </Typography>
      </Box>
    </Stack>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <Stack height="100%" sx={{ background: brand.sidebarGradient, color: "#fff" }}>
      <Brand />
      <Typography variant="overline" sx={{ px: 3, color: alpha("#fff", 0.4), fontSize: "0.65rem" }}>
        Workspace
      </Typography>
      <Stack component="nav" spacing={0.5} px={1.5} mt={0.5} flexGrow={1}>
        {NAV_LINKS.filter((link) => !link.roles || (user && link.roles.includes(user.role.name))).map((link) => {
          const active = isActive(pathname, link.to, link.exact);
          return (
            <Box
              key={link.to}
              component={RouterLink}
              to={link.to}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1.5,
                px: 1.5,
                py: 1.1,
                borderRadius: 2.5,
                color: active ? "#fff" : alpha("#fff", 0.68),
                textDecoration: "none",
                fontSize: "0.9rem",
                fontWeight: active ? 700 : 500,
                position: "relative",
                bgcolor: active ? alpha("#fff", 0.12) : "transparent",
                transition: "background-color 120ms, color 120ms",
                "&:hover": { bgcolor: alpha("#fff", 0.08), color: "#fff" },
                "& svg": { fontSize: 20, color: active ? "#C4B5FD" : "inherit" },
                ...(active && {
                  "&::before": {
                    content: '""',
                    position: "absolute",
                    left: -12,
                    top: 8,
                    bottom: 8,
                    width: 4,
                    borderRadius: 2,
                    background: brand.gradient,
                  },
                }),
              }}
            >
              {link.icon}
              {link.label}
            </Box>
          );
        })}
      </Stack>

      {user && (
        <Stack
          direction="row"
          alignItems="center"
          spacing={1.5}
          m={1.5}
          p={1.5}
          borderRadius={3}
          sx={{ bgcolor: alpha("#fff", 0.06), border: `1px solid ${alpha("#fff", 0.08)}` }}
        >
          <Avatar sx={{ width: 36, height: 36, background: brand.gradient, fontSize: "0.85rem", fontWeight: 700 }}>
            {initials(user.full_name)}
          </Avatar>
          <Box minWidth={0} flexGrow={1}>
            <Typography variant="body2" fontWeight={700} noWrap>
              {user.full_name}
            </Typography>
            <Typography variant="caption" sx={{ color: alpha("#fff", 0.55), textTransform: "capitalize" }} noWrap>
              {user.role.name.replace("_", " ")}
            </Typography>
          </Box>
          <Tooltip title="Log out">
            <IconButton size="small" onClick={handleLogout} aria-label="log out" sx={{ color: alpha("#fff", 0.7) }}>
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      )}
    </Stack>
  );
}

export function AppLayout({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <Box display="flex" minHeight="100vh" bgcolor="background.default">
      {isDesktop ? (
        <Box component="aside" sx={{ width: SIDEBAR_WIDTH, flexShrink: 0, background: brand.sidebarGradient }}>
          <Box sx={{ position: "sticky", top: 0, height: "100vh" }}>
            <SidebarContent />
          </Box>
        </Box>
      ) : (
        <>
          <AppBar position="fixed" elevation={0} sx={{ background: brand.sidebarGradient }}>
            <Toolbar>
              <IconButton color="inherit" edge="start" onClick={() => setMobileOpen(true)} aria-label="open menu">
                <MenuIcon />
              </IconButton>
              <Typography fontWeight={800} ml={1}>
                Stackerbee Tender Intelligence
              </Typography>
            </Toolbar>
          </AppBar>
          <Drawer
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            PaperProps={{ sx: { width: SIDEBAR_WIDTH, border: 0 } }}
          >
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </Drawer>
        </>
      )}

      <Box component="main" flexGrow={1} minWidth={0} px={{ xs: 2, md: 4 }} pt={{ xs: 10, md: 4 }} pb={6}>
        <Box maxWidth={1440} mx="auto">
          {children}
        </Box>
      </Box>
    </Box>
  );
}
