import { Activity } from "lucide-react";

interface TopBarProps {
  onLogoClick?: () => void;
}

export function TopBar({ onLogoClick }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar-inner">
        <button className="brand-button" type="button" onClick={onLogoClick}>
          <span className="brand-mark">
            <Activity size={22} />
          </span>
          <span>LentaCV</span>
        </button>
        <span className="top-meta">OCR + catalog + reference matching</span>
      </div>
    </header>
  );
}
