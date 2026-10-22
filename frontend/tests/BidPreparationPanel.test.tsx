import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { BidPreparationPanel } from "@/components/BidPreparationPanel";
import { bidService } from "@/services/opportunityService";
import type { BidPreparation } from "@/types/opportunity";

vi.mock("@/services/opportunityService", () => ({
  bidService: {
    get: vi.fn(),
    generateDraft: vi.fn(),
    syncChecklist: vi.fn(),
    addItem: vi.fn(),
    updateItem: vi.fn(() => Promise.resolve({})),
    deleteItem: vi.fn(),
    downloadDraft: vi.fn(),
    downloadChecklist: vi.fn(),
    downloadPack: vi.fn(),
  },
}));
vi.mock("@/services/documentService", () => ({ documentService: { download: vi.fn() } }));

const citation = { document_id: "doc-1", file_name: "RFP.pdf", page_number: 3 };

const prep: BidPreparation = {
  opportunity_id: "o-1",
  tender_id: "t-1",
  tender_analysed: true,
  profile_configured: true,
  can_prepare: true,
  can_edit_checklist: true,
  checklist: [
    {
      id: "c-1",
      position: 1,
      title: "ISO 27001 certificate",
      kind: "certificate",
      mandatory: true,
      format_instructions: null,
      form_reference: null,
      source_clause: "Copy of valid ISO 27001 certificate.",
      source_document_id: "doc-1",
      source_file_name: "RFP.pdf",
      source_page: 4,
      is_manual: false,
      status: "available",
      status_set_by_user: false,
      prefill_reason: "ISO 27001 recorded in the company profile",
      owner: null,
      note: null,
    },
    {
      id: "c-2",
      position: 2,
      title: "Self-declaration of not being blacklisted",
      kind: "declaration",
      mandatory: true,
      format_instructions: "On the bidder's letterhead",
      form_reference: "Annexure 3",
      source_clause: "Self-declaration ... as per Annexure 3.",
      source_document_id: "doc-1",
      source_file_name: "RFP.pdf",
      source_page: 4,
      is_manual: false,
      status: "to_prepare",
      status_set_by_user: false,
      prefill_reason: null,
      owner: null,
      note: null,
    },
  ],
  latest_draft: {
    id: "d-1",
    version: 2,
    generated_by_model: "claude-opus-5-5",
    created_by: { id: "u-1", full_name: "Sales Person", email: "s@x" },
    created_at: "2026-10-22T10:00:00Z",
    placeholders: [{ section: "covering letter", text: "[TO FILL: date]" }],
    content: {
      disclaimer: "AI DRAFT — review before use.",
      generated_at: "2026-10-22T10:00:00Z",
      generated_by_model: "claude-opus-5-5",
      covering_letter: "We submit our bid.\n[TO FILL: date]",
      company_overview: "Turnover of ₹12 Cr.",
      eligibility_compliance: [{ ref: "E1", criterion: "Average turnover ₹10 Cr", assessment: "MET", statement: "₹12 Cr average.", citation }],
      technical_compliance: [{ ref: "R1", requirement: "PostgreSQL", response: "[TO FILL: compliance response]", citation }],
      manpower_plan: [],
      relevant_projects: [],
      assumptions: [],
    },
  },
  draft_versions: [
    { id: "d-1", version: 2, created_at: "2026-10-22T10:00:00Z", created_by: null, placeholder_count: 2 },
    { id: "d-0", version: 1, created_at: "2026-10-21T10:00:00Z", created_by: null, placeholder_count: 3 },
  ],
};

function renderPanel(props: Partial<Parameters<typeof BidPreparationPanel>[0]> = {}) {
  return render(
    <MemoryRouter>
      <BidPreparationPanel opportunityId="o-1" tenderId="t-1" {...props} />
    </MemoryRouter>,
  );
}

describe("BidPreparationPanel", () => {
  it("shows the cited checklist, the labelled draft with highlighted placeholders, and downloads", async () => {
    vi.mocked(bidService.get).mockResolvedValue(prep);

    renderPanel();

    expect(await screen.findByText("Documents to submit (2)")).toBeInTheDocument();
    expect(screen.getAllByText("RFP.pdf · p.4")).toHaveLength(2);
    expect(screen.getByText("Pre-filled: ISO 27001 recorded in the company profile")).toBeInTheDocument();
    expect(screen.getByText("Annexure 3 · On the bidder's letterhead")).toBeInTheDocument();
    expect(screen.getByText("AI DRAFT")).toBeInTheDocument();
    expect(screen.getByText(/1 item\(s\) are marked \[TO FILL\]/)).toBeInTheDocument();
    const mark = screen.getByText("[TO FILL: compliance response]");
    expect(mark.tagName).toBe("MARK");
    expect(screen.getByRole("button", { name: "v1" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /bid pack/i }));
    expect(bidService.downloadPack).toHaveBeenCalledWith("o-1");
  });

  it("saves a status change", async () => {
    vi.mocked(bidService.get).mockResolvedValue(prep);
    renderPanel();

    const select = await screen.findByLabelText("Status of Self-declaration of not being blacklisted");
    fireEvent.mouseDown(select);
    fireEvent.click(within(await screen.findByRole("listbox")).getByText("Missing"));

    expect(bidService.updateItem).toHaveBeenCalledWith("o-1", "c-2", { status: "missing" });
  });

  it("explains why a draft was rejected", async () => {
    vi.mocked(bidService.get).mockResolvedValue({ ...prep, latest_draft: null, draft_versions: [] });

    renderPanel({
      initialDraftError: {
        message: "The generated draft was rejected: 1 unsupported statement(s)",
        problems: ["company overview: amount ₹50 Cr is not in the tender facts or company profile"],
      },
    });

    expect(await screen.findByText(/amount ₹50 Cr is not in the tender facts/)).toBeInTheDocument();
    expect(screen.getByText(/so it was not saved/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /draft bid \(\.docx\)/i })).toBeDisabled();
  });

  it("is read-only for users who can't edit", async () => {
    vi.mocked(bidService.get).mockResolvedValue({ ...prep, can_prepare: false, can_edit_checklist: false });
    renderPanel();

    expect(await screen.findByText("Documents to submit (2)")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Status of/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /regenerate draft/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /checklist \(\.xlsx\)/i })).toBeEnabled();
  });
});
