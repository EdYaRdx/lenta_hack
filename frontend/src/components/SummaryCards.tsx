import { AlertTriangle, CheckCircle2, Clock, ScanLine, Split } from "lucide-react";
import type { Summary } from "../types";
import { formatRuntime } from "../utils/format";

interface SummaryCardsProps {
  summary: Summary;
}

export function SummaryCards({ summary }: SummaryCardsProps) {
  const cards = [
    { label: "Найдено ценников", value: summary.totalTags, icon: <ScanLine size={20} /> },
    { label: "Уверенно сопоставлено", value: summary.fullyMatched, icon: <CheckCircle2 size={20} /> },
    { label: "Частично распознано", value: summary.partial, icon: <Split size={20} /> },
    { label: "Требуют проверки", value: summary.needsReview, icon: <AlertTriangle size={20} /> },
    { label: "Время обработки", value: formatRuntime(summary.runtimeSeconds), icon: <Clock size={20} /> },
  ];

  return (
    <div className="summary-grid">
      {cards.map((card) => (
        <article className="summary-card" key={card.label}>
          <span className="summary-icon">{card.icon}</span>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </article>
      ))}
    </div>
  );
}
