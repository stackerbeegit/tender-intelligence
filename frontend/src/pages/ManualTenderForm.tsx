import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import {
  Alert,
  Button,
  Checkbox,
  Divider,
  FormControlLabel,
  Grid,
  IconButton,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { type FormEvent, useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";

import { AppLayout } from "@/layouts/AppLayout";
import { tenderService } from "@/services/tenderService";
import { TENDER_CATEGORY_LABELS, type ManualTenderCreate, type TenderCategoryValue } from "@/types/tender";

const emptyDocument = { file_name: "", source_url: "" };
const emptyLocation = { state: "", city: "" };

export function ManualTenderForm() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [tenderNumber, setTenderNumber] = useState("");
  const [organisationName, setOrganisationName] = useState("");
  const [url, setUrl] = useState("");
  const [publishedDate, setPublishedDate] = useState("");
  const [closingDate, setClosingDate] = useState("");
  const [tenderValue, setTenderValue] = useState("");
  const [emdAmount, setEmdAmount] = useState("");
  const [categories, setCategories] = useState<Record<TenderCategoryValue, boolean>>(
    {} as Record<TenderCategoryValue, boolean>,
  );
  const [locations, setLocations] = useState([{ ...emptyLocation }]);
  const [documents, setDocuments] = useState([{ ...emptyDocument }]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const payload: ManualTenderCreate = {
      title,
      tender_number: tenderNumber || null,
      organisation_name: organisationName || null,
      url: url || null,
      published_date: publishedDate || null,
      closing_date: closingDate ? new Date(closingDate).toISOString() : null,
      tender_value: tenderValue || null,
      emd_amount: emdAmount || null,
      locations: locations.filter((l) => l.state || l.city),
      categories: Object.entries(categories)
        .filter(([, checked]) => checked)
        .map(([value]) => value as TenderCategoryValue),
      documents: documents.filter((d) => d.file_name).map((d) => ({ file_name: d.file_name, source_url: d.source_url || undefined })),
    };

    try {
      const created = await tenderService.createManual(payload);
      navigate(`/tenders/${created.id}`);
    } catch {
      setError("Could not save this tender. Check the required fields and try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppLayout>
      <Button component={RouterLink} to="/tenders" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>
        Back to tenders
      </Button>

      <Typography variant="h5" fontWeight={600} mb={1}>
        Add Tender Manually
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={3}>
        For tenders from a source without an automated connector yet — e.g. a document emailed to you, or a portal
        page without a verified access path. This does not scrape or bypass any portal's access controls.
      </Typography>

      <Paper variant="outlined" sx={{ p: 3 }} component="form" onSubmit={handleSubmit}>
        <Stack spacing={3}>
          {error && <Alert severity="error">{error}</Alert>}

          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                label="Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField label="Tender Number" value={tenderNumber} onChange={(e) => setTenderNumber(e.target.value)} fullWidth />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField label="Source URL" value={url} onChange={(e) => setUrl(e.target.value)} fullWidth />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField label="Organisation" value={organisationName} onChange={(e) => setOrganisationName(e.target.value)} fullWidth />
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField label="Tender Value (₹)" value={tenderValue} onChange={(e) => setTenderValue(e.target.value)} fullWidth />
            </Grid>
            <Grid item xs={12} sm={3}>
              <TextField label="EMD Amount (₹)" value={emdAmount} onChange={(e) => setEmdAmount(e.target.value)} fullWidth />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Published Date"
                type="date"
                value={publishedDate}
                onChange={(e) => setPublishedDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Closing Date & Time"
                type="datetime-local"
                value={closingDate}
                onChange={(e) => setClosingDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
            </Grid>
          </Grid>

          <Divider />
          <Typography variant="subtitle1" fontWeight={600}>
            Categories
          </Typography>
          <Grid container>
            {(Object.entries(TENDER_CATEGORY_LABELS) as [TenderCategoryValue, string][]).map(([value, label]) => (
              <Grid item xs={12} sm={6} md={4} key={value}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={Boolean(categories[value])}
                      onChange={(e) => setCategories((prev) => ({ ...prev, [value]: e.target.checked }))}
                    />
                  }
                  label={label}
                />
              </Grid>
            ))}
          </Grid>

          <Divider />
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1" fontWeight={600}>
              Locations
            </Typography>
            <Button size="small" onClick={() => setLocations((prev) => [...prev, { ...emptyLocation }])}>
              Add location
            </Button>
          </Stack>
          {locations.map((loc, index) => (
            <Stack direction="row" spacing={2} key={index} alignItems="center">
              <TextField
                label="State"
                size="small"
                value={loc.state}
                onChange={(e) =>
                  setLocations((prev) => prev.map((l, i) => (i === index ? { ...l, state: e.target.value } : l)))
                }
                fullWidth
              />
              <TextField
                label="City"
                size="small"
                value={loc.city}
                onChange={(e) =>
                  setLocations((prev) => prev.map((l, i) => (i === index ? { ...l, city: e.target.value } : l)))
                }
                fullWidth
              />
              <IconButton onClick={() => setLocations((prev) => prev.filter((_, i) => i !== index))} aria-label="remove location">
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}

          <Divider />
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1" fontWeight={600}>
              Documents
            </Typography>
            <Button size="small" onClick={() => setDocuments((prev) => [...prev, { ...emptyDocument }])}>
              Add document
            </Button>
          </Stack>
          {documents.map((doc, index) => (
            <Stack direction="row" spacing={2} key={index} alignItems="center">
              <TextField
                label="File name"
                size="small"
                value={doc.file_name}
                onChange={(e) =>
                  setDocuments((prev) => prev.map((d, i) => (i === index ? { ...d, file_name: e.target.value } : d)))
                }
                fullWidth
              />
              <TextField
                label="Source URL"
                size="small"
                value={doc.source_url}
                onChange={(e) =>
                  setDocuments((prev) => prev.map((d, i) => (i === index ? { ...d, source_url: e.target.value } : d)))
                }
                fullWidth
              />
              <IconButton onClick={() => setDocuments((prev) => prev.filter((_, i) => i !== index))} aria-label="remove document">
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}

          <Divider />
          <Stack direction="row" spacing={2} justifyContent="flex-end">
            <Button component={RouterLink} to="/tenders" disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" variant="contained" disabled={isSubmitting || !title}>
              {isSubmitting ? "Saving…" : "Save Tender"}
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </AppLayout>
  );
}
