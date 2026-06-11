"use client";

import { useEffect, useState } from "react";
import { resolveTheme, setTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setThemeState(resolveTheme());
    setMounted(true);
  }, []);

  function select(next: Theme) {
    setTheme(next);
    setThemeState(next);
  }

  if (!mounted) {
    return (
      <div
        className="theme-toggle"
        style={{ width: "7.5rem", height: "2.25rem" }}
        aria-hidden
      />
    );
  }

  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      <button
        type="button"
        aria-pressed={theme === "light"}
        onClick={() => select("light")}
      >
        Light
      </button>
      <button
        type="button"
        aria-pressed={theme === "dark"}
        onClick={() => select("dark")}
      >
        Dark
      </button>
    </div>
  );
}
