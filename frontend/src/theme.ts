import { createTheme } from "@mui/material/styles";

/**
 * Sprint 1 placeholder theme. Swap palette/typography here once Stackerbee
 * branding is finalised — nothing downstream should hardcode colors.
 */
export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1565C0" },
    secondary: { main: "#F59E0B" },
    background: { default: "#F4F6F8" },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: ['"Inter"', "Roboto", "Helvetica", "Arial", "sans-serif"].join(","),
  },
});
