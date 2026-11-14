import Link from "next/link";

export default function NurseIntro() {
  return <div className="nc-intro">
    <section className="nc-intro-copy">
      <span className="nc-sample">샘플</span>
      <h1>방문간호센터<br />반응형 홈페이지 샘플</h1>
      <p>센터 소개, 방문간호 서비스, 이용 안내, 상담 신청, 건강 블로그까지 보호자 눈높이로 구성한 홈페이지와, 관리자 1명이 블로그·이미지·상담 접수를 직접 관리하는 관리자 화면입니다. 센터 이름과 연락처는 가상이며, 데이터는 이 브라우저 안에만 저장됩니다.</p>
      <ol>
        <li><b>홈페이지</b>에서 상담을 신청해 보세요. 접수 완료 화면이 나오고 관리자 화면에 바로 쌓입니다.</li>
        <li><b>관리자 화면</b>에서 블로그 글을 쓰고 발행하면 홈페이지 블로그에 즉시 나타납니다. 검색 제목·설명·주소와 자주 묻는 질문을 넣으면 검색 미리보기와 구조화 데이터가 함께 만들어집니다.</li>
        <li>비밀번호 찾기, 인증코드를 거친 관리자 이메일 변경, 메일 발송 실패 상황까지 눌러 볼 수 있습니다. 인증 메일은 화면의 ‘데모 메일함’에 표시됩니다.</li>
      </ol>
      <div className="nc-intro-links">
        <Link className="nc-ibtn" href="/demo/nurse/site" target="_blank">홈페이지 열기</Link>
        <Link className="nc-ibtn ghost" href="/demo/nurse/admin" target="_blank">관리자 화면 열기</Link>
      </div>
      <p className="nc-intro-note">사진 자리는 직접 그린 일러스트로 채웠습니다. 실제 구축에서는 센터가 제공한 사진과 원고로 바뀌고, 페이지마다 고유 주소와 검색 설정이 적용됩니다.</p>
    </section>
    <div className="nc-phone" aria-label="모바일 화면 미리보기"><iframe src="/demo/nurse/site" title="홈페이지 모바일 화면 샘플" /></div>
  </div>;
}
