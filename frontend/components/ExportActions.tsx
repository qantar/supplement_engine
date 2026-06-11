"use client";

import { useState } from "react";
import type { RecommendationResponse } from "@/lib/types";
import { formatSummary } from "@/lib/api";

export function ExportActions({ data }: { data: RecommendationResponse }) {
  const [copied, setCopied] = useState(false);

  async function copySummary() {
    const text = formatSummary(data);
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex flex-wrap gap-2 print:hidden">
      <button
        type="button"
        onClick={() => window.print()}
        className="rounded-md border border-panelEdge bg-panel px-3 py-1.5 text-sm text-inkMute transition-colors hover:border-signal hover:text-signal"
      >
        Print summary
      </button>
      <button
        type="button"
        onClick={copySummary}
        className="rounded-md border border-panelEdge bg-panel px-3 py-1.5 text-sm text-inkMute transition-colors hover:border-signal hover:text-signal"
      >
        {copied ? "Copied" : "Copy summary"}
      </button>
    </div>
  );
}

function CopyableId({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={`Copy ${label}`}
      className="group text-left"
    >
      <div className="text-2xs uppercase tracking-wider text-inkFaint">
        {label}
      </div>
      <div className="font-mono text-sm text-inkMute group-hover:text-signal">
        {copied
          ? "Copied"
          : value.length > 20
            ? `${value.slice(0, 8)}…${value.slice(-8)}`
            : value}
      </div>
    </button>
  );
}

export function SessionMetaStrip({ data }: { data: RecommendationResponse }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-panel border border-panelEdge bg-panel px-5 py-4">
      <CopyableId label="Session" value={data.session_id} />
      <Meta label="Model" value={data.model_version} mono />
      {data.execution_ms > 0 && (
        <Meta label="Latency" value={`${data.execution_ms} ms`} mono />
      )}
      <Meta
        label="Snapshot"
        value={data.evidence_snapshot_id ?? "—"}
        mono
      />
      {data.next_review_in_weeks != null && (
        <Meta label="Review in" value={`${data.next_review_in_weeks} wks`} />
      )}
      <div className="ml-auto">
        <ExportActions data={data} />
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-2xs uppercase tracking-wider text-inkFaint">
        {label}
      </div>
      <div className={`text-sm text-inkMute ${mono ? "font-mono" : ""}`}>
        {value}
      </div>
    </div>
  );
}
