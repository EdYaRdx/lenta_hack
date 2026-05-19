import { Database, PlayCircle } from "lucide-react";
import { ModeCard } from "../components/ModeCard";

type ModeSelectionPageProps = {
  onProcessing: () => void;
  onTraining: () => void;
};

export function ModeSelectionPage({ onProcessing, onTraining }: ModeSelectionPageProps) {
  return (
    <section className="hero-layout">
      <div className="hero-copy">
        <p className="eyebrow">LentaCV</p>
        <h1>Распознавание ценников из видеопотока робота</h1>
        <p>
          Демонстрационный интерфейс для OCR/matching backend: загрузка видео,
          выбор отдела, запуск обработки и просмотр итогового CSV с уровнем
          уверенности.
        </p>
      </div>

      <div className="mode-grid">
        <ModeCard
          icon={PlayCircle}
          title="Режим обработки видео"
          description="Загрузите видео, выберите отдел и получите список распознанных ценников."
          buttonLabel="Перейти к обработке"
          onClick={onProcessing}
        />
        <ModeCard
          icon={Database}
          title="Режим дообучения"
          description="Черновой экран для будущей ручной разметки и подготовки обучающих данных."
          buttonLabel="Открыть разметку"
          variant="secondary"
          onClick={onTraining}
        />
      </div>
    </section>
  );
}
