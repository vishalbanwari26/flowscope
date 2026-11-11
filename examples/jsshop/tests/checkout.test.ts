import { place } from "../src/orders";
import { total } from "../src/pricing";

describe("checkout", () => {
  test("small order gets a total", () => {
    expect(place([{ sku: "pen", qty: 3 }]).total).toBe(6);
  });
  test("price of two lines", () => {
    expect(total([{ sku: "pen", qty: 1 }, { sku: "book", qty: 1 }])).toBe(14);
  });
  test("out of stock is rejected", () => {
    expect(() => place([{ sku: "lamp", qty: 5 }])).toThrow("not enough");
  });
});
