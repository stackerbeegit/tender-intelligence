import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadarIcon from "@mui/icons-material/Radar";
import { Alert, Box, Button, Stack, TextField, Typography } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { brand } from "@/theme";

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (user) {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={redirectTo} replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
      navigate("/", { replace: true });
    } catch {
      setError("Incorrect email or password.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Box display="flex" minHeight="100vh" bgcolor="background.default">
      <Box
        sx={{
          display: { xs: "none", md: "flex" },
          flex: 1,
          position: "relative",
          overflow: "hidden",
          flexDirection: "column",
          justifyContent: "space-between",
          p: 6,
          color: "#fff",
          background: brand.sidebarGradient,
        }}
      >
        <Box
          sx={{
            position: "absolute",
            width: 520,
            height: 520,
            right: -160,
            bottom: -160,
            borderRadius: "50%",
            background: brand.gradient,
            opacity: 0.55,
            filter: "blur(10px)",
          }}
        />
        <Stack direction="row" spacing={1.5} alignItems="center" position="relative">
          <Box
            sx={{ width: 42, height: 42, borderRadius: 2.5, background: brand.gradient, display: "grid", placeItems: "center" }}
          >
            <RadarIcon />
          </Box>
          <Typography fontWeight={800} fontSize="1.1rem">
            Stackerbee
          </Typography>
        </Stack>
        <Box position="relative" maxWidth={460}>
          <Typography variant="h3" fontWeight={800} letterSpacing="-0.03em" lineHeight={1.1}>
            Find the right tenders, before the deadline does.
          </Typography>
          <Stack spacing={1.5} mt={4}>
            {[
              "Live GeM bids in your focus areas, refreshed on demand",
              "Delivery state, deadline countdowns and value at a glance",
              "AI summaries with every fact traced back to the document",
            ].map((line) => (
              <Stack key={line} direction="row" spacing={1.5} alignItems="center">
                <CheckCircleIcon sx={{ color: "#C4B5FD", fontSize: 20 }} />
                <Typography sx={{ color: alpha("#fff", 0.85) }}>{line}</Typography>
              </Stack>
            ))}
          </Stack>
        </Box>
        <Typography variant="caption" sx={{ color: alpha("#fff", 0.5) }} position="relative">
          Tender Intelligence &amp; Opportunity Management
        </Typography>
      </Box>

      <Box flex={{ xs: 1, md: "0 0 520px" }} display="flex" alignItems="center" justifyContent="center" p={{ xs: 2, sm: 6 }}>
        <Box width="100%" maxWidth={400}>
          <Stack spacing={3} component="form" onSubmit={handleSubmit}>
            <Box>
              <Typography variant="overline" color="primary">
                Stackerbee Tender Intelligence
              </Typography>
              <Typography variant="h4">Welcome back</Typography>
              <Typography variant="body2" color="text.secondary" mt={0.5}>
                Sign in to review tender opportunities.
              </Typography>
            </Box>

            {error && <Alert severity="error">{error}</Alert>}

            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              fullWidth
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
            />
            <Button type="submit" variant="contained" size="large" disabled={isSubmitting} fullWidth sx={{ py: 1.4 }}>
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
