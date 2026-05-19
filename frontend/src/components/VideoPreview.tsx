import { PlayCircle } from "lucide-react";

interface VideoPreviewProps {
  fileName?: string;
}

export function VideoPreview({ fileName }: VideoPreviewProps) {
  return (
    <div className="video-preview">
      <div className="video-preview-inner">
        <PlayCircle size={56} />
        <strong>{fileName ?? "Видео не выбрано"}</strong>
        <span>Preview будет подключен после реальной загрузки на backend.</span>
      </div>
    </div>
  );
}
