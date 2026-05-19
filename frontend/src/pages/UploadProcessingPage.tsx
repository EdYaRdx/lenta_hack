import { ArrowLeft, CheckCircle2, FileVideo, Info } from "lucide-react";
import { Button } from "../components/Button";
import { DepartmentSelect } from "../components/DepartmentSelect";
import { UploadDropzone } from "../components/UploadDropzone";
import type { Department } from "../types";

type UploadProcessingPageProps = {
  file: File | null;
  department: Department;
  onBack: () => void;
  onContinue: () => void;
  onDepartmentChange: (department: Department) => void;
  onFileChange: (file: File | null) => void;
};

export function UploadProcessingPage({
  file,
  department,
  onBack,
  onContinue,
  onDepartmentChange,
  onFileChange,
}: UploadProcessingPageProps) {
  return (
    <section className="stack">
      <Button variant="ghost" icon={<ArrowLeft size={18} />} onClick={onBack}>
        Назад
      </Button>

      <div className="section-heading">
        <p className="eyebrow">Обработка видео</p>
        <h1>Загрузите видео полки</h1>
        <p>
          Сейчас UI работает на моках. В будущем выбранный отдел будет записан в
          <code> input/&lt;run_id&gt;/name.json</code> и передан backend pipeline.
        </p>
      </div>

      <div className="content-grid">
        <div className="panel">
          <UploadDropzone file={file} onFileChange={onFileChange} />
          <DepartmentSelect value={department} onChange={onDepartmentChange} />
          <Button
            className="wide-button"
            disabled={!file}
            icon={<FileVideo size={18} />}
            onClick={onContinue}
          >
            Продолжить
          </Button>
        </div>

        <aside className="side-stack">
          <div className="info-card">
            <Info size={22} />
            <div>
              <h3>Что дальше</h3>
              <p>
                Backend сгруппирует кадры одного ценника, выполнит OCR, сверит
                признаки с каталогом и reference-БД, затем сформирует CSV.
              </p>
            </div>
          </div>

          <div className="info-card">
            <CheckCircle2 size={22} />
            <div>
              <h3>Требования к видео</h3>
              <ul>
                <li>ценники должны быть видны без сильного смаза;</li>
                <li>желательно несколько ракурсов одного ценника;</li>
                <li>для reference mode нужен корректный department.</li>
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
