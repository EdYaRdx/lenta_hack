import type { ResultItem } from "../types";
import { statusLabel, statusTone } from "../utils/format";

interface ResultCardProps {
  item: ResultItem;
}

export function ResultCard({ item }: ResultCardProps) {
  return (
    <article className="result-card">
      <div className="result-card-header">
        <div>
          <span className="input-hint">{item.id}</span>
          <h3>{item.productName}</h3>
        </div>
        <span className={`status-pill ${statusTone(item.status)}`}>{statusLabel(item.status)}</span>
      </div>

      <div className="result-meta">
        <div>
          <span>Без карты</span>
          <strong>{item.priceDefault ?? "-"}</strong>
        </div>
        <div>
          <span>С картой</span>
          <strong>{item.priceCard ?? "-"}</strong>
        </div>
        <div>
          <span>Скидка</span>
          <strong>{item.discountAmount ?? "-"}</strong>
        </div>
        <div>
          <span>Barcode</span>
          <strong>{item.barcode ?? "не прочитан"}</strong>
        </div>
        <div>
          <span>Frame</span>
          <strong>{item.frameTimestamp ?? "-"}</strong>
        </div>
        <div>
          <span>Bbox</span>
          <strong>
            {item.bbox
              ? `${item.bbox.xMin}, ${item.bbox.yMin}, ${item.bbox.xMax}, ${item.bbox.yMax}`
              : "-"}
          </strong>
        </div>
      </div>

      <div className="confidence-track">
        <div className="confidence-fill" style={{ width: `${item.confidence}%` }} />
      </div>
      <div className="confidence-label">Confidence: {item.confidence}%</div>
    </article>
  );
}
