import { describe, expect, it } from "vitest";
import { place } from "../src/orders";
import { total } from "../src/pricing";

describe("checkout", () => {
  it("small order gets a total", () => {
    expect(place([{ sku: "pen", qty: 3 }]).total).toBe(6);
  });
  it("price of two lines", () => {
    expect(total([{ sku: "pen", qty: 1 }, { sku: "book", qty: 1 }])).toBe(14);
  });
  it("out of stock is rejected", () => {
    expect(() => place([{ sku: "lamp", qty: 5 }])).toThrow("not enough");
  });
});
