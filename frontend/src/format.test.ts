import { describe, expect, it } from "vitest";
import { humanize } from "./format";

describe("humanize", () => {
  it("formats operational state labels", () => {
    expect(humanize("waiting_technician")).toBe("Waiting Technician");
  });
});
