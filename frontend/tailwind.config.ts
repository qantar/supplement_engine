import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: "#0d1117",        // deep slate instrument ground
        panel: "#161b22",         // raised panel
        panelEdge: "#222b36",     // hairline edges
        ink: "#e6edf3",           // primary text
        inkMute: "#8b97a6",       // secondary text
        inkFaint: "#5b6675",      // tertiary / captions
        signal: "#39d3c3",        // clinical signal cyan (confidence/data)
        signalDim: "#1d6f68",
        warn: "#e3b341",          // moderate warning amber
        danger: "#f06a6a",        // block / contraindication
        ok: "#56d364",            // sufficiency
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      borderRadius: { panel: "10px" },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
      },
    },
  },
  plugins: [],
};
export default config;
