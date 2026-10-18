import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";

import { analysisService } from "@/services/analysisService";
import { documentService } from "@/services/documentService";
import {
  ELIGIBILITY_TYPE_LABELS,
  REQUIREMENT_CATEGORY_LABELS,
  type Citation,
  type TenderAnalysisResponse,
  type TenderSummary,
} from "@/types/analysis";

const SUMMARY_SECTIONS: { key: keyof TenderSummary; label: string }[] = [
  { key: "core_requirements", label: "Core requirements" },
  { key: "manpower", label: "Manpower" },
  { key: "eligibility_highlights", label: "Eligibility" },
  { key: "msme_provisions", label: "MSME / Startup" },
  { key: "points_to_review", label: "Points to review" },
];

function formatValue(key: string, value: unknown): string {
  if (typeof value === "number" && key.endsWith("_inr")) return `₹${value.toLocaleString("en-IN")}`;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function StructuredValues({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values);
  if (entries.length === 0) return null;
  return (
    <Stack direction="row" spacing={0.5} mt={0.5} flexWrap="wrap" useFlexGap>
      {entries.map(([key, value]) => (
        <Chip key={key} size="small" variant="outlined" label={`${key.replace(/_/g, " ")}: ${formatValue(key, value)}`} />
      ))}
    </Stack>
  );
}

interface FactRowProps {
  label: string;
  summary: string;
  quote: string;
  values: Record<string, unknown>;
  citation: Citation;
  onOpenCitation: (citation: Citation) => void;
}

function FactRow({ label, summary, quote, values, citation, onOpenCitation }: FactRowProps) {
  return (
    <TableRow>
      <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>{label}</TableCell>
      <TableCell sx={{ verticalAlign: "top" }}>
        <Typography variant="body2" fontWeight={500}>
          {summary}
        </Typography>
        <Typography variant="body2" color="text.secondary" fontStyle="italic" mt={0.5}>
          “{quote}”
        </Typography>
        <StructuredValues values={values} />
      </TableCell>
      <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
        <Chip
          size="small"
          clickable
          onClick={() => onOpenCitation(citation)}
          label={`${citation.file_name} · p.${citation.page_number}`}
          title="Download the source document"
        />
      </TableCell>
    </TableRow>
  );
}

interface AnalysisPanelProps {
  tenderId: string;
  canRun: boolean;
  onAnalysisChanged: () => void;
}

export function AnalysisPanel({ tenderId, canRun, onAnalysisChanged }: AnalysisPanelProps) {
  const [data, setData] = useState<TenderAnalysisResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    analysisService
      .get(tenderId)
      .then(setData)
      .catch(() => setError("Could not load the analysis."));
  }, [tenderId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRun = async () => {
    setError(null);
    setIsRunning(true);
    try {
      setData(await analysisService.run(tenderId));
      onAnalysisChanged(); // categories and document page text may have changed
    } catch {
      setError("The analysis request failed. Check the backend logs.");
    } finally {
      setIsRunning(false);
    }
  };

  const openCitation = (citation: Citation) => {
    void documentService.download(tenderId, citation.document_id, citation.file_name);
  };

  const run = data?.analysis ?? null;
  const summary = run?.summary ?? null;
  const dropped = run?.run_stats.dropped_unverified ?? 0;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2} spacing={2}>
        <Typography variant="body2" color="text.secondary">
          {run?.finished_at
            ? `Last run ${new Date(run.finished_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}`
            : "Not analysed yet."}
        </Typography>
        {canRun && (
          <Button
            variant="contained"
            startIcon={isRunning ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
            onClick={handleRun}
            disabled={isRunning}
          >
            {isRunning ? "Analysing documents…" : run ? "Re-run analysis" : "Run analysis"}
          </Button>
        )}
      </Stack>

      {isRunning && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Reading every processed document for this tender. Large tenders can take a few minutes.
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {run?.status === "failed" && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Last analysis failed: {run.error}
          {(data?.requirements.length ?? 0) + (data?.eligibility.length ?? 0) > 0 &&
            " The results below are from the previous successful run."}
        </Alert>
      )}

      {summary && (
        <Box sx={{ border: 1, borderColor: "warning.light", borderRadius: 1, p: 2, mb: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" mb={1}>
            <Chip size="small" color="warning" label="AI INTERPRETATION" />
            <Typography variant="caption" color="text.secondary">
              Written by {run?.generated_by_model} from the cited facts below. [R#]/[E#] point to those facts.
            </Typography>
          </Stack>
          <Typography variant="subtitle1" fontWeight={600}>
            {summary.project}
          </Typography>
          <Typography variant="body2" mb={1}>
            {summary.overview}
          </Typography>
          {summary.contract_duration && (
            <Typography variant="body2" mb={1}>
              <strong>Duration:</strong> {summary.contract_duration}
            </Typography>
          )}
          {SUMMARY_SECTIONS.map(({ key, label }) => {
            const items = summary[key] as string[];
            if (!items?.length) return null;
            return (
              <Box key={key} mt={1}>
                <Typography variant="caption" color="text.secondary">
                  {label}
                </Typography>
                <ul style={{ margin: "2px 0", paddingLeft: 20 }}>
                  {items.map((item) => (
                    <li key={item}>
                      <Typography variant="body2">{item}</Typography>
                    </li>
                  ))}
                </ul>
              </Box>
            );
          })}
        </Box>
      )}

      {data && (data.requirements.length > 0 || data.eligibility.length > 0) && (
        <>
          <Stack direction="row" spacing={1} alignItems="center" mb={1}>
            <Chip size="small" color="success" label="FACT" />
            <Typography variant="caption" color="text.secondary">
              Verbatim clauses, each checked to appear on the cited page.
              {dropped > 0 && ` ${dropped} extracted item(s) were discarded because their quote was not found there.`}
            </Typography>
          </Stack>

          <Typography variant="subtitle2" mt={2}>
            Eligibility criteria ({data.eligibility.length})
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Type</TableCell>
                  <TableCell>Clause</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.eligibility.map((e) => (
                  <FactRow
                    key={e.id}
                    label={ELIGIBILITY_TYPE_LABELS[e.criterion_type] ?? e.criterion_type}
                    summary={e.summary}
                    quote={e.criterion_text}
                    values={e.extracted_value}
                    citation={e.citation}
                    onOpenCitation={openCitation}
                  />
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Divider sx={{ my: 2 }} />

          <Typography variant="subtitle2">Requirements ({data.requirements.length})</Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Category</TableCell>
                  <TableCell>Clause</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.requirements.map((r) => (
                  <FactRow
                    key={r.id}
                    label={REQUIREMENT_CATEGORY_LABELS[r.category] ?? r.category}
                    summary={r.summary}
                    quote={r.requirement_text}
                    values={r.details}
                    citation={r.citation}
                    onOpenCitation={openCitation}
                  />
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {run?.status === "done" && data?.requirements.length === 0 && data?.eligibility.length === 0 && (
        <Alert severity="info">The documents were read, but no requirements or eligibility clauses were found.</Alert>
      )}
    </Box>
  );
}
