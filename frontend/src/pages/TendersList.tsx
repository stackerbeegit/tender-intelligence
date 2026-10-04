import AddIcon from "@mui/icons-material/Add";
import {
  Box,
  Button,
  Chip,
  MenuItem,
  Pagination,
  Paper,
  Stack,
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
import { Link as RouterLink } from "react-router-dom";

import { AppLayout } from "@/layouts/AppLayout";
import { tenderService } from "@/services/tenderService";
import { TENDER_CATEGORY_LABELS, type TenderCategoryValue, type TenderFilters, type TenderListItem } from "@/types/tender";

const STATUS_COLORS: Record<string, "default" | "success" | "warning" | "error"> = {
  open: "success",
  closed: "default",
  cancelled: "error",
  corrigendum: "warning",
};

function formatCurrency(value: string | null): string {
  if (!value) return "—";
  const num = Number(value);
  if (num >= 1e7) return `₹${(num / 1e7).toFixed(2)} Cr`;
  if (num >= 1e5) return `₹${(num / 1e5).toFixed(2)} L`;
  return `₹${num.toLocaleString("en-IN")}`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function TendersList() {
  const [items, setItems] = useState<TenderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState<TenderCategoryValue | "">("");
  const [status, setStatus] = useState<string>("");
  const pageSize = 10;

  useEffect(() => {
    const filters: TenderFilters = { page, page_size: pageSize };
    if (keyword) filters.keyword = keyword;
    if (category) filters.category = category;
    if (status) filters.status = status as TenderFilters["status"];

    tenderService.list(filters).then((res) => {
      setItems(res.items);
      setTotal(res.total);
    });
  }, [page, keyword, category, status]);

  return (
    <AppLayout>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" fontWeight={600}>
          Tenders
        </Typography>
        <Button component={RouterLink} to="/tenders/new" variant="contained" startIcon={<AddIcon />}>
          Add Tender Manually
        </Button>
      </Stack>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField
            label="Search title, number, organisation"
            value={keyword}
            onChange={(e) => {
              setPage(1);
              setKeyword(e.target.value);
            }}
            fullWidth
            size="small"
          />
          <TextField
            label="Category"
            select
            value={category}
            onChange={(e) => {
              setPage(1);
              setCategory(e.target.value as TenderCategoryValue | "");
            }}
            sx={{ minWidth: 220 }}
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
            label="Status"
            select
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
            sx={{ minWidth: 160 }}
            size="small"
          >
            <MenuItem value="">All statuses</MenuItem>
            <MenuItem value="open">Open</MenuItem>
            <MenuItem value="closed">Closed</MenuItem>
            <MenuItem value="cancelled">Cancelled</MenuItem>
            <MenuItem value="corrigendum">Corrigendum</MenuItem>
          </TextField>
        </Stack>
      </Paper>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Title</TableCell>
              <TableCell>Organisation</TableCell>
              <TableCell>Value</TableCell>
              <TableCell>Closing Date</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((tender) => (
              <TableRow
                key={tender.id}
                hover
                component={RouterLink}
                to={`/tenders/${tender.id}`}
                sx={{ textDecoration: "none", cursor: "pointer" }}
              >
                <TableCell sx={{ maxWidth: 400 }}>
                  <Typography variant="body2" noWrap>
                    {tender.title}
                  </Typography>
                  {tender.tender_number && (
                    <Typography variant="caption" color="text.secondary">
                      {tender.tender_number}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>{tender.organisation?.name ?? "—"}</TableCell>
                <TableCell>{formatCurrency(tender.tender_value)}</TableCell>
                <TableCell>{formatDate(tender.closing_date)}</TableCell>
                <TableCell>
                  <Chip label={tender.status} size="small" color={STATUS_COLORS[tender.status] ?? "default"} />
                </TableCell>
              </TableRow>
            ))}
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography variant="body2" color="text.secondary" py={2} textAlign="center">
                    No tenders yet. Tender collection connectors arrive in later sprints — use "Add Tender
                    Manually" to enter one now.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {total > pageSize && (
        <Box display="flex" justifyContent="center" mt={2}>
          <Pagination count={Math.ceil(total / pageSize)} page={page} onChange={(_, p) => setPage(p)} />
        </Box>
      )}
    </AppLayout>
  );
}
