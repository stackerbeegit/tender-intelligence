import AssignmentTurnedInOutlinedIcon from "@mui/icons-material/AssignmentTurnedInOutlined";
import PlaylistAddIcon from "@mui/icons-material/PlaylistAdd";
import { Alert, Button, Chip, CircularProgress, Paper, Stack, Typography } from "@mui/material";
import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import { bidService, opportunityService } from "@/services/opportunityService";
import { OPPORTUNITY_STATUS_LABELS, STATUS_CHIP_COLOR, type OpportunityListItem } from "@/types/opportunity";

const CRM_ROLES = ["admin", "bd_manager", "sales"];

/** The tender page's link into the opportunity pipeline. */
export function OpportunityActions({ tenderId }: { tenderId: string }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [opportunity, setOpportunity] = useState<OpportunityListItem | null | undefined>(undefined);
  const [busy, setBusy] = useState<"prepare" | "add" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canAct = Boolean(user && CRM_ROLES.includes(user.role.name));

  useEffect(() => {
    opportunityService
      .forTender(tenderId)
      .then(setOpportunity)
      .catch(() => setOpportunity(null));
  }, [tenderId]);

  const prepare = async () => {
    setError(null);
    setBusy("prepare");
    try {
      const result = await bidService.start(tenderId);
      navigate(`/opportunities/${result.opportunity_id}?tab=bid`, {
        state: { draftError: result.draft_error ? { message: result.draft_error, problems: result.draft_problems } : null },
      });
    } catch {
      setError("Could not start bid preparation. Check the backend logs.");
      setBusy(null);
    }
  };

  const addToPipeline = async () => {
    setError(null);
    setBusy("add");
    try {
      const created = await opportunityService.create(tenderId);
      navigate(`/opportunities/${created.id}`);
    } catch (err) {
      const existing = axios.isAxiosError(err) ? err.response?.data?.detail?.opportunity_id : undefined;
      if (existing) navigate(`/opportunities/${existing}`);
      else setError("Could not add this tender to the pipeline.");
      setBusy(null);
    }
  };

  if (opportunity === undefined) return null;

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }} justifyContent="space-between">
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography variant="subtitle1" fontWeight={700}>
            Pipeline
          </Typography>
          {opportunity ? (
            <Chip color={STATUS_CHIP_COLOR[opportunity.status]} label={OPPORTUNITY_STATUS_LABELS[opportunity.status]} />
          ) : (
            <Typography variant="body2" color="text.secondary">
              Not an opportunity yet.
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {opportunity && (
            <Button variant="outlined" onClick={() => navigate(`/opportunities/${opportunity.id}`)}>
              Open opportunity
            </Button>
          )}
          {canAct && !opportunity && (
            <Button
              variant="outlined"
              startIcon={busy === "add" ? <CircularProgress size={16} color="inherit" /> : <PlaylistAddIcon />}
              onClick={addToPipeline}
              disabled={busy !== null}
            >
              Add to pipeline
            </Button>
          )}
          {canAct && (
            <Button
              variant="contained"
              startIcon={busy === "prepare" ? <CircularProgress size={16} color="inherit" /> : <AssignmentTurnedInOutlinedIcon />}
              onClick={prepare}
              disabled={busy !== null}
            >
              {busy === "prepare" ? "Preparing bid pack…" : "Interested — prepare bid"}
            </Button>
          )}
        </Stack>
      </Stack>
      {busy === "prepare" && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Building the document checklist and writing a draft bid from the tender and company profile. This can take a minute.
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
    </Paper>
  );
}
