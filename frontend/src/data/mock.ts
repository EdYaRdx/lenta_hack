import type { Department, Issue, ResultItem, Summary } from "../types";

export const departments: Department[] = [
  "wine/25_2-10",
  "wine/25_12-20",
  "wine/26_12-20",
  "gastronomy/43_15",
  "dairy/49_5",
  "unknown",
];

export const mockResults: ResultItem[] = [
  {
    id: "tag_000004",
    productName: "Вино PURE ALTITUDE Шардоне бел. сух. (Франция) 0.75L",
    priceDefault: "2315.78",
    priceCard: "1499.99",
    discountAmount: "-35%",
    barcode: "3700619352626",
    confidence: 94,
    status: "fully_matched",
    frameTimestamp: "0.600",
    bbox: { xMin: 2147, yMin: 94, xMax: 2361, yMax: 316 },
  },
  {
    id: "tag_000005",
    productName: "Вино PURE ALTITUDE Совиньон Блан бел. сух. (Франция) 0.75L",
    priceDefault: "2315.78",
    priceCard: "1499.99",
    discountAmount: "-35%",
    barcode: "3700619352626",
    confidence: 93,
    status: "fully_matched",
    frameTimestamp: "0.750",
    bbox: { xMin: 2140, yMin: 641, xMax: 2360, yMax: 886 },
  },
  {
    id: "tag_000008",
    productName: "Вино HAUT MARIN Colombard Ugni-blanc Littorine бел. сух. (Франция) 0.75L",
    priceDefault: "1747.36",
    priceCard: "1104.99",
    discountAmount: "-36%",
    barcode: "3760094282559",
    confidence: 88,
    status: "fully_matched",
  },
  {
    id: "tag_000007",
    productName: "Не удалось уверенно сопоставить товар",
    priceCard: "104.92",
    discountAmount: "-25%",
    confidence: 32,
    status: "needs_review",
  },
  {
    id: "tag_000023",
    productName: "OCR распознал только часть названия",
    priceCard: "1999.99",
    confidence: 48,
    status: "partial_ocr",
  },
];

export const mockSummary: Summary = {
  totalTags: 97,
  fullyMatched: 15,
  partial: 30,
  needsReview: 52,
  failed: 0,
  runtimeSeconds: 1006.54,
};

export const mockIssues: Issue[] = [
  {
    id: "issue_price",
    title: "Цена не совпадает",
    description:
      "OCR увидел подозрительно низкую цену. Reference matching проверил repair-варианты перед enrichment.",
    severity: "warning",
    tagId: "tag_000008",
  },
  {
    id: "issue_match",
    title: "Не удалось уверенно сопоставить товар",
    description:
      "Недостаточно надежных признаков: barcode/QR/id_sku не прочитаны, product_name шумный.",
    severity: "error",
    tagId: "tag_000007",
  },
  {
    id: "issue_qr",
    title: "QR/barcode не прочитан",
    description:
      "На части кадров код слишком мелкий или смазан. Поля оставлены пустыми.",
    severity: "info",
  },
];
