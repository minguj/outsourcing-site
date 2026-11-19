import Link from "next/link";

export default function TowerIntro() {
  return <div className="tw-intro">
    <section className="tw-intro-copy">
      <span className="tw-sample">샘플</span>
      <h1>지식산업센터 통합 플랫폼<br />핵심 기능 샘플</h1>
      <p>입주기업 디렉토리, 상가 쿠폰, 회의실 예약, 관리자 웹(입주 인증 승인·쿠폰·회의실 관리·대시보드)을 실제로 눌러 볼 수 있게 만든 샘플입니다. 데이터는 모두 가상이며 이 브라우저 안에만 저장됩니다.</p>
      <ol>
        <li><b>앱 화면</b>에서 기업을 검색하고, 상가 혜택에서 쿠폰을 받아 '내 쿠폰'에서 사용해 보세요. 매장 PIN은 1234입니다.</li>
        <li><b>관리자 웹</b>을 다른 탭에 열어 두면, 앱에서 쓴 쿠폰이 사용 내역과 대시보드에 바로 반영됩니다.</li>
        <li>관리자 웹에서 승인 대기 기업을 <b>승인</b>하면 앱의 입주기업 목록에 바로 나타납니다.</li>
        <li>앱의 <b>회의실</b> 탭에서 날짜와 시간을 골라 예약해 보세요. 관리자 웹 회의실 타임라인에 바로 표시되고, 세미나실은 관리자가 승인해야 확정됩니다.</li>
      </ol>
      <div className="tw-intro-links">
        <Link className="tw-btn" href="/demo/tower/app" target="_blank">앱 화면 열기</Link>
        <Link className="tw-btn ghost" href="/demo/tower/admin" target="_blank">관리자 웹 열기</Link>
      </div>
      <p className="tw-intro-note">샘플은 화면 흐름과 운영 방식을 확인하기 위한 웹 버전입니다. 실제 구축은 iOS·Android 앱과 관리자 웹으로 진행합니다.</p>
    </section>
    <div className="tw-phone" aria-label="앱 화면 미리보기"><iframe src="/demo/tower/app" title="앱 화면 샘플" /></div>
  </div>;
}
