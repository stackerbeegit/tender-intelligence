import AddIcon from "@mui/icons-material/Add";
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
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

import { AppLayout } from "@/layouts/AppLayout";
import { sourceService } from "@/services/sourceService";
import type { Source, SourceStatus, SourceType } from "@/types/tender";

const STATUS_COLORS: Record<SourceStatus, "default" | "success" | "warning" | "error"> = {
  healthy: "success",
  degraded: "warning",
  down: "error",
  disabled: "default",
};

const SOURCE_TYPES: SourceType[] = ["gem", "cppp", "state", "psu", "department", "manual", "other"];

export function SourcesAdmin() {
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<SourceType>("state");
  const [newUrl, setNewUrl] = useState("");
  const [newNotes, setNewNotes] = useState("");

  const [notesDialogSource, setNotesDialogSource] = useState<Source | null>(null);
  const [notesDraft, setNotesDraft] = useState("");

  const refresh = () => sourceService.list().then(setSources);

  useEffect(() => {
    refresh();
  }, []);

  const handleCreate = async () => {
    await sourceService.create({ name: newName, source_type: newType, url: newUrl || undefined, terms_access_notes: newNotes || undefined });
    setCreateOpen(false);
    setNewName("");
    setNewUrl("");
    setNewNotes("");
    refresh();
  };

  const handleToggleCrawler = async (source: Source) => {
    setError(null);
    try {
      await sourceService.update(source.id, { crawler_enabled: !source.crawler_enabled });
      refresh();
    } catch {
      setError(
        `Could not enable crawling for "${source.name}" — terms_access_notes must document that automated access is permitted first (Rule 11).`,
      );
    }
  };

  const openNotesDialog = (source: Source) => {
    setNotesDialogSource(source);
    setNotesDraft(source.terms_access_notes ?? "");
  };

  const saveNotes = async () => {
    if (!notesDialogSource) return;
    await sourceService.update(notesDialogSource.id, { terms_access_notes: notesDraft });
    setNotesDialogSource(null);
    refresh();
  };

  return (
    <AppLayout>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5" fontWeight={600}>
          Sources
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Add Source
        </Button>
      </Stack>

      <Typography variant="body2" color="text.secondary" mb={2}>
        A crawler can only be enabled once <code>terms_access_notes</code> documents that automated access is
        permitted for that source (Rule 11) — no portal is crawled without that check first.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Crawler Enabled</TableCell>
              <TableCell>Last Successful Crawl</TableCell>
              <TableCell>Access Notes</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sources.map((source) => (
              <TableRow key={source.id} hover>
                <TableCell>{source.name}</TableCell>
                <TableCell>
                  <Chip label={source.source_type} size="small" variant="outlined" />
                </TableCell>
                <TableCell>
                  <Chip label={source.status} size="small" color={STATUS_COLORS[source.status]} />
                </TableCell>
                <TableCell>
                  <Switch
                    checked={source.crawler_enabled}
                    disabled={source.source_type === "manual"}
                    onChange={() => handleToggleCrawler(source)}
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {source.last_successful_crawl_at ? new Date(source.last_successful_crawl_at).toLocaleString("en-IN") : "Never"}
                </TableCell>
                <TableCell>
                  <Button size="small" onClick={() => openNotesDialog(source)}>
                    {source.terms_access_notes ? "Edit notes" : "Add notes"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add Source</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="Name" value={newName} onChange={(e) => setNewName(e.target.value)} fullWidth autoFocus />
            <TextField label="Type" select value={newType} onChange={(e) => setNewType(e.target.value as SourceType)} fullWidth>
              {SOURCE_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
            <TextField label="URL" value={newUrl} onChange={(e) => setNewUrl(e.target.value)} fullWidth />
            <TextField
              label="Access / Terms Notes"
              value={newNotes}
              onChange={(e) => setNewNotes(e.target.value)}
              multiline
              minRows={3}
              fullWidth
              helperText="Document what you checked about this source's terms of use / robots policy / API availability before any crawler can be enabled for it."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!newName}>
            Create
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(notesDialogSource)} onClose={() => setNotesDialogSource(null)} fullWidth maxWidth="sm">
        <DialogTitle>Access Notes — {notesDialogSource?.name}</DialogTitle>
        <DialogContent>
          <TextField
            value={notesDraft}
            onChange={(e) => setNotesDraft(e.target.value)}
            multiline
            minRows={4}
            fullWidth
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNotesDialogSource(null)}>Cancel</Button>
          <Button variant="contained" onClick={saveNotes}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </AppLayout>
  );
}
