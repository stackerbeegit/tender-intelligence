import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { OpportunityDetail } from "@/pages/OpportunityDetail";
import { opportunityService } from "@/services/opportunityService";
import type { OpportunityDetail as Detail } from "@/types/opportunity";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u-1", full_name: "Sales Person", role: { name: "sales" } },
    logout: vi.fn(),
  }),
}));
vi.mock("@/services/opportunityService", () => ({
  opportunityService: { get: vi.fn(), directory: vi.fn(() => Promise.resolve([])), transition: vi.fn() },
  bidService: { get: vi.fn(() => new Promise(() => {})) },
}));

const opportunity: Detail = {
  id: "o-1",
  status: "screening",
  created_from: "auto_relevance",
  tender: { id: "t-1", title: "Citizen Services Portal", tender_number: "ICSP-014", organisation: "DIT Punjab", closing_date: null },
  owner: null,
  assignees: [],
  relevance_score: 82,
  eligibility_status: "UNCERTAIN",
  created_at: "2026-10-20T10:00:00Z",
  updated_at: "2026-10-21T10:00:00Z",
  assignments: [],
  notes: [],
  history: [
    { id: "h-1", from_status: null, to_status: "new", changed_by: null, changed_at: "2026-10-20T10:00:00Z", comment: "Auto-promoted: relevance 82/100" },
    { id: "h-2", from_status: "new", to_status: "screening", changed_by: { id: "u-1", full_name: "Sales Person", email: "s@x" }, changed_at: "2026-10-21T10:00:00Z", comment: null },
  ],
  allowed_transitions: ["qualified", "no_bid"],
  can_edit: true,
  can_decide: false,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/opportunities/o-1"]}>
      <Routes>
        <Route path="/opportunities/:id" element={<OpportunityDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("OpportunityDetail", () => {
  it("shows the audit trail and needs a reason before a no-bid", async () => {
    vi.mocked(opportunityService.get).mockResolvedValue(opportunity);
    vi.mocked(opportunityService.transition).mockResolvedValue({ ...opportunity, status: "no_bid" });

    renderPage();

    expect(await screen.findByText("Auto-promoted by relevance")).toBeInTheDocument();
    expect(screen.getByText("Relevance 82/100")).toBeInTheDocument();
    expect(screen.getByText(/by the system/)).toBeInTheDocument();
    expect(screen.getByText("Auto-promoted: relevance 82/100")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "No bid" }));
    const confirm = await screen.findByRole("button", { name: "Confirm" });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Reason (required)"), { target: { value: "Outside our focus" } });
    fireEvent.click(confirm);

    expect(opportunityService.transition).toHaveBeenCalledWith("o-1", "no_bid", "Outside our focus");
  });
});
