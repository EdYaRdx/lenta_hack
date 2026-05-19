interface ProgressStatusProps {
  progress: number;
  statusText: string;
}

export function ProgressStatus({ progress, statusText }: ProgressStatusProps) {
  return (
    <section className="progress-card">
      <div className="progress-header">
        <div>
          <h2>Обработка видео</h2>
          <p>{statusText}</p>
        </div>
        <strong>{Math.round(progress)}%</strong>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.min(progress, 100)}%` }} />
      </div>
    </section>
  );
}
