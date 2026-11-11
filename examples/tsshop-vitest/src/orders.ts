import { total, Line } from "./pricing";
import { Stock } from "./stock";

export function place(lines: Line[]) {
  const stock = new Stock();
  for (const l of lines) stock.reserve(l.sku, l.qty);
  return { total: total(lines), lines: lines.length };
}

// no test runs this one, so `flow gaps` lists it
export function cancel(id: number): boolean {
  return id > 0;
}
