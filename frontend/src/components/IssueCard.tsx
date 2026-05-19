import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import type { Issue } from "../types";

interface IssueCardProps {
  issue: Issue;
}

export function IssueCard({ issue }: IssueCardProps) {
  const Icon =
    issue.severity === "error"
      ? AlertCircle
      : issue.severity === "warning"
        ? AlertTriangle
        : Info;

  return (
    <article className={`issue-card ${issue.severity}`}>
      <div className="issue-header">
        <Icon size={18} />
        <span>{issue.title}</span>
      </div>
      <p>{issue.description}</p>
      {issue.tagId ? <small>{issue.tagId}</small> : null}
    </article>
  );
}
