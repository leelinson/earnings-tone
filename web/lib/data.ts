// Build-time data access. Files come from api/export_static.py, so every number matches the API.
import fs from "node:fs";
import path from "node:path";

const DATA = path.join(process.cwd(), "data");
const read = <T,>(...parts: string[]): T => JSON.parse(fs.readFileSync(path.join(DATA, ...parts), "utf8"));

export type Company = {
  ticker: string; name: string; sector: string | null; n_calls: number;
  first_call: string | null; last_call: string | null;
};
export type CompanySummary = {
  calls_with_reaction: number; avg_hedging_pct: number | null; beat_rate: number | null;
  avg_car_0_1: number | null; avg_abs_car_0_1: number | null;
};
export type Call = {
  call_id: string; ticker: string; call_date: string; transcript_date: string; date_fixed: number;
  call_hour: number | null; after_close: number | null; quarter: string | null; reaction_day: string | null;
  n_questions: number | null; in_study: number;
  hedging_per1k: number | null; net_tone: number | null; tone_gap: number | null; relevance: number | null;
  non_answer_rate: number | null; hedging_pct: number | null; evasion_pct: number | null;
  net_tone_pct: number | null; tone_group: number | null;
  beat: string | null; surprise_pct: number | null; sources_disagree: number | null;
  car_0_1: number | null; car_2_20: number | null;
};
export type PricePoint = { date: string; adj_close: number };
export type WindowPoint = { day: number; date: string; stock_pct: number; market_pct: number };
export type QAPair = {
  pair_no: number; question: string; answer: string; answer_words: number;
  hedging_per1k: number; net_tone: number; relevance: number | null; non_answer: number;
};
export type Step = { step: number; title: string; what: string; why: string; figure: number; figure_label: string; fmt: string };
export type Regression = {
  id: string; hypothesis: string; question: string; variable: string; label: string; window: string;
  coef_bps: number; t_stat: number; is_test: boolean;
};
export type Study = {
  summary: [{ calls: number; firms: number; first_call: string; last_call: string; sue_coef_bps: number; sue_t: number }];
  project_steps: Step[];
  regressions: Regression[];
};

export const companies = () => read<Company[]>("companies.json");
export const company = (t: string) =>
  read<{ company: Company & { summary: CompanySummary }; calls: Call[]; prices: PricePoint[] }>("company", `${t}.json`);
export const call = (id: string) => read<{ call: Call; window: WindowPoint[]; qa: QAPair[] }>("call", `${id}.json`);
export const study = () => read<Study>("study.json");
