import RefreshIcon from "@mui/icons-material/Refresh";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  LinearProgress,
  Link,
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
import { Link as RouterLink } from "react-router-dom";

import { documentService } from "@/services/documentService";
import { qualificationService } from "@/services/qualificationService";
import { ELIGIBILITY_TYPE_LABELS } from "@/types/analysis";
import {
  FACTOR_LABELS,
  type CriterionOutcome,
  type EligibilityStatus,
  type FactorName,
  type QualificationResponse,
  type RiskSeverity,
} from "@/types/qualification";

type ChipColor = "success" | "error" | "warning" | "default" | "info";

const STATUS_DISPLAY: Record<EligibilityStatus, { label: string; color: ChipColor }> = {
  ELIGIBLE: { label: "Eligible", color: "success" },
  NOT_ELIGIBLE: { label: "Not eligible", color: "error" },
  UNCERTAIN: { label: "Uncertain", color: "warning" },
};

const OUTCOME_DISPLAY: Record<CriterionOutcome, { label: string; color: ChipColor }> = {
  MET: { label: "Met", color: "success" },
  NOT_MET: { label: "Not met", color: "error" },
  UNKNOWN: { label: "Unknown", color: "warning" },
  INFO: { label: "Info", color: "default" },
};

const SEVERITY_COLOR: Record<RiskSeverity, ChipColor> = { high: "error", medium: "warning", low: "default" };

const FACTOR_ORDER: FactorName[] = [
  "technical",
  "eligibility",
  "experience",
  "manpower",
  "commercial",
  "location",
  "msme",
  "deadline",
];

interface QualificationPanelProps {
  tenderId: string;
  canCompute: boolean;
  /** Bumped by the parent when the tender's facts change, to reload. */
  reloadKey?: number;
}

export function QualificationPanel({ tenderId, canCompute, reloadKey = 0 }: QualificationPanelProps) {
  const [data, setData] = useState<QualificationResponse | null>(null);
  const [isComputing, setIsComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    qualificationService
      .get(tenderId)
      .then(setData)
      .catch(() => setError("Could not load the qualification."));
  }, [tenderId]);

  useEffect(() => {
    load();
  }, [load, reloadKey]);

  const handleCompute = async () => {
    setError(null);
    setIsComputing(true);
    try {
      setData(await qualificationService.compute(tenderId));
    } catch {
      setError("Could not compute the qualification. Check the backend logs.");
    } finally {
      setIsComputing(false);
    }
  };

  const openSource = (documentId: string, fileName: string) => {
    void documentService.download(tenderId, documentId, fileName);
  };

  if (!data) {
    return error ? <Alert severity="error">{error}</Alert> : <LinearProgress />;
  }

  const result = data.qualification;

  if (!data.profile_configured) {
    return (
      <Alert severity="info">
        Qualification compares this tender with the company profile, which has not been set up yet.{" "}
        <Link component={RouterLink} to="/profile">
          Set up the company profile
        </Link>
        .
      </Alert>
    );
  }

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2} mb={2}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <Chip size="small" color="info" label="ASSESSMENT" />
          <Typography variant="caption" color="text.secondary">
            Computed by fixed rules from the cited facts and the company profile. No AI is involved in this step.
          </Typography>
        </Stack>
        {canCompute && (
          <Button
            variant={result && !data.is_stale ? "outlined" : "contained"}
            startIcon={isComputing ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
            onClick={handleCompute}
            disabled={isComputing}
            sx={{ flexShrink: 0 }}
          >
            {result ? "Recompute" : "Compute qualification"}
          </Button>
        )}
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {data.is_stale && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          The company profile or this tender's facts have changed since this was computed.
          {canCompute ? " Recompute to bring it up to date." : " Ask a BD manager or admin to recompute it."}
        </Alert>
      )}
      {!result && <Typography color="text.secondary">Not computed yet.</Typography>}

      {result && (
        <>
          <Stack direction="row" spacing={4} alignItems="center" mb={3} flexWrap="wrap" useFlexGap>
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                Eligibility
              </Typography>
              <Chip
                color={STATUS_DISPLAY[result.eligibility_status].color}
                label={STATUS_DISPLAY[result.eligibility_status].label}
                sx={{ fontWeight: 700 }}
              />
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                Relevance
              </Typography>
              <Typography variant="h5" fontWeight={700} component="span">
                {result.relevance_score}
              </Typography>
              <Typography variant="body2" color="text.secondary" component="span">
                {" "}
                / 100
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Computed {new Date(result.computed_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
            </Typography>
          </Stack>

          <Typography variant="subtitle2">Eligibility criteria</Typography>
          <TableContainer>
            <Table size="small">
              <TableBody>
                {result.reasons.map((reason, i) => (
                  <TableRow key={reason.evidence?.fact_id ?? `reason-${i}`}>
                    <TableCell sx={{ verticalAlign: "top", width: 96 }}>
                      <Chip
                        size="small"
                        color={reason.polarity === "support" && reason.outcome === "INFO" ? "success" : OUTCOME_DISPLAY[reason.outcome].color}
                        variant={reason.outcome === "INFO" ? "outlined" : "filled"}
                        label={OUTCOME_DISPLAY[reason.outcome].label}
                      />
                    </TableCell>
                    <TableCell sx={{ verticalAlign: "top" }}>
                      {reason.criterion_type && (
                        <Typography variant="caption" color="text.secondary">
                          {ELIGIBILITY_TYPE_LABELS[reason.criterion_type] ?? reason.criterion_type}
                        </Typography>
                      )}
                      <Typography variant="body2">{reason.text}</Typography>
                      {reason.evidence && (
                        <Typography variant="body2" color="text.secondary" fontStyle="italic" mt={0.5}>
                          “{reason.evidence.quote}”
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
                      {reason.evidence && (
                        <Chip
                          size="small"
                          clickable
                          onClick={() => openSource(reason.evidence!.document_id, reason.evidence!.file_name)}
                          label={`${reason.evidence.file_name} · p.${reason.evidence.page_number}`}
                          title="Download the source document"
                        />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Divider sx={{ my: 2 }} />

          <Typography variant="subtitle2">Relevance breakdown</Typography>
          <Typography variant="caption" color="text.secondary" display="block" mb={1}>
            The score is the weighted average of these factors. Factors without data count as a neutral 50.
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Factor</TableCell>
                  <TableCell sx={{ width: 160 }}>Score</TableCell>
                  <TableCell align="right">Weight</TableCell>
                  <TableCell>Why</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {FACTOR_ORDER.filter((name) => result.relevance_factors[name]).map((name) => {
                  const factor = result.relevance_factors[name];
                  return (
                    <TableRow key={name} sx={{ opacity: factor.known ? 1 : 0.6 }}>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{FACTOR_LABELS[name]}</TableCell>
                      <TableCell>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <LinearProgress
                            variant="determinate"
                            value={factor.score}
                            sx={{ flexGrow: 1, height: 6, borderRadius: 3 }}
                            color={factor.known ? (factor.score >= 70 ? "success" : factor.score >= 40 ? "warning" : "error") : "inherit"}
                          />
                          <Typography variant="body2" sx={{ width: 28, textAlign: "right" }}>
                            {factor.known ? factor.score : "—"}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell align="right">{factor.weight}%</TableCell>
                      <TableCell>
                        <Typography variant="body2" color={factor.known ? "text.primary" : "text.secondary"}>
                          {factor.known ? factor.explanation : `No data: ${factor.explanation}`}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>

          <Divider sx={{ my: 2 }} />

          <Typography variant="subtitle2" mb={1}>
            Risks ({result.risks.length})
          </Typography>
          {result.risks.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              No risks were identified from the extracted facts.
            </Typography>
          )}
          <Stack spacing={1.5}>
            {result.risks.map((risk, i) => (
              <Stack key={`${risk.risk}-${i}`} direction="row" spacing={1.5} alignItems="flex-start">
                <Chip
                  size="small"
                  color={SEVERITY_COLOR[risk.severity]}
                  label={risk.severity}
                  sx={{ textTransform: "capitalize", width: 72 }}
                />
                <Box flexGrow={1} minWidth={0}>
                  <Typography variant="body2" fontWeight={600}>
                    {risk.risk}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {risk.explanation}
                  </Typography>
                  {risk.evidence && risk.document_id && risk.file_name && (
                    <Stack direction="row" spacing={1} alignItems="center" mt={0.5} flexWrap="wrap" useFlexGap>
                      <Typography variant="body2" color="text.secondary" fontStyle="italic">
                        “{risk.evidence}”
                      </Typography>
                      <Chip
                        size="small"
                        clickable
                        onClick={() => openSource(risk.document_id!, risk.file_name!)}
                        label={`${risk.file_name} · p.${risk.page}`}
                        title="Download the source document"
                      />
                    </Stack>
                  )}
                </Box>
              </Stack>
            ))}
          </Stack>
        </>
      )}
    </Box>
  );
}
