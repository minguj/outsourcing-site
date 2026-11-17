// 구독·고정지출 찾기 데모 API. 방문자마다 서버 메모리의 샌드박스(가상 거래내역)를 쓴다. 방문자 입력은 보내지 않는다.

export type Persona = {
  id: "jisoo" | "junghoon" | "haneul";
  name: string;
  summary: string;
  accounts: { id: string; label: string }[];
};

export type Sandbox = {
  token: string;
  expires_in: number;
  as_of: string;
  period: { from: string; to: string };
  personas: Persona[];
  ai_enabled: boolean;
};

export type Signal = {
  type: "price_increase" | "trial_conversion" | "fx" | "likely_cancelled" | "duplicate";
  label: string;
  date: string | null;
  detail: string;
};

export type CancelState = {
  method: "easy" | "guide";
  method_label: string;
  status: "processing" | "guide" | "done";
  status_label: string;
  requested_at: string;
  due_at?: string;
  done_at?: string;
  steps?: string[];
};

export type Series = {
  id: string;
  key: string;
  canonical: string;
  merchant_raw: string;
  aliases: string[];
  cancel_method: "easy" | "guide" | null;
  cancel: CancelState | null;
  service: string;
  category: string;
  category_label: string;
  kind: "subscription" | "fixed";
  kind_label: string;
  source: "dictionary" | "ai" | "rule";
  source_label: string;
  reason: string | null;
  review: "confirm" | "reject" | null;
  cadence: "monthly" | "weekly" | "yearly";
  cadence_label: string;
  count: number;
  first_date: string;
  last_date: string;
  next_date: string;
  amount_type: "fixed" | "variable" | "fx";
  amount_label: string;
  expected_amount: number;
  last_amount: number;
  currency: string | null;
  monthly_equivalent: number;
  status: "active" | "cancelled";
  confidence: number;
  signals: Signal[];
  transaction_ids: string[];
};

export type Alert = Upcoming & { d_day: number };

export type RegistryRow = {
  canonical: string;
  service: string;
  category_label: string;
  source: Series["source"];
  source_label: string;
  reason: string | null;
  aliases: string[];
  keys: string[];
  personas: string[];
  reports: { confirm: number; reject: number };
  needs_review: boolean;
};

export type Registry = {
  merchants: RegistryRow[];
  stats: {
    recurring_merchants: number;
    dictionary: number;
    ai: number;
    rule: number;
    coverage_pct: number;
    alias_merchants: number;
    general_merchants: number;
  };
};

export type Upcoming = { date: string; series_id: string; service: string; amount: number; amount_type: Series["amount_type"]; kind: Series["kind"] };

export type Saving = { type: "duplicate" | "trial" | "price"; title: string; services: string[]; series_ids: string[]; monthly: number; detail: string };

export type Tx = {
  id: string;
  account: string;
  date: string;
  at: string;
  merchant_raw: string;
  amount: number;
  type: "approval" | "cancel";
  method: "card" | "auto_transfer";
  orig_amount: number | null;
  orig_currency: string | null;
  approval_id?: string;
  series_id: string | null;
};

export type Analysis = {
  persona: Persona;
  as_of: string;
  period: { from: string; to: string };
  summary: {
    monthly_total: number;
    subscription_monthly: number;
    fixed_monthly: number;
    yearly_total: number;
    subscription_count: number;
    fixed_count: number;
    saved_monthly: number;
  };
  series: Series[];
  upcoming: Upcoming[];
  alerts: Alert[];
  savings: Saving[];
  savings_total: number;
  ai_pending: number;
  transactions: Tx[];
  enrich?: { asked: number; saved: number; status: "done" | "partial" | "no_ai" | "limit" | "failed" };
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function json<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : "요청을 처리하지 못했습니다.";
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

const BASE = "/api/demo/spend";

export function createSandbox(): Promise<Sandbox> {
  return fetch(`${BASE}/sandbox`, { method: "POST" }).then(json<Sandbox>);
}

export function client(token: string) {
  const headers = { "X-Spend-Sandbox": token, "Content-Type": "application/json" };
  return {
    analysis: (persona: string) => fetch(`${BASE}/personas/${persona}/analysis`, { headers }).then(json<Analysis>),
    enrich: (persona: string) => fetch(`${BASE}/personas/${persona}/enrich`, { method: "POST", headers }).then(json<Analysis>),
    review: (persona: string, seriesId: string, decision: "confirm" | "reject" | "reset") =>
      fetch(`${BASE}/personas/${persona}/series/${seriesId}/review`, {
        method: "POST",
        headers,
        body: JSON.stringify({ decision }),
      }).then(json<Analysis>),
    cancel: (persona: string, seriesId: string, action: "request" | "confirm" | "undo") =>
      fetch(`${BASE}/personas/${persona}/series/${seriesId}/cancel`, {
        method: "POST",
        headers,
        body: JSON.stringify({ action }),
      }).then(json<Analysis>),
    merchants: () => fetch(`${BASE}/merchants`, { headers }).then(json<Registry>),
  };
}

export type Client = ReturnType<typeof client>;

export const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

export const shortDate = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${Number(m)}월 ${Number(d)}일`;
};

export const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
