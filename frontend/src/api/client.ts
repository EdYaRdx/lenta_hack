import type { Department } from "../types";
import * as mockClient from "./mockClient";

export function startRun(params: { department: Department; fileName?: string }) {
  return mockClient.startRun(params);
}

export function getRunStatus(runId: string) {
  return mockClient.getRunStatus(runId);
}

export function getResults(runId: string) {
  return mockClient.getResults(runId);
}

export function getSummary(runId: string) {
  return mockClient.getSummary(runId);
}

export function getIssues(runId: string) {
  return mockClient.getIssues(runId);
}

export function downloadCsv(runId: string) {
  return mockClient.downloadCsv(runId);
}
