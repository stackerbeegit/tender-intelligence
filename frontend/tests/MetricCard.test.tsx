import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "@/components/MetricCard";

describe("MetricCard", () => {
  it("renders the label and value", () => {
    render(<MetricCard label="New Tenders" value={42} />);
    expect(screen.getByText("New Tenders")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("shows a dash and the reason for a metric that is not available yet", () => {
    render(<MetricCard label="Won" value={null} hint="Needs the opportunity CRM (Sprint 6)." />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText("Needs the opportunity CRM (Sprint 6).")).toBeInTheDocument();
  });
});
