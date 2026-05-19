import { ArrowRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "./Button";

interface ModeCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  buttonLabel: string;
  variant?: "primary" | "secondary";
  onClick: () => void;
}

export function ModeCard({
  title,
  description,
  icon: Icon,
  buttonLabel,
  variant = "primary",
  onClick,
}: ModeCardProps) {
  return (
    <article className={`mode-card ${variant}`}>
      <div className="mode-icon">
        <Icon size={28} />
      </div>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <Button
        onClick={onClick}
        icon={<ArrowRight size={18} />}
        variant={variant === "secondary" ? "secondary" : "primary"}
      >
        {buttonLabel}
      </Button>
    </article>
  );
}
