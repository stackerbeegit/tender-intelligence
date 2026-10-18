import AccessAlarmIcon from "@mui/icons-material/AccessAlarm";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import FiberNewOutlinedIcon from "@mui/icons-material/FiberNewOutlined";
import InsightsIcon from "@mui/icons-material/Insights";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import SyncIcon from "@mui/icons-material/Sync";
import TrackChangesIcon from "@mui/icons-material/TrackChanges";
import {
  Alert,
  Box,
  Button,
  Chip,
  Grid,
  Paper,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { type ReactNode, useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { DeadlineChip } from "@/components/DeadlineChip";
import { MetricCard } from "@/components/MetricCard";
import { useAuth } from "@/hooks/useAuth";
import { AppLayout } from "@/layouts/AppLayout";
import { dashboardService } from "@/services/dashboardService";
import { tenderService } from "@/services/tenderService";
import { brand } from "@/theme";
import type { DashboardSummary } from "@/types/dashboard";
import { TENDER_CATEGORY_LABELS, type TenderListItem } from "@/types/tender";
import { formatRelative } from "@/utils/format";

const PIPELINE_STAGES: { key: keyof DashboardSummary; label: string }[] = [
  { key: "highly_relevant", label: "Highly Relevant" },
  { key: "under_review", label: "Under Review" },
  { key: "bidding", label: "Bidding" },
  { key: "submitted", label: "Submitted" },
  { key: "won", label: "Won" },
  { key: "lost", label: "Lost" },
];

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function SectionCard({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Paper variant="outlined" sx={{ p: 2.5, height: "100%" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={2} spacing={2}>
        <Box>
          <Typography variant="subtitle1">{title}</Typography>
          {subtitle && (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {action}
      </Stack>
      {children}
    </Paper>
  );
}

function Hero({ summary, firstName }: { summary: DashboardSummary; firstName: string }) {
  return (
    <Paper
      elevation={0}
      sx={{
        position: "relative",
        overflow: "hidden",
        p: { xs: 3, md: 4 },
        mb: 3,
        color: "#fff",
        background: brand.gradient,
        borderRadius: 4,
      }}
    >
      {/* Decorative rings */}
      {[260, 180].map((size, i) => (
        <Box
          key={size}
          sx={{
            position: "absolute",
            right: { xs: -size / 2, md: 40 + i * 50 },
            top: -size / 3 + i * 60,
            width: size,
            height: size,
            borderRadius: "50%",
            border: `2px solid ${alpha("#fff", 0.14)}`,
            background: alpha("#fff", 0.04),
            pointerEvents: "none",
          }}
        />
      ))}
      <Stack position="relative" spacing={1.5} maxWidth={680}>
        <Chip
          icon={<SyncIcon sx={{ color: "#fff !important" }} />}
          label={`GeM data refreshed ${formatRelative(summary.last_crawl_at)}`}
          size="small"
          sx={{ alignSelf: "flex-start", bgcolor: alpha("#fff", 0.18), color: "#fff", backdropFilter: "blur(4px)" }}
        />
        <Typography variant="h4" component="h1">
          {greeting()}, {firstName}
        </Typography>
        <Typography sx={{ color: alpha("#fff", 0.85) }}>
          <b>{summary.active_tenders}</b> live opportunities
          {summary.by_state.length > 0 && (
            <>
              {" "}
              across{" "}
              <b>
                {summary.by_state.length}
                {summary.by_state.length >= 10 ? "+" : ""}
              </b>{" "}
              states
            </>
          )}
          , with <b>{summary.expiring_soon}</b> closing in the next {summary.expiring_window_days} days.
        </Typography>
        <Stack direction="row" spacing={1.5} pt={1} flexWrap="wrap" useFlexGap>
          <Button
            component={RouterLink}
            to="/tenders/new"
            variant="outlined"
            sx={{ color: "#fff", borderColor: alpha("#fff", 0.5), "&:hover": { borderColor: "#fff", bgcolor: alpha("#fff", 0.08) } }}
          >
            Add a tender
          </Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

/** Single-series column chart: how many active tenders close on each upcoming day. */
function ClosingTimeline({ days }: { days: DashboardSummary["closing_timeline"] }) {
  const theme = useTheme();
  const max = Math.max(1, ...days.map((d) => d.count));
  const total = days.reduce((sum, d) => sum + d.count, 0);
  const CHART_HEIGHT = 168;

  return (
    <Box>
      <Typography variant="h5" component="p" sx={{ fontVariantNumeric: "tabular-nums" }}>
        {total}
        <Typography component="span" variant="body2" color="text.secondary" ml={1}>
          tenders close in the next {days.length} days
        </Typography>
      </Typography>
      <Box position="relative" mt={2}>
        {/* Recessive gridlines at 0, 50%, 100% of the max */}
        {[1, 0.5].map((frac) => (
          <Box
            key={frac}
            sx={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 22 + CHART_HEIGHT * frac,
              borderTop: `1px dashed ${theme.palette.divider}`,
            }}
          >
            <Typography variant="caption" color="text.disabled" sx={{ position: "absolute", top: -18, left: 0 }}>
              {Math.round(max * frac)}
            </Typography>
          </Box>
        ))}
        <Stack direction="row" alignItems="flex-end" spacing="2px" height={CHART_HEIGHT + 22} pl={3}>
          {days.map((day, i) => {
            const date = new Date(`${day.date}T00:00:00`);
            const weekday = date.toLocaleDateString("en-IN", { weekday: "short" });
            const label = date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
            const isToday = i === 0;
            return (
              <Tooltip
                key={day.date}
                arrow
                placement="top"
                title={`${isToday ? "Today" : weekday}, ${label}: ${day.count} tender${day.count === 1 ? "" : "s"} closing`}
              >
                <Stack flex={1} alignItems="center" height="100%" justifyContent="flex-end" sx={{ cursor: "default" }}>
                  <Box
                    sx={{
                      width: "100%",
                      maxWidth: 34,
                      height: day.count === 0 ? 2 : Math.max(6, (day.count / max) * CHART_HEIGHT),
                      borderRadius: day.count === 0 ? 1 : "4px 4px 0 0",
                      bgcolor: day.count === 0 ? "divider" : isToday ? "primary.dark" : "primary.main",
                      opacity: day.count === 0 ? 1 : isToday ? 1 : 0.85,
                      transition: "opacity 120ms, transform 120ms",
                      "&:hover": { opacity: 1 },
                    }}
                  />
                  <Typography
                    variant="caption"
                    mt={0.5}
                    color={isToday ? "text.primary" : "text.secondary"}
                    fontWeight={isToday ? 700 : 400}
                    sx={{ fontSize: "0.68rem", lineHeight: "16px" }}
                  >
                    {isToday ? "Today" : date.getDate()}
                  </Typography>
                </Stack>
              </Tooltip>
            );
          })}
        </Stack>
      </Box>
    </Box>
  );
}

/** Ranked horizontal bars; each row links to the filtered tender list. */
function RankedBars({ rows }: { rows: { key: string; label: string; count: number; to: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <Stack spacing={1.5}>
      {rows.map((row, i) => (
        <Box
          key={row.key}
          component={RouterLink}
          to={row.to}
          sx={{ color: "inherit", textDecoration: "none", "&:hover .label": { color: "primary.main" } }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" mb={0.5}>
            <Typography variant="body2" className="label" fontWeight={500} noWrap>
              <Typography component="span" variant="caption" color="text.disabled" mr={1} fontWeight={700}>
                {String(i + 1).padStart(2, "0")}
              </Typography>
              {row.label}
            </Typography>
            <Typography variant="body2" fontWeight={700} sx={{ fontVariantNumeric: "tabular-nums" }}>
              {row.count}
            </Typography>
          </Stack>
          <Box height={8} borderRadius={1} bgcolor="action.hover" overflow="hidden">
            <Box
              height="100%"
              width={`${(row.count / max) * 100}%`}
              bgcolor="primary.main"
              borderRadius={1}
              sx={{ opacity: 0.35 + 0.65 * (row.count / max) }}
            />
          </Box>
        </Box>
      ))}
      {rows.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          Nothing to show yet.
        </Typography>
      )}
    </Stack>
  );
}

function ClosingSoonest({ tenders }: { tenders: TenderListItem[] | null }) {
  if (!tenders) return <Skeleton variant="rounded" height={260} />;
  if (tenders.length === 0)
    return (
      <Typography variant="body2" color="text.secondary">
        No live tenders.
      </Typography>
    );
  return (
    <Stack divider={<Box borderTop={1} borderColor="divider" />}>
      {tenders.map((tender) => {
        const state = tender.locations.find((l) => l.state)?.state ?? tender.organisation?.state;
        return (
          <Stack
            key={tender.id}
            component={RouterLink}
            to={`/tenders/${tender.id}`}
            direction="row"
            alignItems="center"
            spacing={2}
            py={1.25}
            sx={{ color: "inherit", textDecoration: "none", "&:hover .title": { color: "primary.main" } }}
          >
            <Box minWidth={0} flexGrow={1}>
              <Typography variant="body2" fontWeight={600} className="title" noWrap>
                {tender.title}
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center" color="text.secondary">
                <Typography variant="caption" noWrap>
                  {tender.organisation?.name ?? "—"}
                </Typography>
                {state && (
                  <Stack direction="row" alignItems="center" spacing={0.25} flexShrink={0}>
                    <PlaceOutlinedIcon sx={{ fontSize: 13 }} />
                    <Typography variant="caption">{state}</Typography>
                  </Stack>
                )}
              </Stack>
            </Box>
            <DeadlineChip closing={tender.closing_date} />
            <ChevronRightIcon fontSize="small" color="disabled" />
          </Stack>
        );
      })}
    </Stack>
  );
}

function Pipeline({ summary }: { summary: DashboardSummary }) {
  const pendingReasons = [...new Set(PIPELINE_STAGES.map(({ key }) => summary.pending_metrics[key]).filter(Boolean))];
  return (
    <SectionCard
      title="Opportunity pipeline"
      subtitle="Track bids from first look to award"
      action={<Chip icon={<AutoAwesomeIcon />} label="Coming soon" size="small" color="primary" variant="outlined" />}
    >
      <Grid container spacing={1.5}>
        {PIPELINE_STAGES.map(({ key, label }, i) => {
          const value = summary[key] as number | null;
          return (
            <Grid item xs={6} sm={4} md={2} key={key}>
              <Box
                title={value === null ? summary.pending_metrics[key] : undefined}
                sx={{
                  p: 1.5,
                  borderRadius: 2.5,
                  border: 1,
                  borderColor: "divider",
                  borderStyle: value === null ? "dashed" : "solid",
                  bgcolor: value === null ? "transparent" : "background.paper",
                }}
              >
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  {String(i + 1).padStart(2, "0")} · {label}
                </Typography>
                <Typography variant="h5" color={value === null ? "text.disabled" : "text.primary"}>
                  {value ?? "—"}
                </Typography>
              </Box>
            </Grid>
          );
        })}
      </Grid>
      {pendingReasons.length > 0 && (
        <Typography variant="caption" color="text.secondary" display="block" mt={1.5}>
          {pendingReasons.join(" ")}
        </Typography>
      )}
    </SectionCard>
  );
}

export function Dashboard() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [closingSoonest, setClosingSoonest] = useState<TenderListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dashboardService
      .getSummary()
      .then(setSummary)
      .catch(() => setError("Could not load dashboard metrics."));
    tenderService
      .list({ closing_after: new Date().toISOString(), page_size: 6 })
      .then((res) => setClosingSoonest(res.items))
      .catch(() => setClosingSoonest([]));
  }, []);

  const firstName = user?.full_name.split(" ")[0] ?? "there";

  return (
    <AppLayout>
      {error && <Alert severity="error">{error}</Alert>}

      {!summary && !error && (
        <Stack spacing={3}>
          <Skeleton variant="rounded" height={200} sx={{ borderRadius: 4 }} />
          <Grid container spacing={2}>
            {Array.from({ length: 4 }).map((_, i) => (
              <Grid item xs={12} sm={6} md={3} key={i}>
                <Skeleton variant="rounded" height={128} />
              </Grid>
            ))}
          </Grid>
          <Skeleton variant="rounded" height={280} />
        </Stack>
      )}

      {summary && (
        <>
          <Hero summary={summary} firstName={firstName} />

          <Grid container spacing={2.5} mb={3}>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard
                label="Active Tenders"
                value={summary.active_tenders}
                color="primary"
                icon={<InsightsIcon />}
                hint="Open, deadline not passed"
                to="/tenders"
              />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard
                label="New Tenders"
                value={summary.new_tenders}
                color="info"
                icon={<FiberNewOutlinedIcon />}
                hint={`Added in the last ${summary.new_window_days} days`}
                share={summary.active_tenders ? summary.new_tenders / summary.active_tenders : 0}
              />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard
                label="Relevant"
                value={summary.relevant_tenders}
                color="success"
                icon={<TrackChangesIcon />}
                hint="In a Stackerbee focus area"
                share={summary.active_tenders ? summary.relevant_tenders / summary.active_tenders : 0}
              />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard
                label="Expiring Soon"
                value={summary.expiring_soon}
                color="warning"
                icon={<AccessAlarmIcon />}
                hint={`Closing within ${summary.expiring_window_days} days`}
                share={summary.active_tenders ? summary.expiring_soon / summary.active_tenders : 0}
              />
            </Grid>
          </Grid>

          <Grid container spacing={2.5} mb={3}>
            <Grid item xs={12} lg={8}>
              <SectionCard title="Upcoming deadlines" subtitle="Active tenders closing each day (IST)">
                <ClosingTimeline days={summary.closing_timeline} />
              </SectionCard>
            </Grid>
            <Grid item xs={12} lg={4}>
              <SectionCard title="Top states" subtitle="Delivery state, else buyer's state">
                <RankedBars
                  rows={summary.by_state.slice(0, 7).map(({ state, count }) => ({
                    key: state,
                    label: state,
                    count,
                    to: `/tenders?state=${encodeURIComponent(state)}`,
                  }))}
                />
              </SectionCard>
            </Grid>
          </Grid>

          <Grid container spacing={2.5} mb={3}>
            <Grid item xs={12} lg={7}>
              <SectionCard
                title="Closing soonest"
                subtitle="Live tenders, nearest deadline first"
                action={
                  <Button component={RouterLink} to="/tenders" size="small" endIcon={<ChevronRightIcon />}>
                    View all
                  </Button>
                }
              >
                <ClosingSoonest tenders={closingSoonest} />
              </SectionCard>
            </Grid>
            <Grid item xs={12} lg={5}>
              <SectionCard
                title="By focus area"
                subtitle={`${summary.analysed_tenders} tender(s) analysed by AI`}
              >
                <RankedBars
                  rows={summary.by_category.map(({ category, count }) => ({
                    key: category,
                    label: TENDER_CATEGORY_LABELS[category] ?? category,
                    count,
                    to: `/tenders?category=${category}`,
                  }))}
                />
              </SectionCard>
            </Grid>
          </Grid>

          <Pipeline summary={summary} />
        </>
      )}
    </AppLayout>
  );
}
