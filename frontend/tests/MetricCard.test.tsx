import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricCard } from "@/components/MetricCard";

describe("MetricCard", () => {
  it("renders the label and value", () => {
    render(<MetricCard label="New Tenders" value={42} />);
    expect(screen.getByText("New Tenders")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
