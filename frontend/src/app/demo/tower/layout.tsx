import type { Metadata } from "next";
import "./tower.css";

// 지식산업센터 통합 플랫폼 제안용 샘플. 검색에 노출하지 않는다.
export const metadata: Metadata = {
  title: { default: "지식산업센터 통합 플랫폼 샘플", template: "%s | 지식산업센터 통합 플랫폼 샘플" },
  robots: { index: false, follow: false },
};

export default function TowerLayout({ children }: { children: React.ReactNode }) {
  return <div className="tw-root">{children}</div>;
}
