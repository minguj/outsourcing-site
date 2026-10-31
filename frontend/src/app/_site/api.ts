import { COPY, money, type Lang } from "./i18n";

export type Brief = {
  project_type?: string; title?: string; summary?: string; current_process?: string; goals?: string[];
  data_and_systems?: string; users_and_scale?: string; budget?: string; timeline?: string; open_questions?: string[];
};
export type ChatMessage = { role: "user" | "assistant"; content: string };

// Server messages are written in Korean; English pages show these instead.
const EN_STATUS: Record<number, string> = {
  401: "Your session has expired. Please start again.", 404: "Not found. Please check the link you received.",
  409: "This has already been completed.", 429: "Too many requests. Please try again in a moment.",
  503: "This service is temporarily unavailable. Please use the inquiry form below.",
};

export async function api<T>(path: string, init?: RequestInit, lang: Lang = "ko"): Promise<T> {
  const copy = COPY[lang].api;
  let response: Response;
  try {
    // FormData (file uploads) sets its own multipart boundary header.
    const json = !(init?.body instanceof FormData);
    response = await fetch(path, { ...init, headers: { ...(json ? { "Content-Type": "application/json" } : {}), ...(init?.headers ?? {}) } });
  } catch {
    throw new Error(copy.network);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    let detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? copy.invalid : copy.generic;
    if (lang === "en" && /[가-힣]/.test(detail)) detail = EN_STATUS[response.status] ?? (response.status === 422 ? copy.invalid : copy.generic);
    const message = response.status === 413 ? copy.tooLarge : detail;
    throw Object.assign(new Error(message), { status: response.status });
  }
  return body as T;
}

export const won = (value: number) => money("ko", value);

const BRIEF_KEYS: (keyof Brief & keyof typeof COPY.ko.brief)[] = ["project_type", "summary", "current_process", "goals",
  "data_and_systems", "users_and_scale", "budget", "timeline", "open_questions"];

export const briefFields = (lang: Lang): [keyof Brief, string][] => BRIEF_KEYS.map(key => [key, COPY[lang].brief[key]]);
export const BRIEF_FIELDS = briefFields("ko");

/** Creates a self-serve sample quote (never charged) and returns its page path. */
export async function createDemoQuote(title?: string, lang: Lang = "ko") {
  const result = await api<{ path: string }>("/api/quotes/demo", { method: "POST", body: JSON.stringify({ ...(title ? { title } : {}), lang }) }, lang);
  return result.path;
}
