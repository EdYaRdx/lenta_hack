import { UploadCloud } from "lucide-react";
import type { ChangeEvent, DragEvent } from "react";

interface UploadDropzoneProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
}

export function UploadDropzone({ file, onFileChange }: UploadDropzoneProps) {
  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const nextFile = event.dataTransfer.files.item(0);
    if (nextFile) onFileChange(nextFile);
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
    onFileChange(event.target.files?.item(0) ?? null);
  };

  return (
    <div className="dropzone" onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
      <div className="dropzone-content">
        <span className="dropzone-icon">
          <UploadCloud size={34} />
        </span>
        <h3>{file ? file.name : "Перетащите видео сюда"}</h3>
        <p>
          {file
            ? "Файл выбран и готов к следующему шагу."
            : "Сейчас это демонстрационный выбор файла. Реальная загрузка будет подключена через API."}
        </p>
        <label className="button button-secondary file-picker">
          <input className="hidden-input" type="file" accept="video/*" onChange={handleInput} />
          <span>Выбрать файл</span>
        </label>
      </div>
    </div>
  );
}
