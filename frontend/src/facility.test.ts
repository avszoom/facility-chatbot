import { describe, expect, it } from "vitest";
import { floors, sensors, totalCapacity, totalOccupancy } from "./facility";

describe("facility digital twin data", () => {
  it("covers every floor and every configured sensor", () => {
    expect(floors.map((floor) => floor.number).sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(new Set(sensors.map((sensor) => sensor.id)).size).toBe(50);
    for (const floor of floors) {
      expect(sensors.filter((sensor) => sensor.floor === floor.number)).toHaveLength(5);
    }
    expect(totalOccupancy).toBeLessThan(totalCapacity);
    expect(sensors.some((sensor) => sensor.state === "Critical")).toBe(true);
  });
});
