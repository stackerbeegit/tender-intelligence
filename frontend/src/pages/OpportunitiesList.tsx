import {
  Box,
  Chip,
  FormControlLabel,
  MenuItem,
  Pagination,
  Paper,
  Skeleton,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { DeadlineChip } from "@/components/DeadlineChip";
import { PageHeader } from "@/components/PageHeader";
import { AppLayout } from "@/layouts/AppLayout";
import { opportunityService } from "@/services/opportunityService";
import {
  OPPORTUNITY_STATUS_LABELS,
  STATUS_CHIP_COLOR,
  type OpportunityListItem,
  type OpportunityStatus,
} from "@/types/opportunity";

const ELIGIBILITY_LABELS = { ELIGIBLE: "Eligible", NOT_ELIGIBLE: "Not eligible", UNCERTAIN: "Uncertain" } as const;
const PAGE_SIZE = 20;

export function OpportunitiesList() {
  const navigate = useNavigate();
  const [items, setItems] = useState<OpportunityListItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<OpportunityStatus | "">("");
  const [mine, setMine] = useState(false);
  const [openOnly, setOpenOnly] = useState(true);

  useEffect(() => {
    opportunityService
      .list({ status: status || undefined, mine, open_only: openOnly, page, page_size: PAGE_SIZE })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      });
  }, [status, mine, openOnly, page]);

  return (
    <AppLayout>
      <PageHeader
        eyebrow="Pipeline"
        title="Opportunities"
        subtitle={items === null ? "Loading…" : `${total} opportunit${total === 1 ? "y" : "ies"}, soonest closing first`}
      />

      <Paper variant="outlined" sx={{ p: 2, mb: 2.5 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            select
            size="small"
            label="Status"
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value as OpportunityStatus | "");
            }}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">All statuses</MenuItem>
            {Object.entries(OPPORTUNITY_STATUS_LABELS).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <FormControlLabel
            control={<Switch checked={mine} onChange={(e) => { setPage(1); setMine(e.target.checked); }} />}
            label="Mine only"
          />
          <FormControlLabel
            control={<Switch checked={openOnly} onChange={(e) => { setPage(1); setOpenOnly(e.target.checked); }} />}
            label="Hide won / lost / no bid"
          />
        </Stack>
      </Paper>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tender</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Assessment</TableCell>
              <TableCell>Closing</TableCell>
              <TableCell>Owner / team</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items === null &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={5}>
                    <Skeleton height={36} />
                  </TableCell>
                </TableRow>
              ))}
            {items?.map((o) => (
              <TableRow key={o.id} hover onClick={() => navigate(`/opportunities/${o.id}`)} sx={{ cursor: "pointer" }}>
                <TableCell sx={{ maxWidth: 380 }}>
                  <Typography variant="body2" fontWeight={600} noWrap title={o.tender.title}>
                    {o.tender.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" noWrap display="block">
                    {o.tender.organisation ?? "—"}
                    {o.created_from === "auto_relevance" && " · auto-promoted"}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_CHIP_COLOR[o.status]} label={OPPORTUNITY_STATUS_LABELS[o.status]} />
                </TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>
                  {o.relevance_score !== null ? (
                    <Typography variant="body2">
                      <strong>{o.relevance_score}</strong>/100 · {o.eligibility_status && ELIGIBILITY_LABELS[o.eligibility_status]}
                    </Typography>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Not assessed
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  <DeadlineChip closing={o.tender.closing_date} />
                </TableCell>
                <TableCell>
                  <Typography variant="body2">{o.owner?.full_name ?? "—"}</Typography>
                  {o.assignees.length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      {o.assignees.map((a) => a.full_name).join(", ")}
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {items?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography variant="body2" color="text.secondary" py={4} textAlign="center">
                    No opportunities match. Open a tender and choose “Interested — prepare bid”, or “Add to pipeline”.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {total > PAGE_SIZE && (
        <Box display="flex" justifyContent="center" mt={3}>
          <Pagination count={Math.ceil(total / PAGE_SIZE)} page={page} onChange={(_, p) => setPage(p)} color="primary" shape="rounded" />
        </Box>
      )}
    </AppLayout>
  );
}
