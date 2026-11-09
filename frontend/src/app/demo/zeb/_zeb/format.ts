export const n = (v: number, d = 0) =>
  v.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });

export const area = (v: number) => `${n(v, v % 1 ? 2 : 0)}㎡`;

export const krw = (v: number) => {
  if (v >= 1e8) return `${n(v / 1e8, 1)}억 원`;
  if (v >= 1e4) return `${n(Math.round(v / 1e4))}만 원`;
  return `${n(v)}원`;
};

export const gradeLabel = (g: string | null) => (g === null ? "등급 외" : g === "+" ? "플러스" : `${g}등급`);

export const SOURCE_KIND: Record<string, string> = {
  law: "법령",
  ordinance: "조례",
  notice: "고시·지침",
  assumption: "가정",
  input: "입력",
  data: "데이터",
};
