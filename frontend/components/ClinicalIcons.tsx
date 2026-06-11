/** Inline DNA helix — sized to sit between hero title lines. */
import type { CSSProperties } from "react";

const VB_W = 560;
const VB_H = 52;
const CY = 26;
const AMP = 14;
const K = 0.048;

function strandY(x: number, strand: "a" | "b"): number {
  const phase = strand === "a" ? 0 : Math.PI;
  return CY + AMP * Math.sin(K * x + phase);
}

function helixPath(strand: "a" | "b"): string {
  const parts: string[] = [];
  for (let x = 20; x <= 540; x += 4) {
    const y = strandY(x, strand);
    parts.push(`${parts.length === 0 ? "M" : "L"} ${x} ${y.toFixed(1)}`);
  }
  return parts.join(" ");
}

function rungAt(x: number) {
  return { x, y1: strandY(x, "a"), y2: strandY(x, "b") };
}

const GATE_XS = [76, 168, 280, 392, 484];
const RUNGS = GATE_XS.map(rungAt);

const STRAND_A = helixPath("a");
const STRAND_B = helixPath("b");

export function HeroHelix() {
  return (
    <span className="hero-helix" aria-hidden>
      <svg
        className="hero-helix-svg"
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="helix-strand-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgb(var(--blue))" stopOpacity="0.12" />
            <stop offset="50%" stopColor="rgb(var(--blue))" stopOpacity="0.5" />
            <stop offset="100%" stopColor="rgb(var(--blue))" stopOpacity="0.12" />
          </linearGradient>
        </defs>

        <path d={STRAND_A} className="hero-helix-strand hero-helix-strand--a" fill="none" />
        <path d={STRAND_B} className="hero-helix-strand hero-helix-strand--b" fill="none" />

        {RUNGS.map((r, i) => (
          <g key={r.x} className="hero-helix-rung" style={{ "--gate-i": i } as CSSProperties}>
            <line x1={r.x} y1={r.y1} x2={r.x} y2={r.y2} className="hero-helix-rung-line" />
            <circle cx={r.x} cy={CY} r="2.5" className="hero-helix-gate-node" />
          </g>
        ))}

        <g className="hero-helix-scan-wrap">
          <circle cx={0} cy={CY} r="2" className="hero-helix-scan-dot" />
        </g>
      </svg>
    </span>
  );
}

/** @deprecated use HeroHelix */
export const HeroRing = HeroHelix;
