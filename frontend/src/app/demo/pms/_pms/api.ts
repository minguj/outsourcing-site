// 운영 플랫폼(PMS) 데모 API. 방문자마다 서버 메모리의 샌드박스(가상 데이터)를 쓰고 역할은 X-Pms-User 로 바꾼다.

export type DemoUser = {
  id: string;
  name: string;
  role: string;
  role_label: string;
  sites: string[];
  permissions: string[];
};

export type Sandbox = {
  token: string;
  expires_in: number;
  operator: { name: string };
  users: DemoUser[];
};

export type Site = {
  id: string;
  name: string;
  asset_type: string;
  asset_label: string;
  owner: string;
  city: string;
  billing: { due_day: number; late_rate_pct: number };
  prices: Record<string, { label: string; price: number }>;
};

export type Unit = {
  id: string;
  site_id: string;
  building: string;
  floor: number;
  number: string;
  type: string;
  area_m2: number;
  status: "vacant" | "reserved" | "occupied" | "maintenance";
  status_label: string;
};

export type ResidentRow = {
  id: string;
  name: string;
  unit_id: string;
  unit_number: string | null;
  status: string;
  status_label: string;
};

export type Resident = {
  id: string;
  site_id: string;
  unit_id: string;
  name: string;
  birth_year: number;
  status: string;
  phone: string;
  guardian: { name: string; relation: string; phone: string };
  care: { level: string; notes: string; allergies: string[] } | null;
};

export type Contract = {
  id: string;
  site_id: string;
  unit_id: string;
  resident_id: string;
  resident_name: string | null;
  unit_number: string | null;
  status: string;
  status_label: string;
  start_date: string;
  end_date: string | null;
  deposit: number;
  monthly_fee: number;
  next: string[];
};

export type InvoiceLine = { code: string; label: string; quantity: number; unit_price: number; amount: number };

export type Invoice = {
  id: string;
  site_id: string;
  contract_id: string;
  resident_id: string;
  resident_name: string | null;
  unit_number: string | null;
  month: string;
  due_date: string;
  lines: InvoiceLine[];
  total: number;
  paid: number;
  outstanding: number;
  late_fee: number;
  status: "issued" | "partial" | "paid" | "overdue";
  payments: { id: string; amount: number; paid_on: string }[];
};

export type AuditEntry = {
  at: string;
  user_id: string;
  user_name: string;
  role: string;
  action: string;
  target: string;
  target_name: string;
  fields: string[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function json<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>;
  let message = "요청을 처리하지 못했습니다.";
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") message = body.detail;
  } catch {
    /* 본문 없음 */
  }
  throw new ApiError(res.status, message);
}

const BASE = "/api/demo/pms";

export function createSandbox(): Promise<Sandbox> {
  return fetch(`${BASE}/sandbox`, { method: "POST" }).then(json<Sandbox>);
}

export function client(token: string, userId: string) {
  const headers = { "X-Pms-Sandbox": token, "X-Pms-User": userId };
  const get = <T,>(path: string) => fetch(`${BASE}${path}`, { headers }).then(json<T>);
  const post = <T,>(path: string, body: unknown) =>
    fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<T>);
  return {
    sites: () => get<Site[]>("/sites"),
    units: (siteId: string) => get<Unit[]>(`/sites/${siteId}/units`),
    residents: (siteId: string) => get<ResidentRow[]>(`/sites/${siteId}/residents`),
    resident: (id: string) => get<Resident>(`/residents/${id}`),
    addUsage: (id: string, body: { service: string; quantity: number; date: string }) => post(`/residents/${id}/usages`, body),
    contracts: (siteId: string) => get<Contract[]>(`/sites/${siteId}/contracts`),
    transition: (id: string, to: string, date?: string) => post<Contract>(`/contracts/${id}/transition`, { to, ...(date ? { date } : {}) }),
    runBilling: (siteId: string, month: string) => post<{ created: string[]; skipped: string[] }>(`/sites/${siteId}/billing-runs`, { month }),
    invoices: (siteId: string, month: string, asOf: string) =>
      get<Invoice[]>(`/sites/${siteId}/invoices?month=${month}&as_of=${asOf}`),
    pay: (id: string, amount: number, paidOn: string, asOf: string) =>
      post<Invoice>(`/invoices/${id}/payments`, { amount, paid_on: paidOn, as_of: asOf }),
    audit: () => get<AuditEntry[]>("/audit"),
  };
}

export type Client = ReturnType<typeof client>;

export const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

export function todayKst(): string {
  const now = new Date(Date.now() + 9 * 3600_000);
  return now.toISOString().slice(0, 10);
}

export const PERMISSION_LABELS: Record<string, string> = {
  "site.read": "사업장 조회",
  "unit.read": "호실 현황",
  "contract.read": "계약 조회",
  "contract.write": "계약 상태 변경",
  "billing.read": "청구서 조회",
  "billing.write": "청구 실행·수납",
  "resident.read": "입주자 조회",
  "pii.read": "연락처 원문 열람",
  "health.read": "건강·돌봄 정보 열람",
  "service.write": "서비스 이용 기록",
  "audit.read": "감사 기록 조회",
};

export const CONTRACT_ACTIONS: Record<string, string> = {
  signed: "체결",
  active: "입주 처리",
  terminated: "해지(퇴거)",
  cancelled: "취소",
};

export const INVOICE_STATUS: Record<Invoice["status"], string> = {
  issued: "발행",
  partial: "부분 납부",
  paid: "완납",
  overdue: "연체",
};
