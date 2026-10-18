import { alpha, createTheme } from "@mui/material/styles";

/**
 * Stackerbee app theme. Every color downstream comes from this palette (or
 * `brand` below) — pages never hardcode hex values.
 */
const ink = { 900: "#0F172A", 700: "#334155", 500: "#64748B", 300: "#CBD5E1", 200: "#E2E8F0", 100: "#F1F5F9" };

export const brand = {
  /** Sidebar + hero banner. */
  navy: "#0B1437",
  gradient: "linear-gradient(135deg, #4F46E5 0%, #7C3AED 55%, #A855F7 100%)",
  sidebarGradient: "linear-gradient(180deg, #0B1437 0%, #161E54 100%)",
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#4F46E5", light: "#818CF8", dark: "#3730A3", contrastText: "#FFFFFF" },
    secondary: { main: "#F59E0B", contrastText: "#1F1300" },
    success: { main: "#059669" },
    warning: { main: "#D97706" },
    error: { main: "#DC2626" },
    info: { main: "#0284C7" },
    background: { default: "#F4F6FB", paper: "#FFFFFF" },
    text: { primary: ink[900], secondary: ink[500] },
    divider: ink[200],
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: ['"Inter"', "Roboto", "Helvetica", "Arial", "sans-serif"].join(","),
    h4: { fontWeight: 700, letterSpacing: "-0.02em" },
    h5: { fontWeight: 700, letterSpacing: "-0.01em" },
    h6: { fontWeight: 600 },
    subtitle1: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
    overline: { fontWeight: 700, letterSpacing: "0.08em" },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        outlined: { borderColor: ink[200], boxShadow: "0 1px 2px rgba(15,23,42,0.04), 0 4px 16px rgba(15,23,42,0.04)" },
      },
    },
    MuiCard: {
      defaultProps: { variant: "outlined" },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 10, paddingInline: 16 },
        containedPrimary: { boxShadow: `0 4px 14px ${alpha("#4F46E5", 0.3)}` },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, borderRadius: 8 },
        sizeSmall: { fontSize: "0.72rem" },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-head": {
            backgroundColor: ink[100],
            color: ink[500],
            fontSize: "0.72rem",
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            borderBottom: `1px solid ${ink[200]}`,
            whiteSpace: "nowrap",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: { root: { borderColor: ink[200], paddingTop: 12, paddingBottom: 12 } },
    },
    MuiTableRow: {
      styleOverrides: {
        root: { transition: "background-color 120ms", "&.MuiTableRow-hover:hover": { backgroundColor: alpha("#4F46E5", 0.04) } },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: { root: { borderRadius: 10, backgroundColor: "#FFFFFF" } },
    },
    MuiTooltip: {
      styleOverrides: { tooltip: { backgroundColor: ink[900], fontSize: "0.75rem", borderRadius: 8, padding: "6px 10px" } },
    },
    MuiLinearProgress: {
      styleOverrides: { root: { borderRadius: 4, backgroundColor: ink[100] }, bar: { borderRadius: 4 } },
    },
  },
});
