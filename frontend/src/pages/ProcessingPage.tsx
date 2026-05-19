import { useEffect } from "react";
import { getRunStatus } from "../api/client";
import { ProgressStatus } from "../components/ProgressStatus";
import type { Run } from "../types";

type ProcessingPageProps = {
  run: Run;
  onRunUpdate: (run: Run) => void;
  onComplete: () => void;
};

function getStatusText(progress: number) {
  if (progress < 20) return "Подготавливаем кадры и группы ценников";
  if (progress < 45) return "Запускаем OCR по выбранным view";
  if (progress < 70) return "Агрегируем поля по группам";
  if (progress < 92) return "Сверяем с каталогом и reference-БД";
  return "Нормализуем CSV и собираем отчеты";
}

export function ProcessingPage({ run, onRunUpdate, onComplete }: ProcessingPageProps) {
  useEffect(() => {
    if (run.status === "completed") {
      onComplete();
      return;
    }

    const timerId = window.setInterval(async () => {
      const nextRun = await getRunStatus(run.id);
      onRunUpdate(nextRun);
      if (nextRun.status === "completed") {
        window.clearInterval(timerId);
        window.setTimeout(onComplete, 450);
      }
    }, 700);

    return () => window.clearInterval(timerId);
  }, [run.id, run.status, onComplete, onRunUpdate]);

  return (
    <section className="processing-layout">
      <div className="section-heading center">
        <p className="eyebrow">Pipeline running</p>
        <h1>Обрабатываем видео</h1>
        <p>{getStatusText(run.progress)}</p>
      </div>
      <ProgressStatus progress={run.progress} statusText={getStatusText(run.progress)} />
    </section>
  );
}
