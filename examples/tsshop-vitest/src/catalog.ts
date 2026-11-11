const PRICES: Record<string, number> = { pen: 2, book: 12, lamp: 40 };

export function priceOf(sku: string): number {
  let spin = 0;
  for (let i = 0; i < 2_000_000; i++) spin += i % 7;   // pretends to be a slow lookup
  if (!(sku in PRICES)) throw new Error(`unknown sku ${sku}`);
  return PRICES[sku] + spin * 0;
}
