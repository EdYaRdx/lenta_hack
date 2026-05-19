import type { ResultItem } from "../types";

function escapeCsv(value: string | number | undefined): string {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function resultsToCsv(rows: ResultItem[]): string {
  const header = [
    "id",
    "product_name",
    "price_default",
    "price_card",
    "discount_amount",
    "barcode",
    "confidence",
    "status",
  ];
  const lines = rows.map((item) =>
    [
      item.id,
      item.productName,
      item.priceDefault,
      item.priceCard,
      item.discountAmount,
      item.barcode,
      item.confidence,
      item.status,
    ].map(escapeCsv).join(","),
  );
  return [header.join(","), ...lines].join("\n");
}
