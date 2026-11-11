import { priceOf } from "./catalog";

export type Line = { sku: string; qty: number };

export const total = (lines: Line[]): number =>
  lines.reduce((sum, l) => sum + priceOf(l.sku) * l.qty, 0);
