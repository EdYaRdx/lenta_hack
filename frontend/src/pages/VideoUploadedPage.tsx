import { ArrowLeft, Play, ShieldCheck } from "lucide-react";
import { Button } from "../components/Button";
import { VideoPreview } from "../components/VideoPreview";
import { formatDepartment } from "../utils/format";
import type { Department } from "../types";

type VideoUploadedPageProps = {
  fileName: string;
  department: Department;
  onBack: () => void;
  onStart: () => void;
};

export function VideoUploadedPage({
  fileName,
  department,
  onBack,
  onStart,
}: VideoUploadedPageProps) {
  return (
    <section className="stack">
      <Button variant="ghost" icon={<ArrowLeft size={18} />} onClick={onBack}>
        Назад
      </Button>

      <div className="section-heading">
        <p className="eyebrow">Видео загружено</p>
        <h1>Готово к обработке</h1>
      </div>

      <div className="content-grid">
        <VideoPreview fileName={fileName} />

        <div className="panel status-panel">
          <div className="status-row success">
            <ShieldCheck size={24} />
            <span>готово к обработке</span>
          </div>

          <div className="meta-list">
            <div>
              <span>Файл</span>
              <strong>{fileName}</strong>
            </div>
            <div>
              <span>Department</span>
              <strong>{formatDepartment(department)}</strong>
            </div>
          </div>

          <Button className="wide-button" icon={<Play size={18} />} onClick={onStart}>
            Начать обработку
          </Button>
        </div>
      </div>
    </section>
  );
}
