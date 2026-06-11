export function shortId(value: string): string {
  if (value.length <= 20) return value;
  return `${value.slice(0, 8)}…${value.slice(-8)}`;
}

export function formatDoseFrequency(
  frequency: string | null,
  withFood: boolean | null,
): string {
  const parts: string[] = [];
  if (frequency) parts.push(frequency.replace(/_/g, " "));
  if (withFood) parts.push("with food");
  return parts.join(" · ") || "As directed";
}
