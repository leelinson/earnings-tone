// a true minus sign (U+2212) lines up with "+" in tabular figures; a hyphen looks cramped
const signed = (s: string) => (s.startsWith("-") ? `\u2212${s.slice(1)}` : s);
export const pct = (x: number | null | undefined, digits = 1) =>
  x == null ? "–" : signed(`${x > 0 ? "+" : ""}${(100 * x).toFixed(digits)}%`);
const ordinal = (n: number) => {
  const r = n % 100;
  return `${n}${r >= 11 && r <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
};
export const pctile = (x: number | null | undefined) => (x == null ? "–" : ordinal(Math.round(x)));
export const bps = (x: number) => signed(`${x > 0 ? "+" : ""}${Math.round(x)} bps`);
export const longDate = (d: string) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
export const signClass = (x: number | null | undefined) => (x == null ? "" : x > 0 ? "up" : x < 0 ? "down" : "");
