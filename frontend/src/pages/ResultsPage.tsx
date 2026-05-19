import { ArrowLeft, Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { downloadCsv, getIssues, getResults, getSummary } from "../api/client";
import { Button } from "../components/Button";
import { IssueCard } from "../components/IssueCard";
import { ResultCard } from "../components/ResultCard";
import { SummaryCards } from "../components/SummaryCards";
import type { Issue, MatchStatus, ResultItem, Summary } from "../types";

type Filter = "all" | "fully_matched" | "partial_ocr" | "needs_review";

type ResultsPageProps = {
  runId: string;
  onBack: () => void;
};

const filters: { id: Filter; label: string }[] = [
  { id: "all", label: "Все" },
  { id: "fully_matched", label: "Уверенные" },
  { id: "partial_ocr", label: "Частичные" },
  { id: "needs_review", label: "Проверка" },
];

export function ResultsPage({ runId, onBack }: ResultsPageProps) {
  const [results, setResults] = useState<ResultItem[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    void Promise.all([getResults(runId), getSummary(runId), getIssues(runId)]).then(
      ([nextResults, nextSummary, nextIssues]) => {
        setResults(nextResults);
        setSummary(nextSummary);
        setIssues(nextIssues);
      },
    );
  }, [runId]);

  const filteredResults = useMemo(() => {
    if (filter === "all") return results;
    return results.filter((item) => item.status === (filter as MatchStatus));
  }, [filter, results]);

  return (
    <section className="stack">
      <div className="toolbar">
        <Button variant="ghost" icon={<ArrowLeft size={18} />} onClick={onBack}>
          На главную
        </Button>
        <Button icon={<Download size={18} />} onClick={() => void downloadCsv(runId)}>
          Экспорт CSV
        </Button>
      </div>

      <div className="section-heading">
        <p className="eyebrow">Результаты</p>
        <h1>Итог распознавания</h1>
        <p>
          Список ниже показывает mock-результаты: уверенные совпадения, частичный
          OCR и позиции, которые требуют ручной проверки.
        </p>
      </div>

      {summary && <SummaryCards summary={summary} />}

      <div className="results-layout">
        <div className="stack">
          <div className="filter-tabs" aria-label="Фильтр результатов">
            {filters.map((item) => (
              <button
                className={filter === item.id ? "active" : ""}
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="result-list">
            {filteredResults.map((item) => (
              <ResultCard item={item} key={item.id} />
            ))}
          </div>
        </div>

        <aside className="side-stack">
          <h2>Проблемы и несовпадения</h2>
          {issues.map((issue) => (
            <IssueCard issue={issue} key={issue.id} />
          ))}
        </aside>
      </div>
    </section>
  );
}
