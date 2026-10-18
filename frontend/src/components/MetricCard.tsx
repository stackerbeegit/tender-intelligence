import { Box, Card, CardActionArea, CardContent, Stack, Typography } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import type { ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";

interface MetricCardProps {
  label: string;
  /** `null` renders as "—": the metric isn't available yet, which is different from 0. */
  value: number | null;
  color?: "default" | "primary" | "warning" | "success" | "error" | "info";
  hint?: string;
  icon?: ReactNode;
  /** Optional 0–1 share shown as a thin bar under the value (e.g. relevant / active). */
  share?: number;
  to?: string;
}

export function MetricCard({ label, value, color = "default", hint, icon, share, to }: MetricCardProps) {
  const theme = useTheme();
  const main = color === "default" ? theme.palette.text.primary : theme.palette[color].main;

  const body = (
    <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
        <Stack spacing={0.5} minWidth={0}>
          <Typography variant="body2" color="text.secondary" fontWeight={600}>
            {label}
          </Typography>
          <Typography
            variant="h4"
            sx={{ color: value === null ? "text.disabled" : "text.primary", fontVariantNumeric: "tabular-nums" }}
          >
            {value ?? "—"}
          </Typography>
        </Stack>
        {icon && (
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: 3,
              display: "grid",
              placeItems: "center",
              flexShrink: 0,
              color: main,
              bgcolor: alpha(main, 0.1),
              "& svg": { fontSize: 24 },
            }}
          >
            {icon}
          </Box>
        )}
      </Stack>
      {share !== undefined && value !== null && (
        <Box mt={1.5} height={4} borderRadius={2} bgcolor="action.hover" overflow="hidden">
          <Box height="100%" width={`${Math.min(100, share * 100)}%`} bgcolor={main} borderRadius={2} />
        </Box>
      )}
      {hint && (
        <Typography variant="caption" color="text.secondary" display="block" mt={1}>
          {hint}
        </Typography>
      )}
    </CardContent>
  );

  return (
    <Card
      sx={{
        height: "100%",
        position: "relative",
        overflow: "hidden",
        transition: "transform 150ms, box-shadow 150ms",
        "&::before": { content: '""', position: "absolute", inset: "0 0 auto 0", height: 3, bgcolor: main, opacity: 0.85 },
        ...(to && { "&:hover": { transform: "translateY(-2px)", boxShadow: `0 10px 24px ${alpha(main, 0.15)}` } }),
      }}
    >
      {to ? (
        <CardActionArea component={RouterLink} to={to} sx={{ height: "100%" }}>
          {body}
        </CardActionArea>
      ) : (
        body
      )}
    </Card>
  );
}
