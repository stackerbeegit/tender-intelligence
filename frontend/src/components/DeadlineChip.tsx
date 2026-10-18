import ScheduleIcon from "@mui/icons-material/Schedule";
import { Chip } from "@mui/material";

import { deadlineCountdown, formatDateTime, type Urgency } from "@/utils/format";

const URGENCY_COLOR: Record<Urgency, "default" | "error" | "warning" | "success"> = {
  closed: "default",
  critical: "error",
  soon: "warning",
  comfortable: "success",
  unknown: "default",
};

export function DeadlineChip({ closing, size = "small" }: { closing: string | null; size?: "small" | "medium" }) {
  const { label, urgency } = deadlineCountdown(closing);
  return (
    <Chip
      icon={<ScheduleIcon />}
      label={label}
      title={closing ? `Closes ${formatDateTime(closing)}` : undefined}
      size={size}
      color={URGENCY_COLOR[urgency]}
      variant={urgency === "closed" || urgency === "unknown" ? "outlined" : "filled"}
      sx={{ fontVariantNumeric: "tabular-nums" }}
    />
  );
}
