import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { QualificationPanel } from "@/components/QualificationPanel";
import { qualificationService } from "@/services/qualificationService";
import type { QualificationResponse, RelevanceFactor } from "@/types/qualification";

vi.mock("@/services/qualificationService", () => ({
  qualificationService: { get: vi.fn(), compute: vi.fn() },
}));
vi.mock("@/services/documentService", () => ({
  documentService: { download: vi.fn() },
}));

const factor = (score: number, weight: number, explanation: string, known = true): RelevanceFactor => ({
  score,
  weight,
  known,
  explanation,
  evidence: [],
});

const computed: QualificationResponse = {
  tender_id: "t-1",
  profile_configured: true,
  is_stale: false,
  qualification: {
    eligibility_status: "NOT_ELIGIBLE",
    reasons: [
      {
        criterion_type: "turnover",
        outcome: "NOT_MET",
        polarity: "concern",
        text: "Turnover below requirement. Average ₹4 Cr against ₹10 Cr required.",
        evidence: {
          fact_id: "e-1",
          document_id: "doc-1",
          file_name: "RFP.pdf",
          page_number: 3,
          quote: "Average annual turnover of at least Rs. 10 Crore.",
        },
        profile_evidence: {},
      },
    ],
    relevance_score: 41,
    relevance_factors: {
      technical: factor(100, 30, "Primary category matches."),
      eligibility: factor(0, 20, "Not eligible: 0 of 1 criteria met."),
      experience: factor(50, 15, "No past projects are recorded in the company profile.", false),
      manpower: factor(100, 10, "5 resources against 120 employees."),
      commercial: factor(50, 10, "The tender value is not stated.", false),
      location: factor(100, 5, "Delivery in Punjab."),
      msme: factor(50, 5, "No MSME provisions.", false),
      deadline: factor(100, 5, "30 days left."),
    },
    risks: [
      {
        risk: "Eligibility criterion not met",
        severity: "high",
        explanation: "Turnover below requirement.",
        evidence: "Average annual turnover of at least Rs. 10 Crore.",
        fact_id: "e-1",
        document_id: "doc-1",
        file_name: "RFP.pdf",
        page: 3,
      },
    ],
    engine_version: "1.0",
    computed_at: "2026-10-20T10:00:00Z",
  },
};

function renderPanel(canCompute = true) {
  return render(
    <MemoryRouter>
      <QualificationPanel tenderId="t-1" canCompute={canCompute} />
    </MemoryRouter>,
  );
}

describe("QualificationPanel", () => {
  it("shows the verdict, cited reasons, factor breakdown and risks", async () => {
    vi.mocked(qualificationService.get).mockResolvedValue(computed);

    renderPanel();

    expect(await screen.findByText("Not eligible")).toBeInTheDocument();
    expect(screen.getByText("ASSESSMENT")).toBeInTheDocument();
    expect(screen.getByText("41")).toBeInTheDocument();
    expect(screen.getByText("Not met")).toBeInTheDocument();
    expect(screen.getAllByText("RFP.pdf · p.3")).toHaveLength(2); // reason + risk
    expect(screen.getByText("Technical fit")).toBeInTheDocument();
    expect(screen.getByText(/No data: No past projects/)).toBeInTheDocument();
    expect(screen.getByText("Eligibility criterion not met")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /recompute/i })).toBeInTheDocument();
  });

  it("points to the profile page when no profile exists", async () => {
    vi.mocked(qualificationService.get).mockResolvedValue({
      tender_id: "t-1",
      profile_configured: false,
      is_stale: false,
      qualification: null,
    });

    renderPanel();

    expect(await screen.findByRole("link", { name: /set up the company profile/i })).toHaveAttribute("href", "/profile");
  });

  it("warns when the result is stale and hides compute for read-only users", async () => {
    vi.mocked(qualificationService.get).mockResolvedValue({ ...computed, is_stale: true });

    renderPanel(false);

    expect(await screen.findByText(/have changed since this was computed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /compute/i })).not.toBeInTheDocument();
  });
});
