import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnalysisPanel } from "@/components/AnalysisPanel";
import { analysisService } from "@/services/analysisService";
import type { TenderAnalysisResponse } from "@/types/analysis";

vi.mock("@/services/analysisService", () => ({
  analysisService: { get: vi.fn(), run: vi.fn() },
}));
vi.mock("@/services/documentService", () => ({
  documentService: { download: vi.fn() },
}));

const citation = { document_id: "doc-1", file_name: "RFP.pdf", page_number: 27 };

const analysed: TenderAnalysisResponse = {
  tender_id: "t-1",
  analysis: {
    status: "done",
    summary: {
      project: "Integrated Citizen Services Portal",
      overview: "Portal build.",
      contract_duration: "36 months [R1]",
      core_requirements: ["PostgreSQL [R1]"],
      manpower: [],
      eligibility_highlights: ["₹10 Cr average turnover [E1]"],
      msme_provisions: [],
      points_to_review: [],
      categories: [],
      fact_refs: { R1: "r-1", E1: "e-1" },
    },
    run_stats: { dropped_unverified: 2 },
    documents_analysed: 1,
    generated_by_model: "claude-opus-5-5",
    started_at: "2026-10-04T10:00:00Z",
    finished_at: "2026-10-04T10:02:00Z",
    error: null,
  },
  requirements: [
    {
      id: "r-1",
      category: "technology",
      summary: "PostgreSQL database",
      requirement_text: "The solution shall use PostgreSQL as the database.",
      details: { technologies: ["PostgreSQL"] },
      citation,
      generated_by_model: "claude-opus-5-5",
    },
  ],
  eligibility: [
    {
      id: "e-1",
      criterion_type: "turnover",
      summary: "Average turnover ₹10 Cr",
      criterion_text: "Average annual turnover of at least Rs. 10 Crore.",
      extracted_value: { amount_inr: 100000000 },
      citation,
      generated_by_model: "claude-opus-5-5",
    },
  ],
};

describe("AnalysisPanel", () => {
  it("labels the summary as AI interpretation and the clauses as cited facts", async () => {
    vi.mocked(analysisService.get).mockResolvedValue(analysed);

    render(<AnalysisPanel tenderId="t-1" canRun onAnalysisChanged={() => {}} />);

    expect(await screen.findByText("AI INTERPRETATION")).toBeInTheDocument();
    expect(screen.getByText("FACT")).toBeInTheDocument();
    expect(screen.getByText("Integrated Citizen Services Portal")).toBeInTheDocument();
    expect(screen.getAllByText("RFP.pdf · p.27")).toHaveLength(2);
    expect(screen.getByText(/2 extracted item\(s\) were discarded/)).toBeInTheDocument();
    expect(screen.getByText("amount inr: ₹10,00,00,000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /re-run analysis/i })).toBeInTheDocument();
  });

  it("shows the failure reason and hides the run button for read-only users", async () => {
    vi.mocked(analysisService.get).mockResolvedValue({
      tender_id: "t-1",
      analysis: { ...analysed.analysis!, status: "failed", summary: null, error: "ANTHROPIC_API_KEY is not set" },
      requirements: [],
      eligibility: [],
    });

    render(<AnalysisPanel tenderId="t-1" canRun={false} onAnalysisChanged={() => {}} />);

    expect(await screen.findByText(/ANTHROPIC_API_KEY is not set/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /analysis/i })).not.toBeInTheDocument();
  });
});
