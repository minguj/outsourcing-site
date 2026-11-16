import type { Metadata } from "next";
import Link from "next/link";
import "./pms.css";

// 운영 플랫폼(PMS) 데모. 여러 사업장을 위탁 운영하는 가상 운영사. 검색에 노출하지 않는다.
export const metadata: Metadata = {
  title: { default: "운영 플랫폼(PMS) 샘플", template: "%s | 운영 플랫폼(PMS) 샘플" },
  description: "여러 사업장의 호실·계약·청구·수납과 역할별 권한을 한 화면에서 체험하는 운영 플랫폼 샘플",
  robots: { index: false, follow: false },
};

export default function PmsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="pm-root">
      <header className="pm-topbar">
        <Link href="/demo/pms" className="pm-brand">
          <span className="pm-brand-mark" aria-hidden>P</span>
          운영 플랫폼(PMS)
        </Link>
        <span className="pm-topbar-note">사업장·호실·계약·청구 + 역할별 권한 · 가상 데이터 샘플</span>
      </header>
      <main className="pm-main">{children}</main>
    </div>
  );
}
