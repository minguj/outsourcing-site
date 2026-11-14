import type { Metadata } from "next";
import "./nurse.css";

// 방문간호센터 홈페이지 제안용 샘플. 검색에 노출하지 않는다.
export const metadata: Metadata = {
  title: { default: "방문간호센터 홈페이지 샘플", template: "%s | 방문간호센터 홈페이지 샘플" },
  robots: { index: false, follow: false },
};

export default function NurseLayout({ children }: { children: React.ReactNode }) {
  return <div className="nc-root">{children}</div>;
}
