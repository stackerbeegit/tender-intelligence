export function formatCurrency(value: string | null, empty = "—"): string {
  if (!value) return empty;
  const num = Number(value);
  if (num >= 1e7) return `₹${(num / 1e7).toFixed(2)} Cr`;
  if (num >= 1e5) return `₹${(num / 1e5).toFixed(2)} L`;
  return `₹${num.toLocaleString("en-IN")}`;
}

export function formatDate(value: string | null, empty = "—"): string {
  if (!value) return empty;
  return new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | null, empty = "Not specified"): string {
  if (!value) return empty;
  return new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function formatRelative(value: string | null): string {
  if (!value) return "never";
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export type Urgency = "closed" | "critical" | "soon" | "comfortable" | "unknown";

/** Time left until a closing date, phrased for a deadline badge. */
export function deadlineCountdown(closing: string | null): { label: string; urgency: Urgency } {
  if (!closing) return { label: "No deadline", urgency: "unknown" };
  const ms = new Date(closing).getTime() - Date.now();
  if (ms <= 0) return { label: "Closed", urgency: "closed" };
  const hours = ms / 3_600_000;
  if (hours < 24) return { label: `${Math.max(1, Math.floor(hours))}h left`, urgency: "critical" };
  const days = Math.floor(hours / 24);
  if (days <= 3) return { label: `${days}d left`, urgency: "critical" };
  if (days <= 7) return { label: `${days}d left`, urgency: "soon" };
  return { label: `${days}d left`, urgency: "comfortable" };
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}
