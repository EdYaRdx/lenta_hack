import type { Department, MatchStatus } from "../types";

export function formatRuntime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)} сек`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} мин ${rest} сек`;
}

export function formatDepartment(department: Department): string {
  if (department === "unknown") return "Неизвестный отдел";
  const [base, key] = department.split("/");
  const labels: Record<string, string> = {
    wine: "Вино",
    gastronomy: "Гастрономия",
    dairy: "Молочная категория",
  };
  return `${labels[base] ?? base} - ${key}`;
}

export function statusLabel(status: MatchStatus): string {
  const labels: Record<MatchStatus, string> = {
    fully_matched: "Уверенно",
    partial_ocr: "Частично",
    needs_review: "Проверка",
    failed: "Ошибка",
  };
  return labels[status];
}

export function statusTone(status: MatchStatus): string {
  const tones: Record<MatchStatus, string> = {
    fully_matched: "success",
    partial_ocr: "partial",
    needs_review: "warning",
    failed: "danger",
  };
  return tones[status];
}
