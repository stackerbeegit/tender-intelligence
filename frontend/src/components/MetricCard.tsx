import { Card, CardContent, Stack, Typography } from "@mui/material";

interface MetricCardProps {
  label: string;
  value: number;
  color?: "default" | "primary" | "warning" | "success" | "error";
}

const colorMap: Record<Required<MetricCardProps>["color"], string> = {
  default: "text.primary",
  primary: "primary.main",
  warning: "warning.main",
  success: "success.main",
  error: "error.main",
};

export function MetricCard({ label, value, color = "default" }: MetricCardProps) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={0.5}>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          <Typography variant="h4" sx={{ color: colorMap[color], fontWeight: 600 }}>
            {value}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}
