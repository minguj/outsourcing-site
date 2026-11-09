import type { Metadata } from "next";
import Link from "next/link";
import "./zeb.css";

// 건축 초기 기획(대지 규모 검토 + ZEB 신재생 시나리오) 데모. 검색에 노출하지 않는다.
export const metadata: Metadata = {
  title: { default: "ZEB 초기 기획 데모", template: "%s | ZEB 초기 기획 데모" },
  description: "대지 규모 검토와 제로에너지건축물(ZEB) 신재생 설비 시나리오를 한 화면에서 확인하는 데모",
  robots: { index: false, follow: false },
};

export default function ZebLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="zb-root">
      <header className="zb-topbar zb-no-print">
        <Link href="/demo/zeb" className="zb-brand">
          <span className="zb-brand-mark" aria-hidden>Z</span>
          ZEB 초기 기획
        </Link>
        <span className="zb-topbar-note">대지 규모 검토 + 신재생 설비 시나리오 · 샘플</span>
      </header>
      <main className="zb-main">{children}</main>
    </div>
  );
}
