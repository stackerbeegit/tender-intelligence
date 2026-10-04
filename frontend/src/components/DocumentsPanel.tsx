import DescriptionIcon from "@mui/icons-material/Description";
import DownloadIcon from "@mui/icons-material/Download";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useRef, useState } from "react";

import { documentService } from "@/services/documentService";
import type { ExtractionStatus, OcrStatus, TenderDocument } from "@/types/tender";

const EXTRACTION_COLORS: Record<ExtractionStatus, "default" | "success" | "warning" | "error"> = {
  pending: "default",
  done: "success",
  failed: "error",
};

const OCR_COLORS: Record<OcrStatus, "default" | "success" | "warning" | "error"> = {
  not_required: "default",
  pending: "warning",
  done: "success",
  failed: "error",
};

const DOCUMENT_TYPES = ["nit", "rfp", "boq", "annexure", "corrigendum", "other"];

function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentsPanelProps {
  tenderId: string;
  documents: TenderDocument[];
  canManage: boolean;
  onDocumentsChanged: () => void;
}

export function DocumentsPanel({ tenderId, documents, canManage, onDocumentsChanged }: DocumentsPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [documentType, setDocumentType] = useState("other");
  const [isUploading, setIsUploading] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError(null);
    setIsUploading(true);
    try {
      await documentService.upload(tenderId, file, documentType);
      onDocumentsChanged();
    } catch {
      setError("Could not upload this file — check it's a PDF, DOCX, XLSX, or ZIP under the size limit.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleProcess = async (documentId: string) => {
    setProcessingId(documentId);
    setError(null);
    try {
      await documentService.process(tenderId, documentId);
      onDocumentsChanged();
    } catch {
      setError("Processing failed unexpectedly — check the server logs.");
    } finally {
      setProcessingId(null);
    }
  };

  const handleDownload = (doc: TenderDocument) => {
    documentService.download(tenderId, doc.id, doc.file_name);
  };

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Document download, text extraction, and OCR fallback for scanned pages.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {canManage && (
        <Stack direction="row" spacing={2} alignItems="center" mb={2}>
          <TextField
            select
            size="small"
            label="Type"
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
            sx={{ minWidth: 140 }}
          >
            {DOCUMENT_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {t.toUpperCase()}
              </MenuItem>
            ))}
          </TextField>
          <Button
            variant="outlined"
            component="label"
            size="small"
            startIcon={<UploadFileIcon />}
            disabled={isUploading}
          >
            {isUploading ? "Uploading…" : "Upload Document"}
            <input ref={fileInputRef} type="file" hidden onChange={handleUpload} />
          </Button>
        </Stack>
      )}

      <List dense>
        {documents.map((doc) => (
          <Box key={doc.id} sx={{ border: 1, borderColor: "divider", borderRadius: 1, mb: 1 }}>
            <ListItem
              secondaryAction={
                <Stack direction="row" spacing={0.5}>
                  {canManage && doc.extraction_status !== "done" && (
                    <IconButton
                      size="small"
                      aria-label="process document"
                      disabled={processingId === doc.id}
                      onClick={() => handleProcess(doc.id)}
                    >
                      <PlayArrowIcon fontSize="small" />
                    </IconButton>
                  )}
                  {doc.storage_path && (
                    <IconButton size="small" aria-label="download document" onClick={() => handleDownload(doc)}>
                      <DownloadIcon fontSize="small" />
                    </IconButton>
                  )}
                  {doc.extracted_text && (
                    <IconButton
                      size="small"
                      aria-label="toggle extracted text"
                      onClick={() => setExpandedId(expandedId === doc.id ? null : doc.id)}
                    >
                      {expandedId === doc.id ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                    </IconButton>
                  )}
                </Stack>
              }
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <DescriptionIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText
                primary={doc.file_name}
                secondary={
                  <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap">
                    <Chip label={doc.extraction_status} size="small" color={EXTRACTION_COLORS[doc.extraction_status]} />
                    {doc.ocr_status !== "not_required" && (
                      <Chip label={`ocr: ${doc.ocr_status}`} size="small" color={OCR_COLORS[doc.ocr_status]} />
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {formatBytes(doc.file_size_bytes)}
                      {doc.page_count ? ` · ${doc.page_count} page(s)` : ""}
                    </Typography>
                  </Stack>
                }
              />
            </ListItem>
            <Collapse in={expandedId === doc.id}>
              <Box sx={{ px: 2, pb: 2 }}>
                {doc.last_processing_error && (
                  <Alert severity="warning" sx={{ mb: 1 }}>
                    {doc.last_processing_error}
                  </Alert>
                )}
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: "0.75rem", maxHeight: 300, overflow: "auto" }}
                >
                  {doc.extracted_text}
                </Typography>
              </Box>
            </Collapse>
          </Box>
        ))}
        {documents.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No documents recorded.
          </Typography>
        )}
      </List>
    </Box>
  );
}
