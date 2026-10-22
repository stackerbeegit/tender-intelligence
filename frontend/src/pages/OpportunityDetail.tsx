import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import axios from "axios";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useLocation, useParams } from "react-router-dom";

import { BidPreparationPanel } from "@/components/BidPreparationPanel";
import { DeadlineChip } from "@/components/DeadlineChip";
import { AppLayout } from "@/layouts/AppLayout";
import { opportunityService } from "@/services/opportunityService";
import {
  FINAL_STATUSES,
  OPPORTUNITY_PIPELINE,
  OPPORTUNITY_STATUS_LABELS,
  REASON_REQUIRED,
  STATUS_CHIP_COLOR,
  TEAM_LABELS,
  type DirectoryUser,
  type OpportunityDetail as OpportunityDetailType,
  type OpportunityStatus,
  type OpportunityTeam,
} from "@/types/opportunity";
import { formatDateTime } from "@/utils/format";

const ELIGIBILITY_LABELS = { ELIGIBLE: "Eligible", NOT_ELIGIBLE: "Not eligible", UNCERTAIN: "Uncertain" } as const;

function Card({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 2.5, height: "100%" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Typography variant="h6">{title}</Typography>
        {action}
      </Stack>
      {children}
    </Paper>
  );
}

function apiMessage(err: unknown): string {
  if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") return err.response.data.detail;
  return "The request failed.";
}

export function OpportunityDetail() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navState = (location.state ?? {}) as { draftError?: { message: string; problems: string[] } | null };
  const [opportunity, setOpportunity] = useState<OpportunityDetailType | null>(null);
  const [people, setPeople] = useState<DirectoryUser[]>([]);
  const [tab, setTab] = useState(new URLSearchParams(location.search).get("tab") === "bid" ? 1 : 0);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<OpportunityStatus | null>(null);
  const [comment, setComment] = useState("");
  const [note, setNote] = useState("");
  const [assignee, setAssignee] = useState("");
  const [team, setTeam] = useState<OpportunityTeam>("technical");

  const refresh = useCallback(() => {
    if (!id) return;
    opportunityService
      .get(id)
      .then(setOpportunity)
      .catch(() => setError("Opportunity not found."));
  }, [id]);

  useEffect(() => {
    refresh();
    opportunityService.directory().then(setPeople).catch(() => setPeople([]));
  }, [refresh]);

  const act = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(apiMessage(err));
    }
    refresh();
  };

  if (!opportunity) {
    return (
      <AppLayout>{error ? <Alert severity="error">{error}</Alert> : <Skeleton variant="rounded" height={300} />}</AppLayout>
    );
  }

  const o = opportunity;
  const isFinal = FINAL_STATUSES.includes(o.status);
  const activeStep = isFinal ? OPPORTUNITY_PIPELINE.length : OPPORTUNITY_PIPELINE.indexOf(o.status);

  const confirmTransition = () =>
    act(async () => {
      await opportunityService.transition(o.id, pending!, comment);
      setPending(null);
      setComment("");
    });

  return (
    <AppLayout>
      <Button component={RouterLink} to="/opportunities" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }} color="inherit">
        Back to opportunities
      </Button>

      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}>
          <Box minWidth={0}>
            <Stack direction="row" spacing={1} mb={1} flexWrap="wrap" useFlexGap>
              <Chip color={STATUS_CHIP_COLOR[o.status]} label={OPPORTUNITY_STATUS_LABELS[o.status]} />
              {o.created_from === "auto_relevance" && <Chip variant="outlined" size="small" label="Auto-promoted by relevance" />}
              {o.eligibility_status && <Chip variant="outlined" size="small" label={ELIGIBILITY_LABELS[o.eligibility_status]} />}
              {o.relevance_score !== null && <Chip variant="outlined" size="small" label={`Relevance ${o.relevance_score}/100`} />}
            </Stack>
            <Typography
              variant="h5"
              component={RouterLink}
              to={`/tenders/${o.tender.id}`}
              color="text.primary"
              sx={{ textDecoration: "none", wordBreak: "break-word", "&:hover": { color: "primary.main" } }}
            >
              {o.tender.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              {[o.tender.tender_number, o.tender.organisation].filter(Boolean).join(" · ") || "—"}
            </Typography>
          </Box>
          <Stack alignItems={{ md: "flex-end" }} spacing={1} flexShrink={0}>
            <DeadlineChip closing={o.tender.closing_date} size="medium" />
            <Typography variant="caption" color="text.secondary">
              Closes {formatDateTime(o.tender.closing_date)}
            </Typography>
          </Stack>
        </Stack>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Workflow & team" />
        <Tab label="Bid preparation" />
      </Tabs>

      {tab === 1 && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <BidPreparationPanel opportunityId={o.id} tenderId={o.tender.id} initialDraftError={navState.draftError ?? null} />
        </Paper>
      )}

      {tab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Card title="Workflow">
              <Box sx={{ overflowX: "auto", pb: 1 }}>
                <Stepper activeStep={activeStep} alternativeLabel sx={{ minWidth: 820 }}>
                  {OPPORTUNITY_PIPELINE.map((s) => (
                    <Step key={s}>
                      <StepLabel>{OPPORTUNITY_STATUS_LABELS[s]}</StepLabel>
                    </Step>
                  ))}
                </Stepper>
              </Box>
              {isFinal && (
                <Alert severity={o.status === "won" ? "success" : "info"} sx={{ mt: 2 }}>
                  Closed as <strong>{OPPORTUNITY_STATUS_LABELS[o.status]}</strong>.
                </Alert>
              )}
              {o.status === "bid_no_bid" && !o.can_decide && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Waiting for the bid / no-bid decision by a BD manager or admin.
                </Alert>
              )}
              {o.allowed_transitions.length > 0 && (
                <Stack direction="row" spacing={1} mt={2} flexWrap="wrap" useFlexGap>
                  <Typography variant="body2" color="text.secondary" alignSelf="center">
                    Move to:
                  </Typography>
                  {o.allowed_transitions.map((s) => (
                    <Button
                      key={s}
                      size="small"
                      variant={REASON_REQUIRED.includes(s) ? "outlined" : "contained"}
                      color={REASON_REQUIRED.includes(s) ? "error" : "primary"}
                      onClick={() => setPending(s)}
                    >
                      {OPPORTUNITY_STATUS_LABELS[s]}
                    </Button>
                  ))}
                </Stack>
              )}
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card title="Team">
              <TextField
                select
                size="small"
                label="Owner"
                value={o.owner?.id ?? ""}
                disabled={!o.can_edit}
                onChange={(e) => act(() => opportunityService.setOwner(o.id, e.target.value || null))}
                fullWidth
                sx={{ mb: 2 }}
              >
                <MenuItem value="">No owner</MenuItem>
                {people.map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.full_name} ({p.role.replace("_", " ")})
                  </MenuItem>
                ))}
              </TextField>
              <Stack spacing={1}>
                {o.assignments.map((a) => (
                  <Stack key={a.id} direction="row" alignItems="center" spacing={1}>
                    <Chip size="small" label={TEAM_LABELS[a.team]} />
                    <Typography variant="body2" flexGrow={1}>
                      {a.user.full_name}
                    </Typography>
                    {o.can_edit && (
                      <IconButton
                        size="small"
                        aria-label={`remove ${a.user.full_name}`}
                        onClick={() => act(() => opportunityService.unassign(o.id, a.id))}
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Stack>
                ))}
                {o.assignments.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    Nobody assigned yet.
                  </Typography>
                )}
              </Stack>
              {o.can_edit && (
                <Stack direction="row" spacing={1} mt={2}>
                  <TextField select size="small" label="Person" value={assignee} onChange={(e) => setAssignee(e.target.value)} sx={{ flex: 2 }}>
                    {people.map((p) => (
                      <MenuItem key={p.id} value={p.id}>
                        {p.full_name}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select
                    size="small"
                    label="Team"
                    value={team}
                    onChange={(e) => setTeam(e.target.value as OpportunityTeam)}
                    sx={{ flex: 1 }}
                  >
                    {(Object.keys(TEAM_LABELS) as OpportunityTeam[]).map((t) => (
                      <MenuItem key={t} value={t}>
                        {TEAM_LABELS[t]}
                      </MenuItem>
                    ))}
                  </TextField>
                  <Button
                    disabled={!assignee}
                    onClick={() => act(async () => {
                      await opportunityService.assign(o.id, assignee, team);
                      setAssignee("");
                    })}
                  >
                    Assign
                  </Button>
                </Stack>
              )}
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card title="Notes">
              <Stack direction="row" spacing={1} mb={2}>
                <TextField
                  size="small"
                  placeholder="Add a note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  fullWidth
                  multiline
                  maxRows={4}
                />
                <Button
                  disabled={!note.trim()}
                  onClick={() => act(async () => {
                    await opportunityService.addNote(o.id, note.trim());
                    setNote("");
                  })}
                >
                  Add
                </Button>
              </Stack>
              <Stack spacing={1.5} maxHeight={320} overflow="auto">
                {o.notes.map((n) => (
                  <Box key={n.id}>
                    <Typography variant="caption" color="text.secondary">
                      {n.author.full_name} · {formatDateTime(n.created_at)}
                    </Typography>
                    <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
                      {n.note_text}
                    </Typography>
                  </Box>
                ))}
                {o.notes.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    No notes yet.
                  </Typography>
                )}
              </Stack>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card title="Status history">
              <Stack spacing={1}>
                {[...o.history].reverse().map((h) => (
                  <Stack key={h.id} direction={{ xs: "column", sm: "row" }} spacing={{ sm: 2 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ minWidth: 150 }}>
                      {formatDateTime(h.changed_at)}
                    </Typography>
                    <Box>
                      <Typography variant="body2">
                        {h.from_status
                          ? `${OPPORTUNITY_STATUS_LABELS[h.from_status]} → ${OPPORTUNITY_STATUS_LABELS[h.to_status]}`
                          : `Created as ${OPPORTUNITY_STATUS_LABELS[h.to_status]}`}
                        <Typography component="span" variant="body2" color="text.secondary">
                          {" "}
                          by {h.changed_by?.full_name ?? "the system"}
                        </Typography>
                      </Typography>
                      {h.comment && (
                        <Typography variant="body2" color="text.secondary" fontStyle="italic">
                          {h.comment}
                        </Typography>
                      )}
                    </Box>
                  </Stack>
                ))}
              </Stack>
            </Card>
          </Grid>
        </Grid>
      )}

      <Dialog open={pending !== null} onClose={() => setPending(null)} fullWidth maxWidth="sm">
        <DialogTitle>Move to “{pending && OPPORTUNITY_STATUS_LABELS[pending]}”</DialogTitle>
        <DialogContent>
          <TextField
            label={pending && REASON_REQUIRED.includes(pending) ? "Reason (required)" : "Comment (optional)"}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            multiline
            minRows={3}
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
          />
          <Typography variant="caption" color="text.secondary">
            Recorded in the status history with your name.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPending(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={confirmTransition}
            disabled={pending !== null && REASON_REQUIRED.includes(pending) && !comment.trim()}
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
}
