"use client";

import { Fragment, useEffect, useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import { Art, Pic } from "../_nurse/art";
import { ABOUT, AREAS, CENTER, DOCUMENTS, FAQ, SERVICES, SITUATIONS, STATS, STEPS, type ImageItem, type Inquiry, type Post } from "../_nurse/data";
import { excerpt, fmtDate, postJsonLd, useNurse } from "../_nurse/store";

// 페이지 이동은 해시(#/about)로 한다. 샘플은 한 화면 안에서 동작하고, 실제 구축에서는 페이지마다 고유 주소(/about)를 쓴다.
function subscribeHash(l: () => void) { window.addEventListener("hashchange", l); return () => window.removeEventListener("hashchange", l); }
function useRoute(): string[] {
  const hash = useSyncExternalStore(subscribeHash, () => window.location.hash, () => "");
  return hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
}
const NAV: [string, string][] = [["about", "센터 소개"], ["services", "방문간호 서비스"], ["guide", "이용 안내"], ["blog", "건강 블로그"]];

export default function SiteView() {
  const route = useRoute();
  const { state } = useNurse();
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState("");
  const key = route.join("/");
  const say = (t: string) => { setToast(t); window.setTimeout(() => setToast(""), 2600); };
  const kakao = () => say("실제 사이트에서는 센터 카카오톡 오픈채팅방으로 연결됩니다.");
  const call = () => say(`샘플 번호입니다. 실제 사이트에서는 ${CENTER.phone}로 바로 전화가 연결됩니다.`);

  useEffect(() => { window.scrollTo(0, 0); }, [key]);

  const published = state.posts.filter(p => p.status === "published").sort((a, b) => (b.publishedAt ?? "").localeCompare(a.publishedAt ?? ""));
  const [page, sub] = route;
  let body: ReactNode;
  if (!page) body = <Home posts={published.slice(0, 3)} images={state.images} call={call} />;
  else if (page === "about") body = <About />;
  else if (page === "services" && sub) body = <ServiceDetail id={sub} />;
  else if (page === "services") body = <Services />;
  else if (page === "guide") body = <Guide />;
  else if (page === "blog" && sub) body = <BlogPost post={published.find(p => p.slug === sub)} images={state.images} others={published.filter(p => p.slug !== sub).slice(0, 2)} />;
  else if (page === "blog") body = <BlogList posts={published} images={state.images} />;
  else if (page === "consult") body = <Consult call={call} kakao={kakao} />;
  else body = <NotFound />;

  return <div className="nc-site">
    <a className="nc-skip" href="#nc-main">본문 바로가기</a>
    <header className="nc-header">
      <div className="nc-wrap nc-header-in">
        <a className="nc-logo" href="#/" onClick={() => setMenuOpen(false)}><Mark />{CENTER.name}</a>
        <button className="nc-menu-btn" aria-expanded={menuOpen} aria-controls="nc-gnb" onClick={() => setMenuOpen(v => !v)}>{menuOpen ? "닫기" : "메뉴"}</button>
        <nav id="nc-gnb" className={"nc-gnb" + (menuOpen ? " open" : "")} aria-label="주요 메뉴">
          {NAV.map(([id, label]) => <a key={id} href={`#/${id}`} className={page === id ? "on" : ""} aria-current={page === id ? "page" : undefined} onClick={() => setMenuOpen(false)}>{label}</a>)}
          <a href="#/consult" className="nc-gnb-cta" onClick={() => setMenuOpen(false)}>상담 신청</a>
        </nav>
      </div>
    </header>

    <main id="nc-main">{body}</main>

    <footer className="nc-footer">
      <div className="nc-wrap nc-footer-in">
        <div>
          <strong className="nc-logo light"><Mark />{CENTER.name}</strong>
          <p>{CENTER.address}<br />대표전화 {CENTER.phone} · {CENTER.email}<br />{CENTER.hours}<br />{CENTER.regNo}</p>
        </div>
        <nav aria-label="하단 메뉴">
          {NAV.map(([id, label]) => <a key={id} href={`#/${id}`}>{label}</a>)}
          <a href="#/consult">상담 신청</a>
          <a href="#/privacy" onClick={e => { e.preventDefault(); say("실제 사이트에는 센터와 협의한 개인정보처리방침이 들어갑니다."); }}>개인정보처리방침</a>
        </nav>
      </div>
      <p className="nc-wrap nc-copy">이 화면은 핏에이전트가 만든 홈페이지 샘플입니다. 센터 이름·연락처·수치는 모두 가상입니다.</p>
    </footer>

    <button className="nc-kakao" onClick={kakao} aria-label="카카오톡 오픈채팅 상담"><KakaoIcon /><span>카카오톡 상담</span></button>
    <nav className="nc-mbar" aria-label="빠른 상담">
      <button onClick={call}><PhoneIcon />전화</button>
      <button onClick={kakao}><KakaoIcon />카카오톡</button>
      <a href="#/consult" className="primary">상담 신청</a>
    </nav>
    {toast && <div className="nc-toast" role="status">{toast}</div>}
  </div>;
}

/* ---------- 메인 ---------- */
function Home({ posts, images, call }: { posts: Post[]; images: ImageItem[]; call: () => void }) {
  return <>
    <section className="nc-hero">
      <div className="nc-wrap nc-hero-in">
        <div className="nc-hero-copy">
          <p className="nc-eyebrow">서울 서남권 방문간호</p>
          <h1>병원에서 받던 간호,<br />이제 집에서 이어 가세요.</h1>
          <p>간호사가 어르신 댁으로 찾아가 상처·관 관리, 복약과 만성질환 관리를 돕습니다. 간호사가 돌아간 뒤에도 가족이 안심할 수 있도록 돌봄 방법까지 함께 알려 드립니다.</p>
          <div className="nc-hero-cta">
            <a className="nc-btn" href="#/consult">상담 신청하기</a>
            <button className="nc-btn ghost" onClick={call}><PhoneIcon />{CENTER.phone}</button>
          </div>
          <p className="nc-hero-note">{CENTER.hours}</p>
        </div>
        <figure className="nc-hero-pic"><Art k="home" label="간호사가 어르신 댁을 방문한 모습" /><figcaption>장기요양 지정 방문간호기관</figcaption></figure>
      </div>
    </section>

    <section className="nc-stats" aria-label="센터 현황">
      <div className="nc-wrap"><ul>{STATS.map(s => <li key={s.label}><strong>{s.value}</strong><span>{s.label}</span></li>)}</ul></div>
    </section>

    <section className="nc-sec">
      <div className="nc-wrap">
        <SecHead kicker="Home Nursing" title="방문간호 서비스" lead="방문간호지시서에 따라 간호사가 직접 방문해 필요한 간호를 제공합니다." more={["#/services", "서비스 전체 보기"]} />
        <ul className="nc-cards">{SERVICES.map(s => <li key={s.id}>
          <a className="nc-card" href={`#/services/${s.id}`}><Art k={s.art} /><div><h3>{s.title}</h3><p>{s.summary}</p><span className="nc-more">자세히 보기</span></div></a>
        </li>)}</ul>
      </div>
    </section>

    <section className="nc-sec tint">
      <div className="nc-wrap">
        <SecHead kicker="When You Need" title="이럴 때 찾아 주세요" />
        <ul className="nc-situations">{SITUATIONS.map(s => <li key={s.title}><Art k={s.art} /><div><h3>{s.title}</h3><p>{s.text}</p></div></li>)}</ul>
      </div>
    </section>

    <section className="nc-sec">
      <div className="nc-wrap">
        <SecHead kicker="How to Start" title="이용 절차" lead="처음이셔도 괜찮습니다. 등급 신청부터 첫 방문까지 단계마다 안내해 드립니다." more={["#/guide", "이용 안내 자세히"]} />
        <ol className="nc-steps">{STEPS.map((s, i) => <li key={s.title}><b>{String(i + 1).padStart(2, "0")}</b><h3>{s.title}</h3><p>{s.text}</p></li>)}</ol>
      </div>
    </section>

    <section className="nc-sec tint">
      <div className="nc-wrap nc-area">
        <div>
          <SecHead kicker="Service Area" title="방문 지역" lead="아래 지역은 정기 방문이 가능합니다. 그 외 지역도 상담해 주시면 가능 여부를 안내해 드립니다." />
          <ul className="nc-chips">{AREAS.map(a => <li key={a}>{a}</li>)}</ul>
        </div>
        <AreaMap />
      </div>
    </section>

    {posts.length > 0 && <section className="nc-sec">
      <div className="nc-wrap">
        <SecHead kicker="Health Notes" title="건강 블로그" lead="방문 현장에서 보호자분들이 자주 묻는 내용을 간호사가 정리합니다." more={["#/blog", "글 전체 보기"]} />
        <PostCards posts={posts} images={images} />
      </div>
    </section>}

    <CtaBand call={call} />
  </>;
}

/* ---------- 센터 소개 ---------- */
function About() {
  return <>
    <PageHead kicker="About" title="센터 소개" lead={CENTER.slogan} />
    <section className="nc-sec">
      <div className="nc-wrap nc-greet">
        <figure><Art k="team" label="센터 간호팀" /></figure>
        <div>
          <h2>센터장 인사말</h2>
          {ABOUT.greeting.map((p, i) => <p key={i}>{p}</p>)}
          <p className="nc-sign">{ABOUT.director}</p>
        </div>
      </div>
    </section>
    <section className="nc-sec tint">
      <div className="nc-wrap">
        <SecHead kicker="Our Promise" title="늘곁의 세 가지 약속" />
        <ol className="nc-promises">{ABOUT.promises.map((p, i) => <li key={p.title}><b>{i + 1}</b><h3>{p.title}</h3><p>{p.text}</p></li>)}</ol>
      </div>
    </section>
    <section className="nc-sec">
      <div className="nc-wrap">
        <SecHead kicker="Nursing Team" title="간호팀" lead="모든 방문은 임상 경력을 갖춘 간호사가 직접 합니다." />
        <ul className="nc-team">{ABOUT.team.map((t, i) => <li key={i}><span className="nc-avatar" aria-hidden="true" /><strong>{t.role}</strong><span>{t.career}</span></li>)}</ul>
      </div>
    </section>
    <section className="nc-sec tint">
      <div className="nc-wrap nc-area">
        <div>
          <SecHead kicker="Location" title="찾아오시는 길" />
          <dl className="nc-dl"><dt>주소</dt><dd>{CENTER.address}</dd><dt>전화</dt><dd>{CENTER.phone}</dd><dt>운영</dt><dd>{CENTER.hours}</dd></dl>
        </div>
        <div className="nc-map-slot">지도 영역<small>실제 사이트에서는 네이버·카카오 지도를 연결합니다.</small></div>
      </div>
    </section>
  </>;
}

/* ---------- 서비스 ---------- */
function Services() {
  return <>
    <PageHead kicker="Home Nursing" title="방문간호 서비스" lead="필요한 간호는 주치의의 방문간호지시서와 첫 방문 평가를 바탕으로 정합니다." />
    <section className="nc-sec">
      <div className="nc-wrap">
        <ul className="nc-svc-list">{SERVICES.map(s => <li key={s.id}>
          <Art k={s.art} />
          <div>
            <h2>{s.title}</h2><p>{s.summary}</p>
            <ul className="nc-check">{s.points.map(p => <li key={p}>{p}</li>)}</ul>
            <a className="nc-more" href={`#/services/${s.id}`}>자세히 보기</a>
          </div>
        </li>)}</ul>
      </div>
    </section>
    <CtaBand />
  </>;
}
function ServiceDetail({ id }: { id: string }) {
  const s = SERVICES.find(x => x.id === id);
  if (!s) return <NotFound />;
  return <>
    <PageHead kicker="Home Nursing" title={s.title} lead={s.summary} back={["#/services", "서비스 목록"]} />
    <section className="nc-sec">
      <div className="nc-wrap nc-detail">
        <Art k={s.art} label={s.title} />
        <div>
          <h2>이렇게 도와드립니다</h2>
          <ul className="nc-check">{s.points.map(p => <li key={p}>{p}</li>)}</ul>
          <h2>이런 분께 필요합니다</h2>
          <ul className="nc-check soft">{s.forWho.map(p => <li key={p}>{p}</li>)}</ul>
          <p className="nc-note">구체적인 간호 내용은 방문간호지시서와 첫 방문 평가에 따라 달라집니다.</p>
        </div>
      </div>
    </section>
    <section className="nc-sec tint">
      <div className="nc-wrap">
        <SecHead title="다른 서비스" />
        <ul className="nc-mini">{SERVICES.filter(x => x.id !== id).map(x => <li key={x.id}><a href={`#/services/${x.id}`}>{x.title}</a></li>)}</ul>
      </div>
    </section>
    <CtaBand />
  </>;
}

/* ---------- 이용 안내 ---------- */
function Guide() {
  return <>
    <PageHead kicker="Guide" title="이용 안내" lead="방문간호는 노인장기요양보험의 재가급여로, 장기요양 등급과 방문간호지시서가 있으면 이용할 수 있습니다." />
    <section className="nc-sec">
      <div className="nc-wrap">
        <SecHead title="신청 절차" />
        <ol className="nc-steps">{STEPS.map((s, i) => <li key={s.title}><b>{String(i + 1).padStart(2, "0")}</b><h3>{s.title}</h3><p>{s.text}</p></li>)}</ol>
      </div>
    </section>
    <section className="nc-sec tint">
      <div className="nc-wrap nc-guide-grid">
        <div>
          <SecHead title="준비 서류" />
          <ul className="nc-docs">{DOCUMENTS.map(d => <li key={d.title}><strong>{d.title}</strong><span>{d.text}</span></li>)}</ul>
        </div>
        <div>
          <SecHead title="비용 안내" />
          <table className="nc-table">
            <thead><tr><th>구분</th><th>본인부담</th></tr></thead>
            <tbody>
              <tr><td>일반</td><td>15%</td></tr><tr><td>감경 대상자</td><td>9% · 6%</td></tr><tr><td>기초생활수급자</td><td>없음</td></tr>
            </tbody>
          </table>
          <p className="nc-note">방문 시간과 횟수에 따라 금액이 달라집니다. 상담 때 예상 금액을 안내해 드립니다.</p>
        </div>
      </div>
    </section>
    <section className="nc-sec">
      <div className="nc-wrap nc-narrow">
        <SecHead kicker="FAQ" title="자주 묻는 질문" />
        <div className="nc-faq">{FAQ.map(f => <details key={f.q}><summary>{f.q}</summary><p>{f.a}</p></details>)}</div>
      </div>
    </section>
    <CtaBand />
  </>;
}

/* ---------- 블로그 ---------- */
function PostCards({ posts, images }: { posts: Post[]; images: ImageItem[] }) {
  return <ul className="nc-posts">{posts.map(p => <li key={p.id}>
    <a className="nc-post-card" href={`#/blog/${encodeURIComponent(p.slug)}`}>
      <Pic img={images.find(i => i.id === p.cover)} />
      <div><time>{fmtDate(p.publishedAt)}</time><h3>{p.title}</h3><p>{p.seoDesc || excerpt(p.body)}</p></div>
    </a>
  </li>)}</ul>;
}
function BlogList({ posts, images }: { posts: Post[]; images: ImageItem[] }) {
  return <>
    <PageHead kicker="Health Notes" title="건강 블로그" lead="방문 현장에서 보호자분들이 자주 묻는 내용을 간호사가 정리합니다." />
    <section className="nc-sec">
      <div className="nc-wrap">{posts.length ? <PostCards posts={posts} images={images} /> : <p className="nc-empty">아직 발행된 글이 없습니다.</p>}</div>
    </section>
  </>;
}
function BlogPost({ post, images, others }: { post: Post | undefined; images: ImageItem[]; others: Post[] }) {
  useEffect(() => {
    if (!post) return;
    const prev = document.title;
    document.title = post.seoTitle || `${post.title} | ${CENTER.name}`;
    return () => { document.title = prev; };
  }, [post]);
  if (!post) return <NotFound text="글을 찾을 수 없습니다. 발행이 취소되었거나 주소가 바뀌었을 수 있어요." />;
  const cover = images.find(i => i.id === post.cover);
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(postJsonLd(post, images)).replace(/</g, "\\u003c") }} />
    <article className="nc-article">
      <div className="nc-wrap nc-narrow">
        <a className="nc-back" href="#/blog">건강 블로그</a>
        <h1>{post.title}</h1>
        <p className="nc-meta">{fmtDate(post.publishedAt)} · {CENTER.name} 간호팀</p>
        {cover && <Pic img={cover} className="nc-cover" />}
        <Body text={post.body} images={images} />
        {post.faq.length > 0 && <section className="nc-article-faq">
          <h2>자주 묻는 질문</h2>
          <div className="nc-faq">{post.faq.map(f => <details key={f.q} open><summary>{f.q}</summary><p>{f.a}</p></details>)}</div>
        </section>}
        <div className="nc-article-cta"><p>어르신 상황에 맞는 간호가 궁금하시면 편하게 문의해 주세요.</p><a className="nc-btn" href="#/consult">상담 신청하기</a></div>
        {others.length > 0 && <><h2 className="nc-others-h">다른 글</h2><PostCards posts={others} images={images} /></>}
      </div>
    </article>
  </>;
}
/** 본문 형식: "## 소제목", "- 목록", "[이미지:id]", 나머지는 문단. */
export function Body({ text, images }: { text: string; images: ImageItem[] }) {
  const out: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => { if (list.length) { out.push(<ul key={"ul" + out.length}>{list.map((l, i) => <li key={i}>{l}</li>)}</ul>); list = []; } };
  text.split("\n").forEach(raw => {
    const line = raw.trim();
    if (line.startsWith("- ")) { list.push(line.slice(2)); return; }
    flush();
    if (!line) return;
    const img = line.match(/^\[이미지:([\w-]+)\]$/);
    if (img) { const it = images.find(i => i.id === img[1]); if (it) out.push(<figure key={"f" + out.length}><Pic img={it} />{it.alt && <figcaption>{it.alt}</figcaption>}</figure>); return; }
    if (line.startsWith("## ")) out.push(<h2 key={"h" + out.length}>{line.slice(3)}</h2>);
    else out.push(<p key={"p" + out.length}>{line}</p>);
  });
  flush();
  return <div className="nc-body">{out.map((n, i) => <Fragment key={i}>{n}</Fragment>)}</div>;
}

/* ---------- 상담 신청 ---------- */
const RELATIONS = ["본인", "자녀", "배우자", "기타"];
const GRADES = ["있음", "없음", "모름"];
const TIMES = ["언제든", "평일 오전", "평일 오후", "토요일 오전"];
function Consult({ call, kakao }: { call: () => void; kakao: () => void }) {
  const { actions } = useNurse();
  const empty = { name: "", phone: "", relation: "자녀", area: "", grade: "모름", time: "언제든", message: "" };
  const [f, setF] = useState(empty);
  const [agree, setAgree] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState<Inquiry | null>(null);
  const set = (k: keyof typeof empty) => (e: { target: { value: string } }) => setF(v => ({ ...v, [k]: e.target.value }));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!f.name.trim()) return setErr("성함을 입력해 주세요.");
    if (!/^0\d{1,2}-?\d{3,4}-?\d{4}$/.test(f.phone.trim())) return setErr("연락처를 확인해 주세요. (예: 010-1234-5678)");
    if (!agree) return setErr("개인정보 수집·이용에 동의해 주세요.");
    setErr("");
    setDone(actions.submitInquiry({ ...f, name: f.name.trim(), phone: f.phone.trim() }));
  }

  if (done) return <>
    <PageHead kicker="Consultation" title="상담 신청" />
    <section className="nc-sec"><div className="nc-wrap nc-narrow">
      <div className="nc-done" role="status">
        <span className="nc-done-mark" aria-hidden="true" />
        <h2>상담 신청이 접수되었습니다</h2>
        {done.mail === "sent"
          ? <p>담당 간호사가 내용을 확인한 뒤 <b>{done.time}</b>에 {done.phone}로 연락드리겠습니다.</p>
          : <p>접수는 정상적으로 저장되었습니다. 다만 담당자 알림이 늦어질 수 있어, 급하신 경우 전화나 카카오톡으로 연락해 주세요.</p>}
        <dl className="nc-dl"><dt>성함</dt><dd>{done.name}</dd><dt>연락처</dt><dd>{done.phone}</dd><dt>지역</dt><dd>{done.area || "-"}</dd><dt>문의</dt><dd>{done.message || "-"}</dd></dl>
        <div className="nc-hero-cta"><a className="nc-btn ghost" href="#/">처음으로</a><button className="nc-btn ghost" onClick={() => { setDone(null); setF(empty); setAgree(false); }}>다른 문의 남기기</button></div>
      </div>
    </div></section>
  </>;

  return <>
    <PageHead kicker="Consultation" title="상담 신청" lead="어르신 상황을 알려 주시면 담당 간호사가 연락드립니다. 상담은 무료입니다." />
    <section className="nc-sec"><div className="nc-wrap nc-consult">
      <form className="nc-form" onSubmit={submit} noValidate>
        <div className="nc-row2">
          <label>성함 <em>필수</em><input value={f.name} onChange={set("name")} autoComplete="name" placeholder="홍길동" /></label>
          <label>연락처 <em>필수</em><input value={f.phone} onChange={set("phone")} inputMode="tel" autoComplete="tel" placeholder="010-1234-5678" /></label>
        </div>
        <fieldset><legend>어르신과의 관계</legend><div className="nc-seg">{RELATIONS.map(r => <label key={r} className={f.relation === r ? "on" : ""}><input type="radio" name="relation" value={r} checked={f.relation === r} onChange={set("relation")} />{r}</label>)}</div></fieldset>
        <div className="nc-row2">
          <label>사시는 지역<input value={f.area} onChange={set("area")} placeholder="예: 양천구 목동" /></label>
          <label>희망 연락 시간<select value={f.time} onChange={set("time")}>{TIMES.map(t => <option key={t}>{t}</option>)}</select></label>
        </div>
        <fieldset><legend>장기요양 등급</legend><div className="nc-seg">{GRADES.map(g => <label key={g} className={f.grade === g ? "on" : ""}><input type="radio" name="grade" value={g} checked={f.grade === g} onChange={set("grade")} />{g}</label>)}</div></fieldset>
        <label>문의 내용<textarea rows={5} value={f.message} onChange={set("message")} placeholder="어르신 상태, 필요한 간호, 궁금한 점을 편하게 적어 주세요." /></label>
        <div className="nc-agree">
          <label><input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} /> 개인정보 수집·이용에 동의합니다 <em>필수</em></label>
          <p>수집 항목: 성함, 연락처, 지역, 문의 내용 · 이용 목적: 상담 회신 · 보관 기간: 상담 종료 후 1년 (샘플 문구, 센터와 협의해 확정)</p>
        </div>
        {err && <p className="nc-err" role="alert">{err}</p>}
        <button className="nc-btn block" type="submit">상담 신청하기</button>
      </form>
      <aside className="nc-consult-side">
        <h2>바로 상담이 필요하시면</h2>
        <button className="nc-side-row" onClick={call}><PhoneIcon /><span><b>{CENTER.phone}</b><small>{CENTER.hours}</small></span></button>
        <button className="nc-side-row" onClick={kakao}><KakaoIcon /><span><b>카카오톡 오픈채팅</b><small>사진과 함께 편하게 문의하세요</small></span></button>
      </aside>
    </div></section>
  </>;
}

/* ---------- 공통 ---------- */
function SecHead({ kicker, title, lead, more }: { kicker?: string; title: string; lead?: string; more?: [string, string] }) {
  return <div className="nc-sec-head">
    <div>{kicker && <p className="nc-kicker">{kicker}</p>}<h2>{title}</h2>{lead && <p>{lead}</p>}</div>
    {more && <a className="nc-more" href={more[0]}>{more[1]}</a>}
  </div>;
}
function PageHead({ kicker, title, lead, back }: { kicker: string; title: string; lead?: string; back?: [string, string] }) {
  return <section className="nc-page-head"><div className="nc-wrap">
    {back && <a className="nc-back" href={back[0]}>{back[1]}</a>}
    <p className="nc-kicker">{kicker}</p><h1>{title}</h1>{lead && <p>{lead}</p>}
  </div></section>;
}
function CtaBand({ call }: { call?: () => void }) {
  return <section className="nc-cta-band"><div className="nc-wrap">
    <div><h2>어떤 간호가 필요한지 모르셔도 괜찮습니다.</h2><p>상황을 들려주시면 필요한 절차부터 차근차근 안내해 드립니다.</p></div>
    <div className="nc-hero-cta"><a className="nc-btn light" href="#/consult">상담 신청하기</a>{call && <button className="nc-btn outline-light" onClick={call}>{CENTER.phone}</button>}</div>
  </div></section>;
}
function NotFound({ text = "페이지를 찾을 수 없습니다." }: { text?: string }) {
  return <section className="nc-sec"><div className="nc-wrap nc-narrow nc-empty"><p>{text}</p><a className="nc-btn ghost" href="#/">처음으로</a></div></section>;
}
function AreaMap() {
  return <svg className="nc-area-map" viewBox="0 0 300 200" role="img" aria-label="방문 지역 약도 (샘플)">
    <path d="M20 120c40-30 80-10 120-40s90-20 140-50" className="river" />
    {[[60, 60, "강서"], [120, 110, "양천"], [100, 160, "구로"], [170, 120, "영등포"], [150, 175, "금천"], [215, 160, "관악"]].map(([x, y, t]) =>
      <g key={t as string}><circle cx={x as number} cy={y as number} r="22" /><text x={x as number} y={(y as number) + 4}>{t}</text></g>)}
  </svg>;
}
function Mark() { return <span className="nc-mark" aria-hidden="true" />; }
function PhoneIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" /></svg>; }
function KakaoIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 4C6.9 4 3 7.2 3 11.1c0 2.5 1.6 4.7 4.1 6l-1 3.6c-.1.3.3.6.6.4l4.2-2.8h1.1c5.1 0 9-3.2 9-7.2S17.1 4 12 4Z" /></svg>; }
