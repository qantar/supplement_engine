"use client";

import type { PipelineGate } from "@/lib/pipeline";

interface Props {
  gates: PipelineGate[];
  logs: { text: string; tone?: "ok" | "warn" }[];
}

export function SafetyPipeline({ gates, logs }: Props) {
  return (
    <section className="panel" aria-label="Safety pipeline">
      <div className="panel-label">Safety pipeline</div>
      <div className="gates">
        {gates.map((gate, i) => (
          <div
            key={gate.id}
            className={`gate ${gate.status !== "idle" ? gate.status : ""}`}
          >
            <div className="gate-node">{i + 1}</div>
            <div className="gate-name">{gate.name}</div>
            <div className="gate-stat">{gate.stat}</div>
          </div>
        ))}
      </div>
      {logs.length > 0 && (
        <div className="console-log" aria-label="Engine log">
          {logs.map((line, i) => (
            <div key={i} className={line.tone}>
              › {line.text}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
