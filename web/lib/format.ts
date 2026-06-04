export type ChangeTone = "up" | "down" | "flat";

/**
 * Classify a human-readable change string (e.g. "+2.1%", "-0.4%", "-") into a
 * display tone. A bare "-" or empty value is a placeholder for "no data" and
 * must render neutral, not as a loss.
 */
export function changeTone(change: string): ChangeTone {
  const trimmed = change.trim();
  if (!trimmed || trimmed === "-") return "flat";
  return trimmed.startsWith("-") ? "down" : "up";
}
