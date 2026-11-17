import type { Metadata } from "next";
import Link from "next/link";
import "./spend.css";

// 구독·고정지출 찾기 데모. 가상 거래내역만 쓰고 방문자 입력은 받지 않는다. 검색에 노출하지 않는다.
export const metadata: Metadata = {
  title: { default: "구독·고정지출 찾기 샘플", template: "%s | 구독·고정지출 찾기 샘플" },
  description: "카드·계좌 거래내역에서 구독과 고정지출을 찾아 가격 인상·중복 구독·절감 후보를 보여 주는 샘플",
  robots: { index: false, follow: false },
};

export default function SpendLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="sp-root">
      <header className="sp-topbar">
        <Link href="/demo/spend" className="sp-brand">
          <span className="sp-brand-mark" aria-hidden>₩</span>
          구독·고정지출 찾기
        </Link>
        <span className="sp-topbar-note">반복 결제 감지 + AI 가맹점 정리 · 가상 데이터 샘플</span>
      </header>
      <main className="sp-main">{children}</main>
    </div>
  );
}
