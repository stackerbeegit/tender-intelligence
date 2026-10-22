import AddIcon from "@mui/icons-material/Add";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import FolderZipOutlinedIcon from "@mui/icons-material/FolderZipOutlined";
import SyncIcon from "@mui/icons-material/Sync";
import TableChartOutlinedIcon from "@mui/icons-material/TableChartOutlined";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  LinearProgress,
  Link,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import axios from "axios";
import { Fragment, type ReactNode, useCallback, useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import { documentService } from "@/services/documentService";
import { bidService } from "@/services/opportunityService";
import {
  CHECKLIST_STATUS_LABELS,
  type BidPreparation,
  type ChecklistItem,
  type ChecklistStatus,
  type DraftContent,
} from "@/types/opportunity";

const STATUS_COLORS: Record<ChecklistStatus, "success" | "warning" | "error" | "default"> = {
  available: "success",
  to_prepare: "warning",
  missing: "error",
  not_applicable: "default",
};

/** Renders text with every [TO FILL: …] placeholder highlighted. */
export function WithPlaceholders({ text }: { text: string }) {
  const parts = text.split(/(\[TO FILL:[^\]]*\])/gi);
  return (
    <>
      {parts.map((part, i) =>
        /^\[TO FILL:/i.test(part) ? (
          <Box
            key={i}
            component="mark"
            sx={{ bgcolor: "warning.light", color: "text.primary", fontWeight: 600, px: 0.25, borderRadius: 0.5 }}
          >
            {part}
          </Box>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box mt={2}>
      <Typography variant="subtitle2" gutterBottom>
        {title}
      </Typography>
      {children}
    </Box>
  );
}

function DraftPreview({ content, onOpenSource }: { content: DraftContent; onOpenSource: (c: { document_id: string; file_name: string }) => void }) {
  const source = (c: { document_id: string; file_name: string; page_number: number }) => (
    <Chip size="small" clickable onClick={() => onOpenSource(c)} label={`${c.file_name} · p.${c.page_number}`} />
  );
  return (
    <Box>
      <Section title="Covering letter">
        <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
          <WithPlaceholders text={content.covering_letter} />
        </Typography>
      </Section>
      <Section title="Company profile">
        <Typography variant="body2">
          <WithPlaceholders text={content.company_overview} />
        </Typography>
      </Section>
      <Section title="Eligibility compliance">
        <Table size="small">
          <TableBody>
            {content.eligibility_compliance.map((e) => (
              <TableRow key={e.ref}>
                <TableCell sx={{ verticalAlign: "top", width: "30%" }}>{e.criterion}</TableCell>
                <TableCell sx={{ verticalAlign: "top" }}>
                  <WithPlaceholders text={e.statement} />
                </TableCell>
                <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>{source(e.citation)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>
      <Section title="Technical compliance">
        <Table size="small">
          <TableBody>
            {content.technical_compliance.map((t) => (
              <TableRow key={t.ref}>
                <TableCell sx={{ verticalAlign: "top", width: "30%" }}>{t.requirement}</TableCell>
                <TableCell sx={{ verticalAlign: "top" }}>
                  <WithPlaceholders text={t.response} />
                </TableCell>
                <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>{source(t.citation)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>
      {content.manpower_plan.length > 0 && (
        <Section title="Manpower deployment">
          <Table size="small">
            <TableBody>
              {content.manpower_plan.map((m) => (
                <TableRow key={m.ref}>
                  <TableCell sx={{ verticalAlign: "top", width: "30%" }}>
                    {m.role}
                    {m.count !== null && ` × ${m.count}`}
                    {m.min_experience_years !== null && ` (${m.min_experience_years}+ yrs)`}
                  </TableCell>
                  <TableCell sx={{ verticalAlign: "top" }}>
                    <WithPlaceholders text={m.proposed_resource} />
                  </TableCell>
                  <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>{source(m.citation)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}
      {content.assumptions.length > 0 && (
        <Section title="Assumptions and points to confirm">
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {content.assumptions.map((a) => (
              <li key={a}>
                <Typography variant="body2">
                  <WithPlaceholders text={a} />
                </Typography>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </Box>
  );
}

function ChecklistRow({
  item,
  editable,
  onChange,
  onDelete,
  onOpenSource,
}: {
  item: ChecklistItem;
  editable: boolean;
  onChange: (changes: { status?: ChecklistStatus; note?: string | null }) => void;
  onDelete: () => void;
  onOpenSource: () => void;
}) {
  const [note, setNote] = useState(item.note ?? "");
  useEffect(() => setNote(item.note ?? ""), [item.note]);

  return (
    <TableRow>
      <TableCell sx={{ verticalAlign: "top" }}>{item.position}</TableCell>
      <TableCell sx={{ verticalAlign: "top", minWidth: 240 }}>
        <Typography variant="body2" fontWeight={600}>
          {item.title}
          {item.mandatory && (
            <Chip size="small" label="Mandatory" variant="outlined" sx={{ ml: 1, height: 20 }} />
          )}
        </Typography>
        {(item.format_instructions || item.form_reference) && (
          <Typography variant="caption" color="text.secondary" display="block">
            {[item.form_reference, item.format_instructions].filter(Boolean).join(" · ")}
          </Typography>
        )}
        {item.source_clause && (
          <Typography variant="caption" color="text.secondary" fontStyle="italic" display="block" mt={0.5}>
            “{item.source_clause}”
          </Typography>
        )}
        {item.prefill_reason && !item.status_set_by_user && (
          <Typography variant="caption" color="success.main" display="block">
            Pre-filled: {item.prefill_reason}
          </Typography>
        )}
      </TableCell>
      <TableCell sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
        {item.source_page ? (
          <Chip size="small" clickable onClick={onOpenSource} label={`${item.source_file_name} · p.${item.source_page}`} />
        ) : (
          <Typography variant="caption" color="text.secondary">
            Added manually
          </Typography>
        )}
      </TableCell>
      <TableCell sx={{ verticalAlign: "top", minWidth: 150 }}>
        {editable ? (
          <TextField
            select
            size="small"
            value={item.status}
            onChange={(e) => onChange({ status: e.target.value as ChecklistStatus })}
            inputProps={{ "aria-label": `Status of ${item.title}` }}
            fullWidth
          >
            {Object.entries(CHECKLIST_STATUS_LABELS).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
        ) : (
          <Chip size="small" color={STATUS_COLORS[item.status]} label={CHECKLIST_STATUS_LABELS[item.status]} />
        )}
      </TableCell>
      <TableCell sx={{ verticalAlign: "top", minWidth: 200 }}>
        {editable ? (
          <TextField
            size="small"
            value={note}
            placeholder="Note"
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => note !== (item.note ?? "") && onChange({ note: note || null })}
            fullWidth
            multiline
            maxRows={4}
          />
        ) : (
          <Typography variant="body2">{item.note ?? "—"}</Typography>
        )}
      </TableCell>
      <TableCell sx={{ verticalAlign: "top" }}>
        {editable && item.is_manual && (
          <Tooltip title="Remove">
            <IconButton size="small" aria-label="remove item" onClick={onDelete}>
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </TableCell>
    </TableRow>
  );
}

function errorDetail(err: unknown): { message: string; problems: string[] } {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return { message: detail, problems: [] };
    if (detail && typeof detail === "object") return { message: detail.message ?? "Request failed", problems: detail.problems ?? [] };
  }
  return { message: "The request failed. Check the backend logs.", problems: [] };
}

interface BidPreparationPanelProps {
  opportunityId: string;
  tenderId: string;
  /** Outcome of a just-run "prepare bid", so its draft error can be shown. */
  initialDraftError?: { message: string; problems: string[] } | null;
}

export function BidPreparationPanel({ opportunityId, tenderId, initialDraftError = null }: BidPreparationPanelProps) {
  const [data, setData] = useState<BidPreparation | null>(null);
  const [draftError, setDraftError] = useState(initialDraftError);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [newItem, setNewItem] = useState("");

  const load = useCallback(() => {
    bidService
      .get(opportunityId)
      .then(setData)
      .catch(() => setError("Could not load the bid preparation."));
  }, [opportunityId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (label: string, action: () => Promise<unknown>) => {
    setError(null);
    setBusy(label);
    try {
      await action();
    } catch (err) {
      setError(errorDetail(err).message);
    } finally {
      setBusy(null);
      load();
    }
  };

  const regenerate = async () => {
    setDraftError(null);
    setBusy("draft");
    try {
      await bidService.generateDraft(opportunityId);
    } catch (err) {
      setDraftError(errorDetail(err));
    } finally {
      setBusy(null);
      load();
    }
  };

  const updateItem = (item: ChecklistItem, changes: { status?: ChecklistStatus; note?: string | null }) => {
    setData((d) => d && { ...d, checklist: d.checklist.map((i) => (i.id === item.id ? { ...i, ...changes } : i)) });
    bidService.updateItem(opportunityId, item.id, changes).catch(() => {
      setError(`Could not save “${item.title}”.`);
      load();
    });
  };

  const openSource = (documentId: string | null, fileName: string | null) => {
    if (documentId && fileName) void documentService.download(tenderId, documentId, fileName);
  };

  if (!data) return error ? <Alert severity="error">{error}</Alert> : <LinearProgress />;

  const draft = data.latest_draft;
  const counts = data.checklist.reduce<Record<string, number>>((acc, i) => ({ ...acc, [i.status]: (acc[i.status] ?? 0) + 1 }), {});

  return (
    <Box>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} justifyContent="space-between" mb={2}>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Button
            variant="outlined"
            startIcon={<DescriptionOutlinedIcon />}
            disabled={!draft}
            onClick={() => void bidService.downloadDraft(opportunityId)}
          >
            Draft bid (.docx)
          </Button>
          <Button
            variant="outlined"
            startIcon={<TableChartOutlinedIcon />}
            onClick={() => void bidService.downloadChecklist(opportunityId)}
          >
            Checklist (.xlsx)
          </Button>
          <Button variant="contained" startIcon={<FolderZipOutlinedIcon />} onClick={() => void bidService.downloadPack(opportunityId)}>
            Bid pack (.zip)
          </Button>
        </Stack>
        {data.can_prepare && (
          <Button
            startIcon={busy === "draft" ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
            onClick={regenerate}
            disabled={busy !== null || !data.tender_analysed || !data.profile_configured}
          >
            {draft ? "Regenerate draft" : "Write draft"}
          </Button>
        )}
      </Stack>

      {!data.tender_analysed && (
        <Alert severity="info" sx={{ mb: 2 }}>
          The tender documents haven't been analysed yet, so there is no submission checklist and no draft. Run the analysis
          on the tender page first.
        </Alert>
      )}
      {!data.profile_configured && (
        <Alert severity="info" sx={{ mb: 2 }}>
          A draft bid is written from the company profile, which hasn't been set up.{" "}
          <Link component={RouterLink} to="/profile">
            Set up the company profile
          </Link>
          .
        </Alert>
      )}
      {busy === "draft" && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Writing the draft with the AI model and checking it against the tender and profile. This can take a minute.
        </Alert>
      )}
      {draftError && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setDraftError(null)}>
          {draftError.message}
          {draftError.problems.length > 0 && (
            <>
              {" "}
              It stated things the tender and company profile don't support, so it was not saved:
              <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
                {draftError.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </>
          )}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap spacing={1}>
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>
            Documents to submit ({data.checklist.length})
          </Typography>
          <Typography variant="caption" color="text.secondary">
            From the tender's own list, each with the page it's on. Marked Available only where the company profile confirms it.
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center">
          {(Object.keys(CHECKLIST_STATUS_LABELS) as ChecklistStatus[])
            .filter((s) => counts[s])
            .map((s) => (
              <Chip key={s} size="small" color={STATUS_COLORS[s]} label={`${CHECKLIST_STATUS_LABELS[s]}: ${counts[s]}`} />
            ))}
          {data.can_edit_checklist && (
            <Tooltip title="Pick up documents found by a newer analysis (keeps your edits)">
              <IconButton size="small" aria-label="sync checklist" onClick={() => run("sync", () => bidService.syncChecklist(opportunityId))}>
                <SyncIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </Stack>

      <TableContainer sx={{ mt: 1 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell>
              <TableCell>Document</TableCell>
              <TableCell>Tender reference</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Note</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {data.checklist.map((item) => (
              <ChecklistRow
                key={item.id}
                item={item}
                editable={data.can_edit_checklist}
                onChange={(changes) => updateItem(item, changes)}
                onDelete={() => run("delete", () => bidService.deleteItem(opportunityId, item.id))}
                onOpenSource={() => openSource(item.source_document_id, item.source_file_name)}
              />
            ))}
            {data.checklist.length === 0 && (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography variant="body2" color="text.secondary">
                    No documents listed yet.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {data.can_edit_checklist && (
        <Stack direction="row" spacing={1} mt={1.5}>
          <TextField
            size="small"
            placeholder="Add a document the tender doesn't list"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            fullWidth
          />
          <Button
            startIcon={<AddIcon />}
            disabled={!newItem.trim()}
            onClick={() => run("add", async () => {
              await bidService.addItem(opportunityId, newItem.trim());
              setNewItem("");
            })}
          >
            Add
          </Button>
        </Stack>
      )}

      <Divider sx={{ my: 3 }} />

      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Typography variant="subtitle1" fontWeight={700}>
          Draft bid
        </Typography>
        {draft && <Chip size="small" color="warning" label="AI DRAFT" />}
        {draft && (
          <Typography variant="caption" color="text.secondary">
            Version {draft.version} · {new Date(draft.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
            {draft.created_by && ` · ${draft.created_by.full_name}`} · {draft.generated_by_model}
          </Typography>
        )}
      </Stack>
      {!draft && (
        <Typography variant="body2" color="text.secondary" mt={1}>
          No draft yet.
        </Typography>
      )}
      {draft && (
        <>
          <Alert severity="warning" sx={{ mt: 1 }}>
            {draft.content.disclaimer}
            {draft.placeholders.length > 0 && (
              <strong> {draft.placeholders.length} item(s) are marked [TO FILL].</strong>
            )}
          </Alert>
          <DraftPreview content={draft.content} onOpenSource={(c) => openSource(c.document_id, c.file_name)} />
          {data.draft_versions.length > 1 && (
            <Typography variant="caption" color="text.secondary" display="block" mt={2}>
              Earlier versions:{" "}
              {data.draft_versions.slice(1).map((v, i) => (
                <Fragment key={v.id}>
                  {i > 0 && ", "}
                  <Link component="button" variant="caption" onClick={() => void bidService.downloadDraft(opportunityId, v.version)}>
                    v{v.version}
                  </Link>
                </Fragment>
              ))}
            </Typography>
          )}
        </>
      )}
    </Box>
  );
}
