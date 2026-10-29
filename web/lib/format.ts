export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "–" : `${x > 0 ? "+" : ""}${(100 * x).toFixed(digits)}%`;
const ordinal = (n: number) => {
  const r = n % 100;
  return `${n}${r >= 11 && r <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
};
export const pctile = (x: number | null | undefined) => (x == null ? "–" : ordinal(Math.round(x)));
export const bps = (x: number) => `${x > 0 ? "+" : ""}${Math.round(x)} bps`;
export const longDate = (d: string) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
export const signClass = (x: number | null | undefined) => (x == null ? "" : x > 0 ? "up" : x < 0 ? "down" : "");
