import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import { DocumentsPanel } from "@/components/DocumentsPanel";
import { useAuth } from "@/hooks/useAuth";
import { AppLayout } from "@/layouts/AppLayout";
import { tenderService } from "@/services/tenderService";
import { TENDER_CATEGORY_LABELS, type TenderDetail as TenderDetailType } from "@/types/tender";

const DOCUMENT_MANAGER_ROLES = ["admin", "bd_manager", "technical"];

function formatCurrency(value: string | null): string {
  if (!value) return "Not specified";
  return `₹${Number(value).toLocaleString("en-IN")}`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not specified";
  return new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
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
    return <AppLayout>{null}</AppLayout>;
  }

  return (
    <AppLayout>
      <Button component={RouterLink} to="/tenders" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>
        Back to tenders
      </Button>

      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Box>
            <Typography variant="h5" fontWeight={600}>
              {tender.title}
            </Typography>
            {tender.tender_number && (
              <Typography variant="body2" color="text.secondary">
                Tender No: {tender.tender_number}
              </Typography>
            )}
          </Box>
          <Chip label={tender.status} color={tender.status === "open" ? "success" : "default"} />
        </Stack>

        <Grid container spacing={3} mt={2}>
          <Grid item xs={12} sm={4}>
            <Typography variant="caption" color="text.secondary">
              Organisation
            </Typography>
            <Typography variant="body1">{tender.organisation?.name ?? "Not specified"}</Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="caption" color="text.secondary">
              Tender Value
            </Typography>
            <Typography variant="body1">{formatCurrency(tender.tender_value)}</Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="caption" color="text.secondary">
              Closing Date
            </Typography>
            <Typography variant="body1">{formatDateTime(tender.closing_date)}</Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="caption" color="text.secondary">
              EMD
            </Typography>
            <Typography variant="body1">{formatCurrency(tender.emd_amount)}</Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="caption" color="text.secondary">
              Tender Fee
            </Typography>
            <Typography variant="body1">{formatCurrency(tender.tender_fee)}</Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="caption" color="text.secondary">
              Published
            </Typography>
            <Typography variant="body1">{tender.published_date ?? "Not specified"}</Typography>
          </Grid>
        </Grid>

        {tender.locations.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="caption" color="text.secondary">
              Locations
            </Typography>
            <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap">
              {tender.locations.map((loc) => (
                <Chip key={loc.id} label={[loc.city, loc.state].filter(Boolean).join(", ") || "Unspecified"} size="small" />
              ))}
            </Stack>
          </>
        )}

        {tender.categories.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="caption" color="text.secondary">
              Categories
            </Typography>
            <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap">
              {tender.categories.map((cat) => (
                <Chip
                  key={cat.id}
                  label={TENDER_CATEGORY_LABELS[cat.category] ?? cat.category}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              ))}
            </Stack>
          </>
        )}
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="h6" mb={1}>
              Deadline History
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              FACT — each row is a recorded deadline event; extensions keep the original rather than replacing it.
            </Typography>
            <List dense>
              {tender.deadlines.map((d) => (
                <ListItem key={d.id} disableGutters>
                  <ListItemText
                    primary={formatDateTime(d.deadline_at)}
                    secondary={d.deadline_type.replace("_", " ")}
                  />
                </ListItem>
              ))}
              {tender.deadlines.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No deadlines recorded.
                </Typography>
              )}
            </List>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="h6" mb={1}>
              Documents
            </Typography>
            <DocumentsPanel
              tenderId={tender.id}
              documents={tender.documents}
              canManage={Boolean(user && DOCUMENT_MANAGER_ROLES.includes(user.role.name))}
              onDocumentsChanged={refresh}
            />
          </Paper>
        </Grid>
      </Grid>
    </AppLayout>
  );
}
