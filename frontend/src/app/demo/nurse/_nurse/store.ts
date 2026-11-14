"use client";

import { useCallback, useSyncExternalStore } from "react";
import { BUILTIN_IMAGES, CENTER, DEMO_ADMIN, INITIAL_INQUIRIES, INITIAL_POSTS, type ImageItem, type Inquiry, type Mail, type Post } from "./data";

// 샘플 상태는 이 브라우저의 localStorage에만 저장한다. 홈페이지 탭과 관리자 탭이 같은 상태를 보고,
// 한쪽에서 바꾸면 storage 이벤트로 다른 탭에도 바로 반영된다.
// 실제 구축에서는 이 자리를 서버 API + DB가 대신한다(비밀번호는 해시로만 저장).
const KEY = "nurse-demo-v1";
const CODE_TTL_MS = 10 * 60 * 1000;

/** real: 실제 메일로 보낸 코드(서버가 확인). 아니면 데모 메일함에만 보여 주는 코드. */
export type PendingCode = { kind: "reset" | "email"; code: string; target: string; expiresAt: number; real?: boolean };
/** mode: real = 실제 메일 발송, local = 데모 메일함에 표시. note: 실제 발송에 실패해 데모 메일함으로 대신한 경우 안내. */
export type CodeResult = { error?: string; mode?: "real" | "local"; note?: string };
export type NurseState = {
  posts: Post[]; images: ImageItem[]; inquiries: Inquiry[]; mails: Mail[];
  account: { email: string; password: string };
  loggedIn: boolean; pending: PendingCode | null; mailFail: boolean;
};

const now = () => new Date().toISOString();
export const uid = () => Math.random().toString(36).slice(2, 9);
const code6 = () => String(Math.floor(100000 + Math.random() * 900000));

function initial(): NurseState {
  return {
    posts: INITIAL_POSTS, images: BUILTIN_IMAGES, inquiries: INITIAL_INQUIRIES,
    mails: [{ id: "m0", at: "2026-11-13T15:42:10", to: DEMO_ADMIN.email, subject: "[상담 신청] 이*정 님 (양천구)", body: "홈페이지에서 새 상담 신청이 접수되었습니다.", ok: true }],
    account: { ...DEMO_ADMIN }, loggedIn: false, pending: null, mailFail: false,
  };
}

let cache: NurseState | null = null;
const listeners = new Set<() => void>();

function read(): NurseState {
  if (cache) return cache;
  try {
    const raw = window.localStorage.getItem(KEY);
    cache = raw ? (JSON.parse(raw) as NurseState) : initial();
  } catch { cache = initial(); }
  return cache;
}
/** 저장에 실패하면(브라우저 저장 공간 초과 등) false. 상태는 메모리에는 반영된다. */
function write(next: NurseState): boolean {
  cache = next;
  let ok = true;
  try { window.localStorage.setItem(KEY, JSON.stringify(next)); } catch { ok = false; }
  listeners.forEach(l => l());
  return ok;
}
function subscribe(l: () => void) {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => { if (e.key === KEY) { cache = null; l(); } };
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(l); window.removeEventListener("storage", onStorage); };
}
const serverState = initial();

function mail(s: NurseState, to: string, subject: string, body: string, ok = true): Mail[] {
  return [{ id: uid(), at: now(), to, subject, body, ok }, ...s.mails].slice(0, 40);
}

/** 받을 수 없는 예시 도메인(기본 데모 계정 등)은 실제로 보내지 않고 데모 메일함에만 보여 준다. */
export const isDeliverable = (email: string) => !/\.(example|test|invalid|localhost|local)$/i.test(email.trim());
const LABEL = { reset: "비밀번호 재설정 인증코드", email: "이메일 변경 인증코드" } as const;

type ApiResult = { ok: true } | { ok: false; status: number; detail: string };
async function callApi(path: "code" | "verify", body: Record<string, string>): Promise<ApiResult> {
  try {
    const r = await fetch(`/api/demo/nurse/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.ok) return { ok: true };
    let detail = "";
    try { const j = await r.json(); if (typeof j.detail === "string") detail = j.detail; } catch { /* 본문 없음 */ }
    return { ok: false, status: r.status, detail };
  } catch { return { ok: false, status: 0, detail: "" }; }
}

/** 인증코드 발송. 실제 주소면 서버가 메일을 보내고, 서버가 응답하지 않으면 데모 메일함으로 대신한다. */
async function issueCode(kind: PendingCode["kind"], target: string): Promise<CodeResult> {
  let note: string | undefined;
  if (isDeliverable(target)) {
    const r = await callApi("code", { purpose: kind, email: target });
    if (r.ok) {
      const s = read();
      write({ ...s, pending: { kind, code: "", target, expiresAt: Date.now() + CODE_TTL_MS, real: true },
        mails: mail(s, target, `[늘곁방문간호센터 샘플] ${LABEL[kind]}`, "실제 메일로 발송했습니다. 인증코드는 받은 메일함에서 확인해 주세요.") });
      return { mode: "real" };
    }
    if (r.status === 400 || r.status === 422 || r.status === 429) return { error: r.detail || "요청을 처리하지 못했습니다." };
    note = "지금은 메일을 보내지 못해 데모 메일함에 대신 표시합니다.";
  }
  const c = code6();
  const s = read();
  write({ ...s, pending: { kind, code: c, target, expiresAt: Date.now() + CODE_TTL_MS },
    mails: mail(s, target, `[늘곁 관리자] ${LABEL[kind]}`, `인증코드: ${c}\n10분 안에 입력해 주세요. 요청하지 않으셨다면 이 메일을 무시하세요.`) });
  return { mode: "local", note };
}

export function useNurse() {
  const state = useSyncExternalStore(subscribe, read, () => serverState);
  const update = useCallback((fn: (s: NurseState) => NurseState) => write(fn(read())), []);

  const actions = {
    reset: () => write(initial()),

    /* ---------- 홈페이지: 상담 신청 ---------- */
    /** 접수는 먼저 저장하고, 메일 발송 결과는 따로 남긴다. 메일이 실패해도 접수는 사라지지 않는다. */
    submitInquiry: (f: Omit<Inquiry, "id" | "at" | "status" | "mail">): Inquiry => {
      const s = read();
      const ok = !s.mailFail;
      const item: Inquiry = { ...f, id: uid(), at: now(), status: "new", mail: ok ? "sent" : "failed" };
      write({ ...s, inquiries: [item, ...s.inquiries],
        mails: mail(s, s.account.email, `[상담 신청] ${f.name} 님 (${f.area || "지역 미입력"})`,
          `홈페이지에서 새 상담 신청이 접수되었습니다.\n\n이름: ${f.name}\n연락처: ${f.phone}\n관계: ${f.relation}\n지역: ${f.area}\n장기요양 등급: ${f.grade}\n희망 연락 시간: ${f.time}\n\n${f.message}`, ok) });
      return item;
    },
    setInquiryStatus: (id: string, status: Inquiry["status"]) => update(s => ({ ...s, inquiries: s.inquiries.map(q => q.id === id ? { ...q, status } : q) })),
    resendInquiry: (id: string) => update(s => {
      const q = s.inquiries.find(x => x.id === id);
      if (!q) return s;
      const ok = !s.mailFail;
      return { ...s, inquiries: s.inquiries.map(x => x.id === id ? { ...x, mail: ok ? "sent" : "failed" } : x),
        mails: mail(s, s.account.email, `[상담 신청·재발송] ${q.name} 님 (${q.area})`, `미발송 상담 신청을 다시 보냅니다.\n\n${q.message}`, ok) };
    }),
    setMailFail: (v: boolean) => update(s => ({ ...s, mailFail: v })),

    /* ---------- 관리자 인증 ---------- */
    login: (email: string, password: string): string | null => {
      const s = read();
      if (!email.trim() || !password) return "이메일과 비밀번호를 입력해 주세요.";
      if (email.trim().toLowerCase() !== s.account.email.toLowerCase() || password !== s.account.password) return "이메일 또는 비밀번호가 맞지 않습니다.";
      write({ ...s, loggedIn: true });
      return null;
    },
    logout: () => update(s => ({ ...s, loggedIn: false })),
    /** 비밀번호 찾기 1단계: 등록된 관리자 이메일로 인증코드를 보낸다. */
    requestReset: async (email: string): Promise<CodeResult> => {
      const s = read();
      if (email.trim().toLowerCase() !== s.account.email.toLowerCase()) return { error: "등록된 관리자 이메일이 아닙니다." };
      return issueCode("reset", s.account.email);
    },
    /** 이메일 변경 1단계: 현재 비밀번호를 확인하고 새 이메일로 인증코드를 보낸다. */
    requestEmailChange: async (newEmail: string, password: string): Promise<CodeResult> => {
      const s = read();
      const e = newEmail.trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return { error: "이메일 형식을 확인해 주세요." };
      if (e.toLowerCase() === s.account.email.toLowerCase()) return { error: "지금 쓰는 이메일과 같습니다." };
      if (password !== s.account.password) return { error: "현재 비밀번호가 맞지 않습니다." };
      return issueCode("email", e);
    },
    /** 인증코드 확인. 비밀번호 재설정이면 newPassword를 함께 받는다. 실제로 보낸 코드는 서버가 확인한다. */
    verifyCode: async (kind: PendingCode["kind"], input: string, newPassword?: string): Promise<string | null> => {
      const p = read().pending;
      if (!p || p.kind !== kind) return "인증 요청 내역이 없습니다. 인증코드를 다시 받아 주세요.";
      if (kind === "reset" && (!newPassword || newPassword.length < 8)) return "새 비밀번호는 8자 이상으로 정해 주세요.";
      if (!/^\d{6}$/.test(input.trim())) return "6자리 숫자를 입력해 주세요.";
      if (p.real) {
        const r = await callApi("verify", { purpose: kind, email: p.target, code: input.trim() });
        if (!r.ok) return r.detail || "인증코드를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.";
      } else {
        if (Date.now() > p.expiresAt) return "인증코드가 만료되었습니다. 다시 받아 주세요.";
        if (input.trim() !== p.code) return "인증코드가 맞지 않습니다.";
      }
      const s = read();
      if (kind === "reset") {
        write({ ...s, pending: null, account: { ...s.account, password: newPassword! },
          mails: mail(s, s.account.email, "[늘곁 관리자] 비밀번호가 변경되었습니다", "관리자 비밀번호가 변경되었습니다. 본인이 아니라면 바로 연락 주세요.") });
      } else {
        write({ ...s, pending: null, account: { ...s.account, email: p.target },
          mails: mail(s, s.account.email, "[늘곁 관리자] 관리자 이메일이 변경되었습니다", `관리자 이메일이 ${p.target}(으)로 변경되었습니다. 본인이 아니라면 바로 연락 주세요.`) });
      }
      return null;
    },
    expireCode: () => update(s => s.pending && !s.pending.real ? { ...s, pending: { ...s.pending, expiresAt: Date.now() - 1 } } : s),
    changePassword: (current: string, next: string): string | null => {
      const s = read();
      if (current !== s.account.password) return "현재 비밀번호가 맞지 않습니다.";
      if (next.length < 8) return "새 비밀번호는 8자 이상으로 정해 주세요.";
      write({ ...s, account: { ...s.account, password: next } });
      return null;
    },

    /* ---------- 블로그 ---------- */
    savePost: (p: Post): string | null => {
      const s = read();
      if (!p.title.trim()) return "제목을 입력해 주세요.";
      if (!/^[a-z0-9가-힣-]+$/.test(p.slug)) return "주소(URL)는 영문 소문자·숫자·한글·하이픈(-)만 쓸 수 있습니다.";
      if (s.posts.some(x => x.slug === p.slug && x.id !== p.id)) return "같은 주소(URL)를 쓰는 글이 이미 있습니다.";
      const next = { ...p, updatedAt: now() };
      const exists = s.posts.some(x => x.id === p.id);
      return write({ ...s, posts: exists ? s.posts.map(x => x.id === p.id ? next : x) : [next, ...s.posts] }) ? null : "브라우저 저장 공간이 부족해 저장하지 못했습니다.";
    },
    deletePost: (id: string) => update(s => ({ ...s, posts: s.posts.filter(p => p.id !== id) })),

    /* ---------- 이미지 ---------- */
    addImage: (img: ImageItem): string | null => {
      const s = read();
      if (write({ ...s, images: [img, ...s.images] })) return null;
      write(s);
      return "브라우저 저장 공간이 부족합니다. 샘플에서는 사진을 몇 장만 올릴 수 있어요. (실제 구축은 서버 저장소를 사용합니다)";
    },
    replaceImage: (id: string, patch: Partial<ImageItem>): string | null => {
      const s = read();
      if (write({ ...s, images: s.images.map(i => i.id === id ? { ...i, ...patch } : i) })) return null;
      write(s);
      return "브라우저 저장 공간이 부족해 교체하지 못했습니다.";
    },
    deleteImage: (id: string) => update(s => ({ ...s, images: s.images.filter(i => i.id !== id), posts: s.posts.map(p => p.cover === id ? { ...p, cover: null } : p) })),
  };

  return { state, actions };
}

export function fmtDate(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}
export function fmtTime(iso: string) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
export function fmtBytes(n: number) {
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)}KB`;
  return `${(n / 1024 / 1024).toFixed(1)}MB`;
}
/** 글 주소 후보: 공백을 하이픈으로, 허용하지 않는 문자는 뺀다. */
export function slugify(title: string) {
  return title.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9가-힣-]/g, "").replace(/-+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
}
/** 본문 첫 문단에서 요약을 만든다(설명 미입력 시 기본값). */
export function excerpt(body: string, len = 90) {
  const first = body.split("\n").map(l => l.trim()).find(l => l && !l.startsWith("#") && !l.startsWith("-") && !l.startsWith("[이미지")) ?? "";
  return first.length > len ? first.slice(0, len - 1) + "…" : first;
}
export const SITE_BASE = "/demo/nurse/site";
export const postUrl = (slug: string) => `${SITE_BASE}#/blog/${slug}`;
/** 실제 구축 시 쓰일 공개 주소 예시(검색 미리보기·구조화 데이터용). */
export const PUBLIC_ORIGIN = "https://www.neulgyeot.example";
export const centerName = CENTER.name;

/** 블로그 글의 구조화 데이터(JSON-LD). 검색엔진·AI 검색이 글의 성격과 Q&A를 이해하도록 돕는다. */
export function postJsonLd(p: Post, images: ImageItem[]) {
  const img = images.find(i => i.id === p.cover);
  const graph: Record<string, unknown>[] = [{
    "@type": "BlogPosting",
    headline: p.seoTitle || p.title,
    description: p.seoDesc || excerpt(p.body, 120),
    datePublished: p.publishedAt ?? undefined,
    dateModified: p.updatedAt,
    url: `${PUBLIC_ORIGIN}/blog/${p.slug}`,
    ...(img ? { image: `${PUBLIC_ORIGIN}/images/${img.id}.webp` } : {}),
    author: { "@type": "Organization", name: CENTER.name },
    publisher: { "@type": "Organization", name: CENTER.name },
  }];
  if (p.faq.length) graph.push({
    "@type": "FAQPage",
    mainEntity: p.faq.map(f => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
  });
  return { "@context": "https://schema.org", "@graph": graph };
}
