import AddIcon from "@mui/icons-material/Add";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import SearchIcon from "@mui/icons-material/Search";
import SearchOffIcon from "@mui/icons-material/SearchOff";
import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  InputAdornment,
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
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";

import { DeadlineChip } from "@/components/DeadlineChip";
import { PageHeader } from "@/components/PageHeader";
import { AppLayout } from "@/layouts/AppLayout";
import { tenderService } from "@/services/tenderService";
import { TENDER_CATEGORY_LABELS, type TenderCategoryValue, type TenderFilters, type TenderListItem } from "@/types/tender";
import { formatCurrency, formatDate } from "@/utils/format";

const STATUS_COLORS: Record<string, "default" | "success" | "warning" | "error"> = {
  open: "success",
  closed: "default",
  cancelled: "error",
  corrigendum: "warning",
};

/** Delivery states first; a buyer-only state is marked so it isn't read as the delivery location. */
function tenderStates(tender: TenderListItem): { label: string; isBuyer: boolean }[] {
  const delivery = [...new Set(tender.locations.map((loc) => loc.state).filter((s): s is string => Boolean(s)))];
  if (delivery.length > 0) return delivery.map((label) => ({ label, isBuyer: false }));
  return tender.organisation?.state ? [{ label: tender.organisation.state, isBuyer: true }] : [];
}

const FIT_LABELS = {
  ELIGIBLE: { label: "Eligible", color: "success" },
  NOT_ELIGIBLE: { label: "Not eligible", color: "error" },
  UNCERTAIN: { label: "Uncertain", color: "warning" },
} as const;

function isCategory(value: string | null): value is TenderCategoryValue {
  return value !== null && value in TENDER_CATEGORY_LABELS;
}

export function TendersList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [items, setItems] = useState<TenderListItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const initialCategory = searchParams.get("category");
  const [category, setCategory] = useState<TenderCategoryValue | "">(isCategory(initialCategory) ? initialCategory : "");
  const [status, setStatus] = useState<string>("");
  const [state, setState] = useState<string>(searchParams.get("state") ?? "");
  const [liveOnly, setLiveOnly] = useState(true);
  const [sort, setSort] = useState<"closing" | "relevance">(searchParams.get("sort") === "relevance" ? "relevance" : "closing");
  const [states, setStates] = useState<string[]>([]);
  const pageSize = 15;
  // Fixed per mount so paging doesn't shift the "live" cut-off under the user.
  const now = useMemo(() => new Date().toISOString(), []);

  useEffect(() => {
    tenderService.states().then(setStates);
  }, []);

  useEffect(() => {
    const filters: TenderFilters = { page, page_size: pageSize };
    if (keyword) filters.keyword = keyword;
    if (category) filters.category = category;
    if (status) filters.status = status as TenderFilters["status"];
    if (state) filters.state = state;
    if (liveOnly) filters.closing_after = now;
    if (sort === "relevance") filters.sort = "relevance";

    tenderService.list(filters).then((res) => {
      setItems(res.items);
      setTotal(res.total);
    });
  }, [page, keyword, category, status, state, liveOnly, sort, now]);

  const syncParams = (next: { category?: string; state?: string }) => {
    const params: Record<string, string> = {};
    const nextCategory = next.category ?? category;
    const nextState = next.state ?? state;
    if (nextCategory) params.category = nextCategory;
    if (nextState) params.state = nextState;
    setSearchParams(params, { replace: true });
  };

  const hasFilters = Boolean(keyword || category || status || state);
  // GeM publishes no bid value, so a column of dashes is just noise.
  const showValue = Boolean(items?.some((t) => t.tender_value));
  const columnCount = showValue ? 8 : 7;

  return (
    <AppLayout>
      <PageHeader
        eyebrow="Opportunities"
        title="Tenders"
        subtitle={
          items === null ? "Loading…" : `${total.toLocaleString("en-IN")} ${liveOnly ? "live " : ""}tender${total === 1 ? "" : "s"}${hasFilters ? " match your filters" : ""}`
        }
        actions={
          <Button component={RouterLink} to="/tenders/new" variant="contained" startIcon={<AddIcon />}>
            Add Tender Manually
          </Button>
        }
      />

      <Paper variant="outlined" sx={{ p: 2, mb: 2.5 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
          <TextField
            placeholder="Search title, number, organisation…"
            value={keyword}
            onChange={(e) => {
              setPage(1);
              setKeyword(e.target.value);
            }}
            fullWidth
            size="small"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" color="action" />
                </InputAdornment>
              ),
            }}
          />
          <TextField
            label="Category"
            select
            value={category}
            onChange={(e) => {
              const value = e.target.value as TenderCategoryValue | "";
              setPage(1);
              setCategory(value);
              syncParams({ category: value });
            }}
            sx={{ minWidth: 200 }}
            size="small"
          >
            <MenuItem value="">All categories</MenuItem>
            {Object.entries(TENDER_CATEGORY_LABELS).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="State"
            select
            value={state}
            onChange={(e) => {
              setPage(1);
              setState(e.target.value);
              syncParams({ state: e.target.value });
            }}
            sx={{ minWidth: 180 }}
            size="small"
          >
            <MenuItem value="">All states</MenuItem>
            {/* Keep a URL-supplied state selectable even before the list loads. */}
            {(state && !states.includes(state) ? [state, ...states] : states).map((s) => (
              <MenuItem key={s} value={s}>
                {s}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Status"
            select
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
            sx={{ minWidth: 150 }}
            size="small"
          >
            <MenuItem value="">All statuses</MenuItem>
            <MenuItem value="open">Open</MenuItem>
            <MenuItem value="closed">Closed</MenuItem>
            <MenuItem value="cancelled">Cancelled</MenuItem>
            <MenuItem value="corrigendum">Corrigendum</MenuItem>
          </TextField>
          <TextField
            label="Sort by"
            select
            value={sort}
            onChange={(e) => {
              setPage(1);
              setSort(e.target.value as "closing" | "relevance");
            }}
            sx={{ minWidth: 170 }}
            size="small"
          >
            <MenuItem value="closing">Closing soonest</MenuItem>
            <MenuItem value="relevance">Most relevant</MenuItem>
          </TextField>
          <FormControlLabel
            control={
              <Switch
                checked={liveOnly}
                onChange={(e) => {
                  setPage(1);
                  setLiveOnly(e.target.checked);
                }}
              />
            }
            label={<Typography variant="body2" fontWeight={600} noWrap>Live only</Typography>}
            title="Hide tenders whose closing date has passed"
            sx={{ flexShrink: 0, mr: 0 }}
          />
        </Stack>
      </Paper>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Tender</TableCell>
              <TableCell title="Rule-based relevance score and eligibility from the company profile">Fit</TableCell>
              <TableCell>Category</TableCell>
              <TableCell>Organisation</TableCell>
              <TableCell>State</TableCell>
              {showValue && <TableCell align="right">Value</TableCell>}
              <TableCell>Closing</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items === null &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={columnCount}>
                    <Skeleton height={36} />
                  </TableCell>
                </TableRow>
              ))}
            {items?.map((tender) => (
              <TableRow
                key={tender.id}
                hover
                onClick={() => navigate(`/tenders/${tender.id}`)}
                sx={{ cursor: "pointer", "&:hover .title": { color: "primary.main" } }}
              >
                <TableCell sx={{ maxWidth: { xs: 260, lg: 340 } }}>
                  <Typography
                    component={RouterLink}
                    to={`/tenders/${tender.id}`}
                    onClick={(e) => e.stopPropagation()}
                    variant="body2"
                    fontWeight={600}
                    className="title"
                    noWrap
                    title={tender.title}
                    display="block"
                    color="text.primary"
                    sx={{ textDecoration: "none" }}
                  >
                    {tender.title}
                  </Typography>
                  {tender.tender_number && (
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace" }}>
                      {tender.tender_number}
                    </Typography>
                  )}
                  {tender.opportunity && (
                    <Chip size="small" color="secondary" variant="outlined" label="In pipeline" sx={{ ml: 1, height: 20 }} />
                  )}
                </TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>
                  {tender.qualification ? (
                    <Stack spacing={0.25} alignItems="flex-start">
                      <Typography variant="body2" fontWeight={700}>
                        {tender.qualification.relevance_score}
                        <Typography component="span" variant="caption" color="text.secondary">
                          /100
                        </Typography>
                      </Typography>
                      <Chip
                        size="small"
                        label={FIT_LABELS[tender.qualification.eligibility_status].label}
                        color={FIT_LABELS[tender.qualification.eligibility_status].color}
                        variant="outlined"
                        sx={{ height: 20 }}
                      />
                    </Stack>
                  ) : (
                    <Typography variant="body2" color="text.disabled" title="Not assessed yet">
                      —
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {tender.categories.map((cat) => (
                      <Chip
                        key={cat.id}
                        label={TENDER_CATEGORY_LABELS[cat.category] ?? cat.category}
                        title={cat.confidence === null ? "Set at ingestion / manually" : "Assigned by AI analysis"}
                        size="small"
                        variant="outlined"
                        color={cat.confidence === null ? "primary" : "warning"}
                      />
                    ))}
                    {tender.categories.length === 0 && "—"}
                  </Stack>
                </TableCell>
                <TableCell sx={{ maxWidth: 200 }}>
                  <Typography variant="body2" noWrap title={tender.organisation?.name}>
                    {tender.organisation?.name ?? "—"}
                  </Typography>
                </TableCell>
                <TableCell>
                  {tenderStates(tender).map(({ label, isBuyer }) => (
                    <Stack
                      key={label}
                      direction="row"
                      alignItems="center"
                      spacing={0.5}
                      title={isBuyer ? "Buyer's state — the bid lists no delivery location" : "Delivery (consignee) state"}
                      color={isBuyer ? "text.secondary" : "text.primary"}
                    >
                      <PlaceOutlinedIcon sx={{ fontSize: 15, color: isBuyer ? "text.disabled" : "primary.main" }} />
                      <Typography variant="body2" noWrap>
                        {label}
                        {isBuyer && " (buyer)"}
                      </Typography>
                    </Stack>
                  ))}
                  {tenderStates(tender).length === 0 && (
                    <Typography variant="body2" color="text.disabled">
                      —
                    </Typography>
                  )}
                </TableCell>
                {showValue && (
                  <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
                    {formatCurrency(tender.tender_value)}
                  </TableCell>
                )}
                <TableCell sx={{ whiteSpace: "nowrap" }}>
                  <Stack spacing={0.5} alignItems="flex-start">
                    <DeadlineChip closing={tender.closing_date} />
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(tender.closing_date)}
                    </Typography>
                  </Stack>
                </TableCell>
                <TableCell>
                  <Chip
                    label={tender.status}
                    size="small"
                    color={STATUS_COLORS[tender.status] ?? "default"}
                    variant="outlined"
                    sx={{ textTransform: "capitalize" }}
                  />
                </TableCell>
              </TableRow>
            ))}
            {items?.length === 0 && (
              <TableRow>
                <TableCell colSpan={columnCount}>
                  <Stack alignItems="center" spacing={1} py={6} color="text.secondary">
                    <SearchOffIcon sx={{ fontSize: 40, color: "text.disabled" }} />
                    <Typography variant="subtitle1" color="text.primary">
                      {hasFilters || liveOnly ? "No tenders match these filters" : "No tenders yet"}
                    </Typography>
                    <Typography variant="body2">
                      {hasFilters || liveOnly
                        ? "Try clearing a filter or turning off “Live only”."
                        : "Run a source crawl, or use “Add Tender Manually” to enter one now."}
                    </Typography>
                  </Stack>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {total > pageSize && (
        <Box display="flex" justifyContent="center" mt={3}>
          <Pagination
            count={Math.ceil(total / pageSize)}
            page={page}
            onChange={(_, p) => setPage(p)}
            color="primary"
            shape="rounded"
          />
        </Box>
      )}
    </AppLayout>
  );
}
