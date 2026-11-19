// 회의실 예약 규칙. 화면과 상태 저장(store.ts)에서 같이 쓰도록 React 없이 순수 함수로 둔다.
import type { Room } from "./data";

export type BookingStatus = "confirmed" | "pending" | "rejected" | "cancelled";
export type Booking = {
  id: string; roomId: string;
  /** YYYY-MM-DD (브라우저 현지 날짜) */
  date: string;
  /** 0시부터 지난 분. 09:30 → 570 */
  start: number; end: number;
  companyId: string; title: string; attendees: number;
  status: BookingStatus;
  /** 무료 시간을 넘겨 유료로 잡힌 분 */
  paidMinutes: number;
  createdAt: string; reason?: string;
  /** 샘플 초기 예약. 날짜가 바뀌면 오늘 기준으로 다시 만든다. */
  seed?: boolean;
};
export type Block = { id: string; roomId: string; date: string; start: number; end: number; reason: string };

export const OPEN = 9 * 60;
export const CLOSE = 21 * 60;
export const SLOT = 30;
export const BOOK_DAYS = 14;
export const FREE_MINUTES = 8 * 60;

const pad = (n: number) => String(n).padStart(2, "0");
export const localDate = (d: Date = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const nowMinutes = (d: Date = new Date()) => d.getHours() * 60 + d.getMinutes();
export function addDays(date: string, n: number) {
  const [y, m, d] = date.split("-").map(Number);
  return localDate(new Date(y, m - 1, d + n));
}
/** 예약 가능한 날짜: 오늘부터 14일 */
export const bookingDays = (today: string) => Array.from({ length: BOOK_DAYS }, (_, i) => addDays(today, i));
export const slotStarts = () => Array.from({ length: (CLOSE - OPEN) / SLOT }, (_, i) => OPEN + i * SLOT);
export const fmtMin = (m: number) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
export const fmtDuration = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}시간` : "") + (m % 60 ? ` ${m % 60}분` : "");
const WEEK = ["일", "월", "화", "수", "목", "금", "토"];
export function fmtDay(date: string, today?: string) {
  if (today && date === today) return "오늘";
  if (today && date === addDays(today, 1)) return "내일";
  const [y, m, d] = date.split("-").map(Number);
  return `${m}/${d}(${WEEK[new Date(y, m - 1, d).getDay()]})`;
}
export const isWeekend = (date: string) => { const [y, m, d] = date.split("-").map(Number); const w = new Date(y, m - 1, d).getDay(); return w === 0 || w === 6; };

/** 시간을 차지하는 예약: 확정과 승인 대기 */
export const occupies = (b: Booking) => b.status === "confirmed" || b.status === "pending";
const overlap = (a: { start: number; end: number }, b: { start: number; end: number }) => a.start < b.end && b.start < a.end;

export type SlotState = "free" | "booked" | "pending" | "blocked" | "past";
export function slotState(roomId: string, date: string, start: number, bookings: Booking[], blocks: Block[], today: string, now: number): SlotState {
  const cell = { start, end: start + SLOT };
  if (blocks.some(k => k.roomId === roomId && k.date === date && overlap(k, cell))) return "blocked";
  const b = bookings.find(x => x.roomId === roomId && x.date === date && occupies(x) && overlap(x, cell));
  if (b) return b.status === "pending" ? "pending" : "booked";
  if (date < today || (date === today && start < now)) return "past";
  return "free";
}

/** 그 달에 회사가 잡은 시간(확정+승인 대기). 무료 시간 계산용 */
export function usedMinutes(companyId: string, month: string, bookings: Booking[], exceptId?: string) {
  return bookings.filter(b => b.companyId === companyId && b.date.startsWith(month) && occupies(b) && b.id !== exceptId)
    .reduce((a, b) => a + (b.end - b.start), 0);
}
/** 이번 예약 중 무료·유료로 나뉘는 분 */
export function splitFree(companyId: string, date: string, minutes: number, bookings: Booking[]) {
  const left = Math.max(FREE_MINUTES - usedMinutes(companyId, date.slice(0, 7), bookings), 0);
  const free = Math.min(left, minutes);
  return { free, paid: minutes - free, left };
}

export type BookingRequest = { roomId: string; date: string; start: number; end: number; attendees: number; title: string };
/** 예약 가능 여부. 문제가 없으면 null, 있으면 사용자에게 보여 줄 문장 */
export function validate(req: BookingRequest, room: Room | undefined, bookings: Booking[], blocks: Block[], today: string, now: number): string | null {
  if (!room) return "회의실을 찾을 수 없습니다.";
  if (req.date < today || req.date > addDays(today, BOOK_DAYS - 1)) return `오늘부터 ${BOOK_DAYS}일 안에서만 예약할 수 있습니다.`;
  if (req.start % SLOT || req.end % SLOT) return "30분 단위로 예약해 주세요.";
  if (req.start < OPEN || req.end > CLOSE) return `운영 시간(${fmtMin(OPEN)}~${fmtMin(CLOSE)}) 안에서 예약해 주세요.`;
  if (req.end <= req.start) return "종료 시간이 시작 시간보다 늦어야 합니다.";
  if (req.date === today && req.start < now) return "이미 지난 시간입니다.";
  if (req.end - req.start > room.maxMinutes) return `${room.name}은 한 번에 최대 ${fmtDuration(room.maxMinutes).trim()}까지 예약할 수 있습니다.`;
  if (!req.title.trim()) return "회의 목적을 입력해 주세요.";
  if (!(req.attendees >= 1)) return "참석 인원을 입력해 주세요.";
  if (req.attendees > room.capacity) return `${room.name} 최대 인원은 ${room.capacity}명입니다.`;
  if (blocks.some(k => k.roomId === req.roomId && k.date === req.date && overlap(k, req))) return "관리자가 사용을 막아 둔 시간입니다.";
  if (bookings.some(b => b.roomId === req.roomId && b.date === req.date && occupies(b) && overlap(b, req))) return "다른 예약과 시간이 겹칩니다.";
  return null;
}

/** 선택한 시작 시각부터 이어서 비어 있는 만큼 고를 수 있는 사용 시간(분) 목록 */
export function durationOptions(room: Room, date: string, start: number, bookings: Booking[], blocks: Block[], today: string, now: number) {
  const out: number[] = [];
  for (let end = start + SLOT; end <= Math.min(CLOSE, start + room.maxMinutes); end += SLOT) {
    if (slotState(room.id, date, end - SLOT, bookings, blocks, today, now) !== "free") break;
    out.push(end - start);
  }
  return out;
}

/** 시작 전인 확정·승인 대기 예약만 취소할 수 있다 */
export const canCancel = (b: Booking, today: string, now: number) => occupies(b) && (b.date > today || (b.date === today && b.start > now));

/** 그날 확정 예약이 운영 시간 중 차지한 비율(%) */
export function utilization(date: string, rooms: Room[], bookings: Booking[]) {
  const used = bookings.filter(b => b.date === date && b.status === "confirmed").reduce((a, b) => a + (b.end - b.start), 0);
  return Math.round((used / (rooms.length * (CLOSE - OPEN))) * 100);
}

/** 샘플 초기 예약: 오늘 기준 상대 날짜로 만든다 (언제 열어도 오늘·내일 일정이 차 있게) */
export function seedBookings(today: string, createdAt: string): Booking[] {
  const h = (t: string) => { const [a, b] = t.split(":").map(Number); return a * 60 + b; };
  const rows: [number, string, string, string, string, string, number, BookingStatus][] = [
    [0, "r1", "10:00", "11:00", "c02", "패키지 시안 리뷰", 3, "confirmed"],
    [0, "r2", "14:00", "16:00", "c03", "고객사 도면 검토", 6, "confirmed"],
    [0, "r3", "09:30", "11:30", "c04", "부가세 신고 설명회", 12, "confirmed"],
    [0, "r4", "13:00", "14:00", "c01", "고객사 화상 미팅", 4, "confirmed"],
    [0, "r5", "15:00", "18:00", "c05", "신제품 설명회", 35, "pending"],
    [1, "r1", "09:00", "10:00", "c03", "주간 회의", 4, "confirmed"],
    [1, "r2", "10:00", "12:00", "c01", "MES 요구사항 회의", 7, "confirmed"],
    [1, "r3", "16:00", "18:00", "c02", "브랜드 워크숍", 14, "confirmed"],
    [1, "r5", "10:00", "12:00", "c04", "입주사 세무 세미나", 30, "confirmed"],
    [2, "r4", "11:00", "12:00", "c05", "해외 바이어 화상 상담", 5, "confirmed"],
    [2, "r2", "15:00", "17:00", "c02", "신규 고객 킥오프", 8, "confirmed"],
    [3, "r5", "14:00", "17:00", "c03", "협력사 기술 교육", 25, "pending"],
  ];
  // 이번 달에 이미 쓴 무료 시간(누리소프트): 오늘 이전이면서 같은 달인 날만 넣는다
  const past: [number, string, string, string, string][] = [[-2, "r2", "10:00", "12:00", "스프린트 회고"], [-5, "r1", "14:00", "15:00", "채용 면접"]];
  const out: Booking[] = rows.map(([d, roomId, s, e, companyId, title, attendees, status], i) => ({
    id: `seed-b${i + 1}`, roomId, date: addDays(today, d), start: h(s), end: h(e), companyId, title, attendees, status, paidMinutes: 0, createdAt, seed: true }));
  past.forEach(([d, roomId, s, e, title], i) => {
    const date = addDays(today, d);
    if (date.slice(0, 7) === today.slice(0, 7)) out.push({ id: `seed-p${i + 1}`, roomId, date, start: h(s), end: h(e), companyId: "c01", title, attendees: 4, status: "confirmed", paidMinutes: 0, createdAt, seed: true });
  });
  return out;
}
export const seedBlocks = (today: string): Block[] => [{ id: "seed-k1", roomId: "r3", date: addDays(today, 3), start: 13 * 60, end: 17 * 60, reason: "빔프로젝터 점검" }];
