import { ThemeToggle } from "@/components/ThemeToggle";

interface Props {
  modelVersion?: string;
}

export function AppHeader({ modelVersion = "rec-engine" }: Props) {
  return (
    <header className="topbar print:hidden" role="banner">
      <div className="topbar-brand">
        <span className="topbar-dot" aria-hidden />
        <span className="topbar-name">Supplement Engine</span>
        <span className="topbar-version mono-val">{modelVersion}</span>
      </div>

      <div className="topbar-actions">
        <span className="topbar-status" aria-label="Engine status">
          <span className="topbar-status-dot" aria-hidden />
          Engine ready
        </span>
        <ThemeToggle />
      </div>
    </header>
  );
}
