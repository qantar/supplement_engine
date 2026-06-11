import type { CSSProperties } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { HeroHelix } from "@/components/ClinicalIcons";

interface Props {
  modelVersion?: string;
}

export function AppHeader({ modelVersion = "rec-engine" }: Props) {
  return (
    <header className="hero print:hidden">
      <div className="hero-toolbar">
        <ThemeToggle />
      </div>

      <div className="hero-stage">
        <div className="hero-copy">
          <div className="eyebrow hero-eyebrow hero-animate" style={{ "--delay": "0ms" } as CSSProperties}>
            Supplement Engine · {modelVersion}
          </div>

          <h1 className="hero-title hero-title--stack">
            <span className="hero-line hero-animate" style={{ "--delay": "60ms" } as CSSProperties}>
              <span className="hero-accent">Evidence-ranked</span> nutraceutical recommendations
            </span>

            <span className="hero-helix-slot hero-animate" style={{ "--delay": "100ms" } as CSSProperties}>
              <HeroHelix />
            </span>

            <span
              className="hero-line hero-line--sub hero-animate"
              style={{ "--delay": "140ms" } as CSSProperties}
            >
              behind a <em className="hero-emphasis">deterministic safety gate</em>
            </span>
          </h1>
        </div>
      </div>
    </header>
  );
}
