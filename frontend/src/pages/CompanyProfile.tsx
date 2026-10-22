import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
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
import { type ReactNode, useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { useAuth } from "@/hooks/useAuth";
import { AppLayout } from "@/layouts/AppLayout";
import { profileService } from "@/services/profileService";
import {
  CUSTOMER_TYPE_LABELS,
  type Capability,
  type CompanyProfileResponse,
  type CustomerType,
  type ExperienceRecord,
} from "@/types/profile";
import { TENDER_CATEGORY_LABELS, type TenderCategoryValue } from "@/types/tender";
import { formatCurrency } from "@/utils/format";

const CRORE = 10_000_000;
const CATEGORIES = Object.keys(TENDER_CATEGORY_LABELS).filter((c) => c !== "other") as TenderCategoryValue[];
const CUSTOMER_TYPES = Object.keys(CUSTOMER_TYPE_LABELS) as CustomerType[];

// ------------------------------------------------------------- helpers

type TriState = "yes" | "no" | "unknown";
const toTri = (v: boolean | null): TriState => (v === null ? "unknown" : v ? "yes" : "no");
const fromTri = (v: TriState): boolean | null => (v === "unknown" ? null : v === "yes");

const splitList = (text: string): string[] =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

/** "" → null; otherwise the number of rupees for an amount typed in crore. */
const croreToInr = (text: string): number | null => (text.trim() === "" ? null : Math.round(Number(text) * CRORE));
const inrToCrore = (value: string | number | null): string => (value === null ? "" : String(Number(value) / CRORE));
const intOrNull = (text: string): number | null => (text.trim() === "" ? null : Number.parseInt(text, 10));

function apiError(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  }
  return fallback;
}

function Card({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2} mb={2}>
        <Box>
          <Typography variant="h6">{title}</Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions}
      </Stack>
      {children}
    </Paper>
  );
}

// ------------------------------------------------------- company details

interface DetailsForm {
  company_name: string;
  msme_registered: TriState;
  msme_certificate_ref: string;
  startup_registered: TriState;
  startup_certificate_ref: string;
  net_worth_cr: string;
  years_in_business: string;
  employee_count: string;
  locations: string;
  certifications: string;
  turnover: { financial_year: string; amount_cr: string }[];
}

function toForm(data: CompanyProfileResponse): DetailsForm {
  const p = data.profile;
  return {
    company_name: p?.company_name ?? "",
    msme_registered: toTri(p?.msme_registered ?? null),
    msme_certificate_ref: p?.msme_certificate_ref ?? "",
    startup_registered: toTri(p?.startup_registered ?? null),
    startup_certificate_ref: p?.startup_certificate_ref ?? "",
    net_worth_cr: inrToCrore(p?.net_worth_inr ?? null),
    years_in_business: p?.years_in_business?.toString() ?? "",
    employee_count: p?.employee_count?.toString() ?? "",
    locations: p?.locations.join(", ") ?? "",
    certifications: p?.certifications.join(", ") ?? "",
    turnover: p?.turnover_by_year.map((y) => ({ financial_year: y.financial_year, amount_cr: inrToCrore(y.amount_inr) })) ?? [],
  };
}

function DetailsCard({ data, canEdit, onSaved }: { data: CompanyProfileResponse; canEdit: boolean; onSaved: () => void }) {
  const [form, setForm] = useState<DetailsForm>(() => toForm(data));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => setForm(toForm(data)), [data]);

  const set = <K extends keyof DetailsForm>(key: K, value: DetailsForm[K]) => {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: value }));
  };

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      await profileService.save({
        company_name: form.company_name,
        msme_registered: fromTri(form.msme_registered),
        msme_certificate_ref: form.msme_certificate_ref || null,
        startup_registered: fromTri(form.startup_registered),
        startup_certificate_ref: form.startup_certificate_ref || null,
        net_worth_inr: croreToInr(form.net_worth_cr)?.toString() ?? null,
        years_in_business: intOrNull(form.years_in_business),
        employee_count: intOrNull(form.employee_count),
        locations: splitList(form.locations),
        certifications: splitList(form.certifications),
        turnover_by_year: form.turnover
          .filter((y) => y.financial_year && y.amount_cr !== "")
          .map((y) => ({ financial_year: y.financial_year.trim(), amount_inr: croreToInr(y.amount_cr)! })),
      });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(apiError(err, "Could not save the profile."));
    } finally {
      setSaving(false);
    }
  };

  const ro = !canEdit;
  const triSelect = (label: string, key: "msme_registered" | "startup_registered") => (
    <TextField label={label} select value={form[key]} onChange={(e) => set(key, e.target.value as TriState)} fullWidth disabled={ro}>
      <MenuItem value="yes">Yes</MenuItem>
      <MenuItem value="no">No</MenuItem>
      <MenuItem value="unknown">Not recorded</MenuItem>
    </TextField>
  );

  return (
    <Card
      title="Company details"
      subtitle="Leave a field empty when it isn't known. Matching then reports the criterion as unknown instead of guessing."
      actions={
        canEdit && (
          <Button variant="contained" onClick={handleSave} disabled={!form.company_name || saving}>
            {data.profile ? "Save changes" : "Create profile"}
          </Button>
        )
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {saved && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Saved. Existing qualification results are now marked out of date until recomputed.
        </Alert>
      )}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <TextField label="Company name" value={form.company_name} onChange={(e) => set("company_name", e.target.value)} fullWidth required disabled={ro} />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField label="Years in business" type="number" value={form.years_in_business} onChange={(e) => set("years_in_business", e.target.value)} fullWidth disabled={ro} />
        </Grid>
        <Grid item xs={6} md={3}>
          <TextField label="Employees" type="number" value={form.employee_count} onChange={(e) => set("employee_count", e.target.value)} fullWidth disabled={ro} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {triSelect("MSME (Udyam) registered", "msme_registered")}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <TextField label="Udyam / NSIC number" value={form.msme_certificate_ref} onChange={(e) => set("msme_certificate_ref", e.target.value)} fullWidth disabled={ro} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          {triSelect("DPIIT startup recognised", "startup_registered")}
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <TextField label="DPIIT certificate number" value={form.startup_certificate_ref} onChange={(e) => set("startup_certificate_ref", e.target.value)} fullWidth disabled={ro} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <TextField label="Net worth (₹ Cr)" type="number" value={form.net_worth_cr} onChange={(e) => set("net_worth_cr", e.target.value)} fullWidth disabled={ro} />
        </Grid>
        <Grid item xs={12} sm={6} md={9}>
          <TextField
            label="Operating locations (states)"
            value={form.locations}
            onChange={(e) => set("locations", e.target.value)}
            helperText='Comma-separated, e.g. "Punjab, Haryana". Use "Pan India" to match any delivery state.'
            fullWidth
            disabled={ro}
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label="Company certifications"
            value={form.certifications}
            onChange={(e) => set("certifications", e.target.value)}
            helperText='Comma-separated, e.g. "ISO 27001, ISO 9001, CMMI Level 3, CERT-In empanelled".'
            fullWidth
            disabled={ro}
          />
        </Grid>
      </Grid>

      <Typography variant="subtitle2" mt={3} mb={1}>
        Annual turnover
      </Typography>
      <Stack spacing={1}>
        {form.turnover.map((row, i) => (
          <Stack key={i} direction="row" spacing={1} alignItems="center">
            <TextField
              label="Financial year"
              placeholder="2024-25"
              size="small"
              value={row.financial_year}
              onChange={(e) => set("turnover", form.turnover.map((r, j) => (j === i ? { ...r, financial_year: e.target.value } : r)))}
              disabled={ro}
            />
            <TextField
              label="Turnover (₹ Cr)"
              type="number"
              size="small"
              value={row.amount_cr}
              onChange={(e) => set("turnover", form.turnover.map((r, j) => (j === i ? { ...r, amount_cr: e.target.value } : r)))}
              disabled={ro}
            />
            {canEdit && (
              <IconButton aria-label="remove year" onClick={() => set("turnover", form.turnover.filter((_, j) => j !== i))}>
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            )}
          </Stack>
        ))}
        {form.turnover.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No turnover recorded.
          </Typography>
        )}
        {canEdit && (
          <Box>
            <Button size="small" startIcon={<AddIcon />} onClick={() => set("turnover", [...form.turnover, { financial_year: "", amount_cr: "" }])}>
              Add year
            </Button>
          </Box>
        )}
      </Stack>
    </Card>
  );
}

// --------------------------------------------------------- capabilities

interface CapabilityForm {
  capability: TenderCategoryValue;
  technologies: string;
  certifications: string;
  description: string;
}

function CapabilitiesCard({ items, canEdit, onChanged }: { items: Capability[]; canEdit: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState<Capability | "new" | null>(null);
  const [form, setForm] = useState<CapabilityForm>({ capability: "software_development", technologies: "", certifications: "", description: "" });
  const [error, setError] = useState<string | null>(null);

  const open = (item: Capability | "new") => {
    setError(null);
    setEditing(item);
    const unused = CATEGORIES.find((c) => !items.some((i) => i.capability === c)) ?? "software_development";
    setForm(
      item === "new"
        ? { capability: unused, technologies: "", certifications: "", description: "" }
        : {
            capability: item.capability,
            technologies: item.technologies.join(", "),
            certifications: item.certifications.join(", "),
            description: item.description ?? "",
          },
    );
  };

  const save = async () => {
    const payload = {
      technologies: splitList(form.technologies),
      certifications: splitList(form.certifications),
      description: form.description || null,
    };
    try {
      if (editing === "new") await profileService.addCapability({ capability: form.capability, ...payload });
      else if (editing) await profileService.updateCapability(editing.id, payload);
      setEditing(null);
      onChanged();
    } catch (err) {
      setError(apiError(err, "Could not save the capability."));
    }
  };

  const remove = async (item: Capability) => {
    if (!window.confirm(`Remove the ${TENDER_CATEGORY_LABELS[item.capability]} capability?`)) return;
    await profileService.deleteCapability(item.id);
    onChanged();
  };

  return (
    <Card
      title="Capabilities"
      subtitle="Focus areas the company delivers in. These are compared with each tender's categories and named technologies."
      actions={
        canEdit && (
          <Button startIcon={<AddIcon />} onClick={() => open("new")} disabled={items.length >= CATEGORIES.length}>
            Add capability
          </Button>
        )
      }
    >
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Capability</TableCell>
              <TableCell>Technologies</TableCell>
              <TableCell>Certifications</TableCell>
              {canEdit && <TableCell />}
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{TENDER_CATEGORY_LABELS[item.capability]}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {item.technologies.map((t) => (
                      <Chip key={t} size="small" variant="outlined" label={t} />
                    ))}
                  </Stack>
                </TableCell>
                <TableCell>{item.certifications.join(", ") || "—"}</TableCell>
                {canEdit && (
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    <Tooltip title="Edit">
                      <IconButton size="small" aria-label="edit capability" onClick={() => open(item)}>
                        <EditOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Remove">
                      <IconButton size="small" aria-label="remove capability" onClick={() => remove(item)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                )}
              </TableRow>
            ))}
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={4}>
                  <Typography variant="body2" color="text.secondary">
                    No capabilities recorded.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="sm">
        <DialogTitle>{editing === "new" ? "Add capability" : "Edit capability"}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Capability"
              select
              value={form.capability}
              onChange={(e) => setForm({ ...form, capability: e.target.value as TenderCategoryValue })}
              disabled={editing !== "new"}
              fullWidth
            >
              {CATEGORIES.map((c) => (
                <MenuItem key={c} value={c} disabled={editing === "new" && items.some((i) => i.capability === c)}>
                  {TENDER_CATEGORY_LABELS[c]}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Technologies"
              value={form.technologies}
              onChange={(e) => setForm({ ...form, technologies: e.target.value })}
              helperText='Comma-separated, e.g. "Python, React, PostgreSQL".'
              fullWidth
            />
            <TextField
              label="Certifications for this area"
              value={form.certifications}
              onChange={(e) => setForm({ ...form, certifications: e.target.value })}
              helperText="Comma-separated. Optional."
              fullWidth
            />
            <TextField label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} multiline minRows={2} fullWidth />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(null)}>Cancel</Button>
          <Button variant="contained" onClick={save}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

// ----------------------------------------------------------- experience

interface ExperienceForm {
  project_name: string;
  client_name: string;
  customer_type: CustomerType;
  capability: TenderCategoryValue | "";
  industry: string;
  technologies: string;
  value_cr: string;
  year: string;
  description: string;
}

const EMPTY_EXPERIENCE: ExperienceForm = {
  project_name: "",
  client_name: "",
  customer_type: "government",
  capability: "",
  industry: "",
  technologies: "",
  value_cr: "",
  year: "",
  description: "",
};

function ExperienceCard({ items, canEdit, onChanged }: { items: ExperienceRecord[]; canEdit: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState<ExperienceRecord | "new" | null>(null);
  const [form, setForm] = useState<ExperienceForm>(EMPTY_EXPERIENCE);
  const [error, setError] = useState<string | null>(null);

  const open = (item: ExperienceRecord | "new") => {
    setError(null);
    setEditing(item);
    setForm(
      item === "new"
        ? EMPTY_EXPERIENCE
        : {
            project_name: item.project_name,
            client_name: item.client_name ?? "",
            customer_type: item.customer_type,
            capability: item.capability ?? "",
            industry: item.industry ?? "",
            technologies: item.technologies.join(", "),
            value_cr: inrToCrore(item.project_value_inr),
            year: item.year?.toString() ?? "",
            description: item.description ?? "",
          },
    );
  };

  const save = async () => {
    const payload = {
      project_name: form.project_name,
      client_name: form.client_name || null,
      customer_type: form.customer_type,
      capability: form.capability || null,
      industry: form.industry || null,
      technologies: splitList(form.technologies),
      project_value_inr: croreToInr(form.value_cr)?.toString() ?? null,
      year: intOrNull(form.year),
      description: form.description || null,
    };
    try {
      if (editing === "new") await profileService.addExperience(payload);
      else if (editing) await profileService.updateExperience(editing.id, payload);
      setEditing(null);
      onChanged();
    } catch (err) {
      setError(apiError(err, "Could not save the project."));
    }
  };

  const remove = async (item: ExperienceRecord) => {
    if (!window.confirm(`Remove "${item.project_name}"?`)) return;
    await profileService.deleteExperience(item.id);
    onChanged();
  };

  return (
    <Card
      title="Past projects"
      subtitle="Completed work used for the similar-project and government-experience checks. Projects without a value or a capability can't confirm a criterion."
      actions={
        canEdit && (
          <Button startIcon={<AddIcon />} onClick={() => open("new")}>
            Add project
          </Button>
        )
      }
    >
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Project</TableCell>
              <TableCell>Client</TableCell>
              <TableCell>Capability</TableCell>
              <TableCell align="right">Value</TableCell>
              <TableCell align="right">Year</TableCell>
              {canEdit && <TableCell />}
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <Typography variant="body2" fontWeight={500}>
                    {item.project_name}
                  </Typography>
                  {item.technologies.length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      {item.technologies.join(", ")}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  {item.client_name ?? "—"}
                  <Chip size="small" label={CUSTOMER_TYPE_LABELS[item.customer_type]} sx={{ ml: 1 }} />
                </TableCell>
                <TableCell>{item.capability ? TENDER_CATEGORY_LABELS[item.capability] : <Typography variant="body2" color="warning.main">Not set</Typography>}</TableCell>
                <TableCell align="right">{formatCurrency(item.project_value_inr, "Not recorded")}</TableCell>
                <TableCell align="right">{item.year ?? "—"}</TableCell>
                {canEdit && (
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    <Tooltip title="Edit">
                      <IconButton size="small" aria-label="edit project" onClick={() => open(item)}>
                        <EditOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Remove">
                      <IconButton size="small" aria-label="remove project" onClick={() => remove(item)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                )}
              </TableRow>
            ))}
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography variant="body2" color="text.secondary">
                    No past projects recorded.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} fullWidth maxWidth="sm">
        <DialogTitle>{editing === "new" ? "Add past project" : "Edit past project"}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} mt={0}>
            {error && (
              <Grid item xs={12}>
                <Alert severity="error">{error}</Alert>
              </Grid>
            )}
            <Grid item xs={12}>
              <TextField label="Project name" value={form.project_name} onChange={(e) => setForm({ ...form, project_name: e.target.value })} fullWidth required autoFocus />
            </Grid>
            <Grid item xs={12} sm={7}>
              <TextField label="Client" value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })} fullWidth />
            </Grid>
            <Grid item xs={12} sm={5}>
              <TextField label="Client type" select value={form.customer_type} onChange={(e) => setForm({ ...form, customer_type: e.target.value as CustomerType })} fullWidth>
                {CUSTOMER_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {CUSTOMER_TYPE_LABELS[t]}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={7}>
              <TextField
                label="Counts as experience in"
                select
                value={form.capability}
                onChange={(e) => setForm({ ...form, capability: e.target.value as TenderCategoryValue | "" })}
                fullWidth
              >
                <MenuItem value="">Not set</MenuItem>
                {CATEGORIES.map((c) => (
                  <MenuItem key={c} value={c}>
                    {TENDER_CATEGORY_LABELS[c]}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={5}>
              <TextField label="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} fullWidth />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Value (₹ Cr)" type="number" value={form.value_cr} onChange={(e) => setForm({ ...form, value_cr: e.target.value })} fullWidth />
            </Grid>
            <Grid item xs={6}>
              <TextField label="Completion year" type="number" value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} fullWidth />
            </Grid>
            <Grid item xs={12}>
              <TextField label="Technologies" value={form.technologies} onChange={(e) => setForm({ ...form, technologies: e.target.value })} helperText="Comma-separated." fullWidth />
            </Grid>
            <Grid item xs={12}>
              <TextField label="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} multiline minRows={2} fullWidth />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(null)}>Cancel</Button>
          <Button variant="contained" onClick={save} disabled={!form.project_name}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
}

// ----------------------------------------------------------------- page

export function CompanyProfile() {
  const { user } = useAuth();
  const [data, setData] = useState<CompanyProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canEdit = user?.role.name === "admin";

  const refresh = useCallback(() => {
    profileService
      .get()
      .then(setData)
      .catch(() => setError("Could not load the company profile."));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AppLayout>
      <PageHeader
        eyebrow="Matching"
        title="Company Profile"
        subtitle="What every tender is qualified against: turnover, certifications, capabilities and past projects."
      />
      {!canEdit && (
        <Alert severity="info" sx={{ mb: 3 }}>
          Only admins can edit the company profile.
        </Alert>
      )}
      {error && <Alert severity="error">{error}</Alert>}
      {!data && !error && <Skeleton variant="rounded" height={320} />}
      {data && (
        <>
          <DetailsCard data={data} canEdit={canEdit} onSaved={refresh} />
          {data.profile ? (
            <>
              <CapabilitiesCard items={data.capabilities} canEdit={canEdit} onChanged={refresh} />
              <ExperienceCard items={data.experience} canEdit={canEdit} onChanged={refresh} />
            </>
          ) : (
            <Alert severity="info">
              {canEdit ? "Create the profile above, then add capabilities and past projects." : "The company profile has not been set up yet."}
            </Alert>
          )}
        </>
      )}
    </AppLayout>
  );
}
