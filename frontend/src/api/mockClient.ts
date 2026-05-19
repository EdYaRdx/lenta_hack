import { mockIssues, mockResults, mockSummary } from "../data/mock";
import type { Department, Issue, ResultItem, Run, Summary } from "../types";
import { resultsToCsv } from "../utils/csv";

const runs = new Map<string, Run>();

function delay<T>(value: T, ms = 350): Promise<T> {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(value), ms);
  });
}

function createRunId(): string {
  return `run_${Date.now().toString(36)}`;
}

export async function startRun(params: { department: Department; fileName?: string }): Promise<Run> {
  const run: Run = {
    id: createRunId(),
    department: params.department,
    fileName: params.fileName,
    status: "processing",
    progress: 0,
    createdAt: new Date().toISOString(),
  };
  runs.set(run.id, run);
  return delay(run);
}

export async function getRunStatus(runId: string): Promise<Run> {
  const current = runs.get(runId);
  if (!current) {
    return delay({
      id: runId,
      department: "unknown",
      status: "failed",
      progress: 0,
      createdAt: new Date().toISOString(),
    });
  }

  const nextProgress = Math.min(100, current.progress + 7 + Math.round(Math.random() * 10));
  const next: Run = {
    ...current,
    progress: nextProgress,
    status: nextProgress >= 100 ? "completed" : "processing",
  };
  runs.set(runId, next);
  return delay(next, 420);
}

export async function getResults(_runId: string): Promise<ResultItem[]> {
  return delay(mockResults, 240);
}

export async function getSummary(_runId: string): Promise<Summary> {
  return delay(mockSummary, 240);
}

export async function getIssues(_runId: string): Promise<Issue[]> {
  return delay(mockIssues, 240);
}

export async function downloadCsv(_runId: string): Promise<void> {
  const csv = resultsToCsv(mockResults);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "lenta_cv_results_mock.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return delay(undefined, 100);
}
