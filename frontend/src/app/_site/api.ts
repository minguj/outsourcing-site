export type Brief = {
  project_type?: string; title?: string; summary?: string; current_process?: string; goals?: string[];
  data_and_systems?: string; users_and_scale?: string; budget?: string; timeline?: string; open_questions?: string[];
};
export type ChatMessage = { role: "user" | "assistant"; content: string };

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    // FormData (file uploads) sets its own multipart boundary header.
    const json = !(init?.body instanceof FormData);
    response = await fetch(path, { ...init, headers: { ...(json ? { "Content-Type": "application/json" } : {}), ...(init?.headers ?? {}) } });
  } catch {
    throw new Error("서버에 연결하지 못했습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail
      : Array.isArray(body.detail) ? "입력값을 확인해 주세요." : "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
    const message = response.status === 413 ? "파일이 너무 큽니다. 10MB 이하로 줄여 주세요." : detail;
    throw Object.assign(new Error(message), { status: response.status });
  }
  return body as T;
}

export const won = (value: number) => `${new Intl.NumberFormat("ko-KR").format(value)}원`;

export const BRIEF_FIELDS: [keyof Brief, string][] = [
  ["project_type", "유형"], ["summary", "요약"], ["current_process", "현재 업무"], ["goals", "기대 효과"],
  ["data_and_systems", "문서·데이터·시스템"], ["users_and_scale", "사용자·규모"], ["budget", "예산"], ["timeline", "일정"],
  ["open_questions", "추가로 확인할 점"],
];

/** Creates a self-serve sample quote (never charged) and returns its page path. */
export async function createDemoQuote(title?: string) {
  const result = await api<{ path: string }>("/api/quotes/demo", { method: "POST", body: JSON.stringify(title ? { title } : {}) });
  return result.path;
}
