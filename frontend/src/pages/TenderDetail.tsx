import AccountBalanceOutlinedIcon from "@mui/icons-material/AccountBalanceOutlined";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import CurrencyRupeeIcon from "@mui/icons-material/CurrencyRupee";
import EventBusyOutlinedIcon from "@mui/icons-material/EventBusyOutlined";
import FolderOpenOutlinedIcon from "@mui/icons-material/FolderOpenOutlined";
import HistoryIcon from "@mui/icons-material/History";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import ReceiptLongOutlinedIcon from "@mui/icons-material/ReceiptLongOutlined";
import SavingsOutlinedIcon from "@mui/icons-material/SavingsOutlined";
import {
  Alert,
  Box,
  Button,
  Chip,
  Grid,
  Paper,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import { AnalysisPanel } from "@/components/AnalysisPanel";
import { DeadlineChip } from "@/components/DeadlineChip";
import { DocumentsPanel } from "@/components/DocumentsPanel";
import { useAuth } from "@/hooks/useAuth";
import { AppLayout } from "@/layouts/AppLayout";
import { tenderService } from "@/services/tenderService";
import { brand } from "@/theme";
import { TENDER_CATEGORY_LABELS, type TenderDetail as TenderDetailType } from "@/types/tender";
import { formatCurrency, formatDate, formatDateTime } from "@/utils/format";

const DOCUMENT_MANAGER_ROLES = ["admin", "bd_manager", "technical"];

function Fact({ icon, label, value, sub }: { icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode }) {
  const theme = useTheme();
  return (
    <Stack direction="row" spacing={1.5} alignItems="flex-start">
      <Box
        sx={{
          width: 40,
          height: 40,
          borderRadius: 2.5,
          display: "grid",
          placeItems: "center",
          flexShrink: 0,
          color: "primary.main",
          bgcolor: alpha(theme.palette.primary.main, 0.08),
          "& svg": { fontSize: 20 },
        }}
      >
        {icon}
      </Box>
      <Box minWidth={0}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          {label}
        </Typography>
        <Typography variant="body1" fontWeight={600} sx={{ wordBreak: "break-word" }}>
          {value}
        </Typography>
        {sub && (
          <Typography variant="caption" color="text.secondary">
            {sub}
          </Typography>
        )}
      </Box>
    </Stack>
  );
}

function Section({ icon, title, subtitle, children }: { icon: ReactNode; title: string; subtitle?: string; children: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 3, height: "100%" }}>
      <Stack direction="row" spacing={1.5} alignItems="center" mb={subtitle ? 0.5 : 2}>
        <Box sx={{ color: "primary.main", display: "flex" }}>{icon}</Box>
        <Typography variant="h6">{title}</Typography>
      </Stack>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" mb={2}>
          {subtitle}
        </Typography>
      )}
      {children}
    </Paper>
  );
}

export function TenderDetail() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [tender, setTender] = useState<TenderDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!id) return;
    tenderService
      .get(id)
      .then(setTender)
      .catch(() => setError("Tender not found."));
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (error) {
    return (
      <AppLayout>
        <Alert severity="error">{error}</Alert>
      </AppLayout>
    );
  }

  if (!tender) {
    return (
      <AppLayout>
        <Skeleton variant="rounded" height={260} sx={{ mb: 3, borderRadius: 4 }} />
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Skeleton variant="rounded" height={220} />
          </Grid>
          <Grid item xs={12} md={6}>
            <Skeleton variant="rounded" height={220} />
          </Grid>
        </Grid>
      </AppLayout>
    );
  }

  const canManage = Boolean(user && DOCUMENT_MANAGER_ROLES.includes(user.role.name));
  const deliveryStates = [...new Set(tender.locations.map((l) => l.state).filter(Boolean))];

  return (
    <AppLayout>
      <Button component={RouterLink} to="/tenders" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }} color="inherit">
        Back to tenders
      </Button>

      <Paper variant="outlined" sx={{ mb: 3, overflow: "hidden", borderRadius: 4 }}>
        <Box sx={{ height: 6, background: brand.gradient }} />
        <Box p={{ xs: 2.5, md: 3.5 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2} alignItems="flex-start">
            <Box minWidth={0}>
              <Stack direction="row" spacing={1} mb={1.5} flexWrap="wrap" useFlexGap>
                <Chip
                  label={tender.status}
                  size="small"
                  color={tender.status === "open" ? "success" : tender.status === "corrigendum" ? "warning" : "default"}
                  sx={{ textTransform: "capitalize" }}
                />
                {tender.categories.map((cat) => (
                  <Chip
                    key={cat.id}
                    label={
                      cat.confidence === null
                        ? TENDER_CATEGORY_LABELS[cat.category] ?? cat.category
                        : `${TENDER_CATEGORY_LABELS[cat.category] ?? cat.category} · AI ${Math.round(Number(cat.confidence) * 100)}%`
                    }
                    title={cat.confidence === null ? "Set manually" : "Assigned by AI analysis (interpretation)"}
                    size="small"
                    color={cat.confidence === null ? "primary" : "warning"}
                    variant="outlined"
                  />
                ))}
              </Stack>
              <Typography variant="h5" component="h1" sx={{ wordBreak: "break-word" }}>
                {tender.title}
              </Typography>
              {tender.tender_number && (
                <Typography variant="body2" color="text.secondary" mt={0.5} sx={{ fontFamily: "monospace" }}>
                  {tender.tender_number}
                </Typography>
              )}
            </Box>
            <Stack spacing={1} alignItems={{ xs: "flex-start", md: "flex-end" }} flexShrink={0}>
              <DeadlineChip closing={tender.closing_date} size="medium" />
              {tender.url && (
                <Button
                  href={tender.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="contained"
                  size="small"
                  endIcon={<OpenInNewIcon />}
                >
                  View on portal
                </Button>
              )}
            </Stack>
          </Stack>

          <Grid container spacing={3} mt={1}>
            <Grid item xs={12} sm={6} md={4}>
              <Fact
                icon={<AccountBalanceOutlinedIcon />}
                label="Organisation"
                value={tender.organisation?.name ?? "Not specified"}
                sub={tender.organisation?.state ? `Buyer state: ${tender.organisation.state}` : undefined}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Fact
                icon={<PlaceOutlinedIcon />}
                label="Delivery"
                value={deliveryStates.length ? deliveryStates.join(", ") : "Not stated in the bid"}
                sub={
                  tender.locations.length
                    ? tender.locations
                        .map((l) => [l.city, l.pincode].filter(Boolean).join(" "))
                        .filter(Boolean)
                        .join(" · ") || undefined
                    : undefined
                }
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Fact icon={<EventBusyOutlinedIcon />} label="Closing" value={formatDateTime(tender.closing_date)} />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Fact icon={<CurrencyRupeeIcon />} label="Tender Value" value={formatCurrency(tender.tender_value, "Not specified")} />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Fact icon={<SavingsOutlinedIcon />} label="EMD" value={formatCurrency(tender.emd_amount, "Not specified")} />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Fact icon={<ReceiptLongOutlinedIcon />} label="Tender Fee" value={formatCurrency(tender.tender_fee, "Not specified")} />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <Fact
                icon={<CalendarMonthOutlinedIcon />}
                label="Published"
                value={formatDate(tender.published_date, "Not specified")}
              />
            </Grid>
          </Grid>
        </Box>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={5}>
          <Section
            icon={<HistoryIcon />}
            title="Deadline History"
            subtitle="FACT — each row is a recorded deadline event; extensions keep the original rather than replacing it."
          >
            <Stack spacing={0} position="relative" pl={2.5}>
              {tender.deadlines.length > 0 && (
                <Box position="absolute" left={5} top={8} bottom={8} borderLeft={2} borderColor="divider" />
              )}
              {tender.deadlines.map((d, i) => (
                <Box key={d.id} position="relative" py={1}>
                  <Box
                    position="absolute"
                    left={-20}
                    top={14}
                    width={12}
                    height={12}
                    borderRadius="50%"
                    border={2}
                    borderColor={i === tender.deadlines.length - 1 ? "primary.main" : "divider"}
                    bgcolor="background.paper"
                  />
                  <Typography variant="body2" fontWeight={600}>
                    {formatDateTime(d.deadline_at)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: "capitalize" }}>
                    {d.deadline_type.replace("_", " ")}
                  </Typography>
                </Box>
              ))}
              {tender.deadlines.length === 0 && (
                <Typography variant="body2" color="text.secondary" ml={-2.5}>
                  No deadlines recorded.
                </Typography>
              )}
            </Stack>
          </Section>
        </Grid>

        <Grid item xs={12} md={7}>
          <Section icon={<FolderOpenOutlinedIcon />} title="Documents">
            <DocumentsPanel
              tenderId={tender.id}
              documents={tender.documents}
              canManage={canManage}
              onDocumentsChanged={refresh}
            />
          </Section>
        </Grid>

        <Grid item xs={12}>
          <Section icon={<AutoAwesomeIcon />} title="Tender Intelligence">
            <AnalysisPanel tenderId={tender.id} canRun={canManage} onAnalysisChanged={refresh} />
          </Section>
        </Grid>
      </Grid>
    </AppLayout>
  );
}
