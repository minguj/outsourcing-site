"use client";

import { useCallback, useSyncExternalStore } from "react";
import { COMPANIES, COUPONS, MY_COMPANY_ID, ROOMS, type Activity, type Company, type Coupon, type MyCoupon, type Usage } from "./data";
import { fmtDay, fmtMin, localDate, nowMinutes, seedBlocks, seedBookings, splitFree, validate, canCancel, occupies, type Block, type Booking, type BookingRequest } from "./rooms";

// 샘플 상태는 이 브라우저의 localStorage에만 저장한다. 앱 탭과 관리자 탭이 같은 상태를 보고,
// 한쪽에서 바꾸면 storage 이벤트로 다른 탭에도 바로 반영된다.
const KEY = "tower-demo-v1";

export type TowerState = {
  companies: Company[]; coupons: Coupon[]; mine: MyCoupon[]; usages: Usage[];
  favorites: string[]; activity: Activity[];
  /** 회의실 예약·사용 막기. roomsSeededOn: 샘플 예약을 만든 날짜 */
  bookings: Booking[]; blocks: Block[]; roomsSeededOn: string;
};

const now = () => new Date().toISOString();
const uid = () => Math.random().toString(36).slice(2, 9);

function initial(): TowerState {
  return {
    companies: COMPANIES, coupons: COUPONS, mine: [], favorites: [],
    // 회의실 샘플 예약은 날짜에 따라 달라서 서버 렌더링 값에는 넣지 않고, 브라우저에서 읽을 때 채운다(withRooms).
    bookings: [], blocks: [], roomsSeededOn: "",
    usages: [
      { id: "u1", couponId: "k1", storeId: "s1", member: "김*현", at: "2026-11-03T08:41:00" },
      { id: "u2", couponId: "k2", storeId: "s2", member: "이*진", at: "2026-11-03T12:12:00" },
      { id: "u3", couponId: "k1", storeId: "s1", member: "박*수", at: "2026-11-03T13:05:00" },
      { id: "u4", couponId: "k5", storeId: "s5", member: "최*아", at: "2026-11-03T14:20:00" },
    ],
    activity: [
      { id: "a1", at: "2026-11-03T14:20:00", text: "베이크하우스 쿠폰이 사용되었습니다." },
      { id: "a2", at: "2026-11-03T10:02:00", text: "우드앤코가 입주기업 인증을 신청했습니다." },
      { id: "a3", at: "2026-11-03T09:15:00", text: "미래로컨설팅이 입주기업 인증을 신청했습니다." },
      { id: "a4", at: "2026-11-02T17:40:00", text: "스텔라모빌리티가 입주기업 인증을 신청했습니다." },
    ],
  };
}

let cache: TowerState | null = null;
const listeners = new Set<() => void>();

/** 회의실 기능 이전에 저장된 상태에도 빈 항목을 채우고, 날짜가 바뀌었으면 샘플 예약만 오늘 기준으로 다시 만든다.
 *  사용자가 직접 한 예약과 관리자가 막아 둔 시간은 그대로 둔다. */
function withRooms(s: TowerState): TowerState {
  const today = localDate();
  if (s.roomsSeededOn === today && Array.isArray(s.bookings) && Array.isArray(s.blocks)) return s;
  const base = { ...initial(), ...s };
  return { ...base, roomsSeededOn: today,
    bookings: [...(base.bookings ?? []).filter(b => !b.seed), ...seedBookings(today, new Date().toISOString())],
    blocks: [...(base.blocks ?? []).filter(k => !k.id.startsWith("seed-")), ...seedBlocks(today)] };
}
function read(): TowerState {
  if (cache) return cache;
  let loaded: TowerState;
  try {
    const raw = window.localStorage.getItem(KEY);
    loaded = raw ? (JSON.parse(raw) as TowerState) : initial();
  } catch { loaded = initial(); }
  const next = withRooms(loaded);
  cache = next;
  if (next !== loaded) { try { window.localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* 메모리로만 동작 */ } }
  return cache;
}
function write(next: TowerState) {
  cache = next;
  try { window.localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* 저장 불가 환경: 메모리로만 동작 */ }
  listeners.forEach(l => l());
}
function subscribe(l: () => void) {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => { if (e.key === KEY) { cache = null; l(); } };
  window.addEventListener("storage", onStorage);
  return () => { listeners.delete(l); window.removeEventListener("storage", onStorage); };
}
const serverState = initial();

export function useTower() {
  const state = useSyncExternalStore(subscribe, read, () => serverState);
  const update = useCallback((fn: (s: TowerState) => TowerState) => write(fn(read())), []);
  const log = (s: TowerState, text: string): Activity[] => [{ id: uid(), at: now(), text }, ...s.activity].slice(0, 30);

  const actions = {
    reset: () => write(withRooms(initial())),
    toggleFavorite: (id: string) => update(s => ({ ...s, favorites: s.favorites.includes(id) ? s.favorites.filter(f => f !== id) : [...s.favorites, id] })),
    /** 쿠폰 받기: 한 사람이 같은 쿠폰을 한 번만 받는다. 수량이 남아 있어야 한다. */
    claim: (couponId: string): string | null => {
      const s = read(); const k = s.coupons.find(x => x.id === couponId);
      if (!k || !k.active) return "종료된 쿠폰입니다.";
      if (s.mine.some(m => m.couponId === couponId)) return "이미 받은 쿠폰입니다.";
      if (k.issued >= k.total) return "준비된 수량이 모두 소진되었습니다.";
      write({ ...s, coupons: s.coupons.map(x => x.id === couponId ? { ...x, issued: x.issued + 1 } : x),
        mine: [{ id: uid(), couponId, status: "issued", issuedAt: now() }, ...s.mine] });
      return null;
    },
    /** 쿠폰 사용: 매장 직원이 고객 화면에 상가 PIN을 입력한다. 한 번 쓰면 다시 쓸 수 없다. */
    redeem: (myId: string, pin: string, storePin: string, storeName: string): string | null => {
      const s = read(); const m = s.mine.find(x => x.id === myId);
      if (!m) return "쿠폰을 찾을 수 없습니다.";
      if (m.status === "used") return "이미 사용한 쿠폰입니다.";
      if (pin !== storePin) return "PIN이 맞지 않습니다. 매장 직원에게 확인해 주세요.";
      const k = s.coupons.find(x => x.id === m.couponId)!;
      write({ ...s,
        mine: s.mine.map(x => x.id === myId ? { ...x, status: "used", usedAt: now() } : x),
        coupons: s.coupons.map(x => x.id === k.id ? { ...x, used: x.used + 1 } : x),
        usages: [{ id: uid(), couponId: k.id, storeId: k.storeId, member: "샘*용", at: now() }, ...s.usages],
        activity: log(s, `${storeName} 쿠폰이 사용되었습니다.`) });
      return null;
    },
    approve: (id: string) => update(s => {
      const co = s.companies.find(x => x.id === id);
      return { ...s, companies: s.companies.map(x => x.id === id ? { ...x, status: "approved", reason: undefined } : x), activity: log(s, `${co?.name} 입주 인증을 승인했습니다.`) };
    }),
    reject: (id: string, reason: string) => update(s => {
      const co = s.companies.find(x => x.id === id);
      return { ...s, companies: s.companies.map(x => x.id === id ? { ...x, status: "rejected", reason } : x), activity: log(s, `${co?.name} 입주 인증을 반려했습니다.`) };
    }),
    setVisible: (id: string, visible: boolean) => update(s => ({ ...s, companies: s.companies.map(x => x.id === id ? { ...x, visible } : x) })),
    saveCompany: (co: Company) => update(s => {
      const exists = s.companies.some(x => x.id === co.id);
      return { ...s, companies: exists ? s.companies.map(x => x.id === co.id ? co : x) : [co, ...s.companies],
        activity: log(s, exists ? `${co.name} 기업 정보를 수정했습니다.` : `${co.name}을(를) 입주기업으로 등록했습니다.`) };
    }),
    addCoupon: (k: Omit<Coupon, "id" | "issued" | "used" | "active">) => update(s => ({ ...s,
      coupons: [{ ...k, id: uid(), issued: 0, used: 0, active: true }, ...s.coupons], activity: log(s, `쿠폰 '${k.title}'을 발행했습니다.`) })),
    setCouponActive: (id: string, active: boolean) => update(s => ({ ...s, coupons: s.coupons.map(x => x.id === id ? { ...x, active } : x) })),

    /* ---------- 회의실 ---------- */
    /** 예약: 세미나실처럼 승인이 필요한 방은 승인 대기, 나머지는 바로 확정. 월 무료 시간을 넘긴 만큼은 유료로 기록한다. */
    book: (req: BookingRequest): { error: string } | { booking: Booking } => {
      const s = read(); const room = ROOMS.find(r => r.id === req.roomId);
      const err = validate(req, room, s.bookings, s.blocks, localDate(), nowMinutes());
      if (err || !room) return { error: err ?? "회의실을 찾을 수 없습니다." };
      const { paid } = splitFree(MY_COMPANY_ID, req.date, req.end - req.start, s.bookings);
      const booking: Booking = { ...req, title: req.title.trim(), id: uid(), companyId: MY_COMPANY_ID, status: room.needsApproval ? "pending" : "confirmed", paidMinutes: paid, createdAt: now() };
      const who = s.companies.find(c => c.id === MY_COMPANY_ID)?.name;
      write({ ...s, bookings: [...s.bookings, booking],
        activity: log(s, `${who}이(가) ${room.name}을 ${fmtDay(req.date)} ${fmtMin(req.start)}에 ${room.needsApproval ? "예약 신청" : "예약"}했습니다.`) });
      return { booking };
    },
    /** 취소: 시작 전 예약만. 관리자가 취소하면 사유를 남긴다. */
    cancelBooking: (id: string, reason?: string): string | null => {
      const s = read(); const b = s.bookings.find(x => x.id === id);
      if (!b) return "예약을 찾을 수 없습니다.";
      if (!canCancel(b, localDate(), nowMinutes())) return "이미 시작했거나 끝난 예약은 취소할 수 없습니다.";
      const room = ROOMS.find(r => r.id === b.roomId)?.name;
      write({ ...s, bookings: s.bookings.map(x => x.id === id ? { ...x, status: "cancelled", reason } : x),
        activity: log(s, `${room} ${fmtDay(b.date)} ${fmtMin(b.start)} 예약이 ${reason ? "관리자에 의해 " : ""}취소되었습니다.`) });
      return null;
    },
    approveBooking: (id: string): string | null => {
      const s = read(); const b = s.bookings.find(x => x.id === id);
      if (!b || b.status !== "pending") return "승인 대기 중인 예약이 아닙니다.";
      if (!canCancel(b, localDate(), nowMinutes())) return "시작 시간이 지난 신청은 승인할 수 없습니다.";
      if (s.blocks.some(k => k.roomId === b.roomId && k.date === b.date && k.start < b.end && b.start < k.end)) return "사용을 막아 둔 시간과 겹칩니다.";
      const room = ROOMS.find(r => r.id === b.roomId)?.name;
      write({ ...s, bookings: s.bookings.map(x => x.id === id ? { ...x, status: "confirmed" } : x), activity: log(s, `${room} ${fmtDay(b.date)} 예약 신청을 승인했습니다.`) });
      return null;
    },
    rejectBooking: (id: string, reason: string) => update(s => {
      const b = s.bookings.find(x => x.id === id); const room = ROOMS.find(r => r.id === b?.roomId)?.name;
      return { ...s, bookings: s.bookings.map(x => x.id === id ? { ...x, status: "rejected", reason } : x), activity: log(s, `${room} 예약 신청을 반려했습니다.`) };
    }),
    /** 사용 막기: 이미 잡힌 예약과 겹치면 먼저 그 예약을 처리하도록 막는다. */
    addBlock: (k: Omit<Block, "id">): string | null => {
      const s = read();
      if (k.end <= k.start) return "종료 시간이 시작 시간보다 늦어야 합니다.";
      if (!k.reason.trim()) return "사유를 입력해 주세요.";
      const hit = s.bookings.filter(b => b.roomId === k.roomId && b.date === k.date && occupies(b) && b.start < k.end && k.start < b.end);
      if (hit.length) return `이 시간에 예약 ${hit.length}건이 있습니다. 예약을 먼저 취소하거나 반려해 주세요.`;
      const room = ROOMS.find(r => r.id === k.roomId)?.name;
      write({ ...s, blocks: [...s.blocks, { ...k, reason: k.reason.trim(), id: uid() }], activity: log(s, `${room} ${fmtDay(k.date)} ${fmtMin(k.start)}~${fmtMin(k.end)} 사용을 막았습니다.`) });
      return null;
    },
    removeBlock: (id: string) => update(s => ({ ...s, blocks: s.blocks.filter(k => k.id !== id) })),
  };
  return { state, actions, newId: uid };
}

/** 한글 초성 추출: "누리소프트" → "ㄴㄹㅅㅍㅌ" */
const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
export function chosung(text: string) {
  return [...text].map(ch => { const code = ch.charCodeAt(0) - 0xac00; return code >= 0 && code <= 11171 ? CHO[Math.floor(code / 588)] : ch; }).join("");
}
/** 이름·소개·보유 기술·서비스에서 부분 일치, 초성만 입력하면 기업명 초성으로 찾는다. */
export function matches(co: Company, q: string) {
  const query = q.trim().toLowerCase();
  if (!query) return true;
  const hay = [co.name, co.intro, co.industry, ...co.techs, ...co.services].join(" ").toLowerCase();
  if (hay.includes(query)) return true;
  return /^[ㄱ-ㅎ]+$/.test(query) && chosung(co.name).includes(query);
}

export const fmtTime = (iso: string) => { const d = new Date(iso); return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
