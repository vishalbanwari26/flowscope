const stock: Record<string, number> = { pen: 10, book: 2, lamp: 1 };

export class Stock {
  reserve(sku: string, qty: number): void {
    if ((stock[sku] ?? 0) < qty) throw new Error(`not enough ${sku}`);
    stock[sku] -= qty;
  }
}
