import { Alert, Box, Grid, Skeleton, Typography } from "@mui/material";
import { useEffect, useState } from "react";

import { MetricCard } from "@/components/MetricCard";
import { AppLayout } from "@/layouts/AppLayout";
import { dashboardService } from "@/services/dashboardService";
import type { DashboardSummary } from "@/types/dashboard";

export function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dashboardService
      .getSummary()
      .then(setSummary)
      .catch(() => setError("Could not load dashboard metrics."));
  }, []);

  return (
    <AppLayout>
      <Typography variant="h5" fontWeight={600} mb={1}>
        Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        Tender collection, intelligence, and the opportunity CRM arrive in later sprints — see{" "}
        <code>docs/development-plan.md</code>.
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}
      {summary?.note && (
        <Alert severity="info" sx={{ mb: 3 }}>
          {summary.note}
        </Alert>
      )}

      <Grid container spacing={2}>
        {summary ? (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="New Tenders" value={summary.new_tenders} color="primary" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Relevant" value={summary.relevant_tenders} color="primary" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Highly Relevant" value={summary.highly_relevant} color="success" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Expiring Soon" value={summary.expiring_soon} color="warning" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Under Review" value={summary.under_review} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Bidding" value={summary.bidding} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Submitted" value={summary.submitted} />
            </Grid>
            <Grid item xs={12} sm={6} md={1.5}>
              <MetricCard label="Won" value={summary.won} color="success" />
            </Grid>
            <Grid item xs={12} sm={6} md={1.5}>
              <MetricCard label="Lost" value={summary.lost} color="error" />
            </Grid>
          </>
        ) : (
          !error &&
          Array.from({ length: 8 }).map((_, i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Box>
                <Skeleton variant="rounded" height={88} />
              </Box>
            </Grid>
          ))
        )}
      </Grid>
    </AppLayout>
  );
}
