import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";


const lead = {
  id: 1,
  external_id: "acme-1",
  company: "Acme",
  industry: "Software",
  employees: 25,
  employee_band: "20–50",
  message_variant: "Founder note",
  baseline_score: 62,
  outcome: "replied",
  created_at: "2026-10-12T00:00:00Z",
  updated_at: "2026-10-12T00:00:00Z"
};

const analytics = {
  target: "replied",
  labeled_count: 30,
  overall_successes: 12,
  overall_rate: 0.4,
  overall_smoothed_rate: 0.40625,
  metrics: [
    {
      dimension: "industry",
      segment: "Software",
      observations: 10,
      successes: 8,
      rate: 0.8,
      smoothed_rate: 0.75,
      lift: 1.85,
      eligible: true,
      adjustment: 9,
      recommendation: "Observed 1.9× replied rate; consider +9 points"
    }
  ]
};

const ranking = {
  target: "replied",
  items: [
    {
      ...lead,
      baseline_rank: 2,
      suggested_rank: 1,
      rank_delta: 1,
      suggested_score: 71,
      drivers: ["Software: +9"]
    }
  ]
};


describe("outcome ranking workflow", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("imports leads, records outcomes, changes objective, and renders rank movement", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith("/api/leads") && (!init || init.method === undefined)) {
        return new Response(JSON.stringify({ items: [lead], total: 1, page: 1, page_size: 50, pages: 1 }));
      }
      if (url.startsWith("/api/analytics")) return new Response(JSON.stringify(analytics));
      if (url.startsWith("/api/rankings")) return new Response(JSON.stringify(ranking));
      if (url === "/api/imports" && init?.method === "POST") {
        return new Response(JSON.stringify({ filename: "leads.csv", total_rows: 1, created: 1, updated: 0 }), { status: 201 });
      }
      if (url === "/api/leads/1/outcome" && init?.method === "PATCH") {
        return new Response(JSON.stringify({ ...lead, outcome: "interested" }));
      }
      return new Response(JSON.stringify({ detail: "Unexpected request" }), { status: 500 });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<App />);

    expect((await screen.findAllByText("Acme")).length).toBeGreaterThan(0);
    expect(screen.getByText("#2 → #1")).toBeInTheDocument();

    const file = new File(
      ["external_id,company,industry,employees,message_variant,baseline_score\na-1,Acme,Software,25,A,50\n"],
      "leads.csv",
      { type: "text/csv" }
    );
    await user.upload(screen.getByLabelText("CSV file"), file);
    await user.click(screen.getByRole("button", { name: "Import leads" }));
    expect(await screen.findByText("Imported 1 lead")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Outcome for Acme"), "interested");
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/leads/1/outcome",
        expect.objectContaining({ method: "PATCH" })
      );
    });

    await user.selectOptions(screen.getByLabelText("Ranking objective"), "meeting_booked");
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url) === "/api/rankings?target=meeting_booked")).toBe(true);
    });
  });
});
