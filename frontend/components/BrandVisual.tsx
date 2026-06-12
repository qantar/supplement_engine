"use client";

import { useState } from "react";

const CDN_BASE =
  "https://d8j0ntlcm91z4.cloudfront.net/user_3Ezu3FyVZgfmIrgb7Sj43rMkwMy";

/** Generated brand visuals. Local files (public/visuals) are preferred;
 *  the CDN copy is used automatically until `scripts/fetch_visuals.sh`
 *  has been run. If both fail the image hides itself — never a broken icon. */
const SOURCES: Record<string, { local: string; cdn: string }> = {
  dashboard: {
    local: "/visuals/dashboard.png",
    cdn: `${CDN_BASE}/hf_20260612_065229_684b377a-99c5-45a2-af53-672ed338f8c0.png`,
  },
  "feature-bayesian": {
    local: "/visuals/feature-bayesian.png",
    cdn: `${CDN_BASE}/hf_20260612_065302_ed5cc9ee-36c3-4eb4-8f7d-0ed56f629b5f.png`,
  },
  "feature-safety-gate": {
    local: "/visuals/feature-safety-gate.png",
    cdn: `${CDN_BASE}/hf_20260612_065332_dded8244-2673-4b72-a709-1abcb8fbeeee.png`,
  },
  "empty-state": {
    local: "/visuals/empty-state.png",
    cdn: `${CDN_BASE}/hf_20260612_065422_6e64035b-186f-42c1-ae36-7badb858dc21.png`,
  },
  "hero-dark": {
    local: "/visuals/hero-dark.png",
    cdn: `${CDN_BASE}/hf_20260611_164030_5f7d0546-c01c-4369-8f3c-cbc0e321df45.png`,
  },
};

interface Props {
  name: keyof typeof SOURCES;
  alt: string;
  className?: string;
}

export function BrandVisual({ name, alt, className }: Props) {
  const src = SOURCES[name];
  const [stage, setStage] = useState<"local" | "cdn" | "hidden">("local");

  if (!src || stage === "hidden") return null;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={stage === "local" ? src.local : src.cdn}
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => setStage(stage === "local" ? "cdn" : "hidden")}
    />
  );
}
