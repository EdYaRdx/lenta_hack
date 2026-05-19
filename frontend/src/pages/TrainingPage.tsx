import { ArrowLeft, Save, X } from "lucide-react";
import { useState } from "react";
import { Button } from "../components/Button";
import { UploadDropzone } from "../components/UploadDropzone";

type TrainingPageProps = {
  onBack: () => void;
};

const annotations = [
  "tag_000001: bbox размечен, название требует проверки",
  "tag_000002: цена и скидка подтверждены",
  "tag_000003: QR не читается, нужен дополнительный кадр",
];

export function TrainingPage({ onBack }: TrainingPageProps) {
  const [file, setFile] = useState<File | null>(null);

  return (
    <section className="stack">
      <Button variant="ghost" icon={<ArrowLeft size={18} />} onClick={onBack}>
        Назад
      </Button>

      <div className="section-heading">
        <p className="eyebrow">Режим дообучения</p>
        <h1>Разметка и подготовка данных</h1>
        <p>
          Это UI-заглушка. Реальное обучение модели и сохранение разметки сейчас
          не реализованы.
        </p>
      </div>

      <div className="training-layout">
        <div className="panel">
          <UploadDropzone file={file} onFileChange={setFile} />
          <div className="training-viewer">
            <span>{file ? file.name : "Здесь будет viewer видео и bbox-разметка"}</span>
          </div>
        </div>

        <aside className="panel annotation-panel">
          <h2>Размеченные ценники</h2>
          <div className="annotation-list">
            {annotations.map((item) => (
              <div className="annotation-item" key={item}>
                {item}
              </div>
            ))}
          </div>
          <div className="button-row">
            <Button icon={<Save size={18} />}>Сохранить и выйти</Button>
            <Button icon={<X size={18} />} variant="secondary" onClick={onBack}>
              Отменить
            </Button>
          </div>
        </aside>
      </div>
    </section>
  );
}
