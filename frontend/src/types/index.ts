export type Department =
  | "wine/25_2-10"
  | "wine/25_12-20"
  | "wine/26_12-20"
  | "gastronomy/43_15"
  | "dairy/49_5"
  | "unknown";

export type RunStatus = "idle" | "uploaded" | "processing" | "completed" | "failed";

export type MatchStatus = "fully_matched" | "partial_ocr" | "needs_review" | "failed";

export type Severity = "warning" | "error" | "info";

export interface Run {
  id: string;
  department: Department;
  fileName?: string;
  status: RunStatus;
  progress: number;
  createdAt: string;
}

export interface ResultItem {
  id: string;
  productName: string;
  priceDefault?: string;
  priceCard?: string;
  discountAmount?: string;
  barcode?: string;
  confidence: number;
  status: MatchStatus;
  frameTimestamp?: string;
  bbox?: { xMin: number; yMin: number; xMax: number; yMax: number };
  imageUrl?: string;
}

export interface Summary {
  totalTags: number;
  fullyMatched: number;
  partial: number;
  needsReview: number;
  failed: number;
  runtimeSeconds: number;
}

export interface Issue {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  tagId?: string;
}
