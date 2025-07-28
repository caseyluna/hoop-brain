import { render, screen, waitFor } from "@testing-library/react";
import TeamsTable from "./TeamsTable";
import { describe, it, vi, beforeEach } from "vitest";

const mockTeams = [
  {
    id: "1",
    full_name: "Boston Celtics",
    abbreviation: "BOS",
    nickname: "Celtics",
    city: "Boston",
    state: "MA",
    year_founded: "1946",
  },
];

describe("TeamsTable", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          json: () => Promise.resolve(mockTeams),
        }),
      ) as typeof fetch,
    );
  });

  it("renders team data from API", async () => {
    render(<TeamsTable />);

    await waitFor(() => {
      expect(screen.getByText("Boston Celtics")).toBeInTheDocument();
      expect(screen.getByText("BOS")).toBeInTheDocument();
      expect(screen.getByText("Celtics")).toBeInTheDocument();
      expect(screen.getByText("Boston")).toBeInTheDocument();
      expect(screen.getByText("MA")).toBeInTheDocument();
      expect(screen.getByText("1946")).toBeInTheDocument();
    });
  });
});
