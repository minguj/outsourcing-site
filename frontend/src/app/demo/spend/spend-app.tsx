"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, client, createSandbox, won, type Analysis, type Client, type Sandbox } from "./_spend/api";
import { MerchantsTab, SavingsPanel, SeriesList, SignalsPanel, TransactionsTable, UpcomingList } from "./_spend/sections";

type Tab = "series" | "upcoming" | "transactions" | "merchants";
const TABS: { key: Tab; label: string }[] = [
  { key: "series", label: "구독·고정지출" },
  { key: "upcoming", label: "결제 예정 30일" },
  { key: "transactions", label: "원본 거래내역" },
  { key: "merchants", label: "가맹점 사전" },
];

const ENRICH_TEXT: Record<NonNullable<Analysis["enrich"]>["status"], (a: number, s: number) => string> = {
  done: (a, s) => (a ? `AI가 가맹점 ${s}곳을 정리했어요. 정리 결과는 저장돼 다음부터는 다시 묻지 않아요.` : "정리할 가맹점이 없어요."),
  partial: (a, s) => `가맹점 ${a}곳 중 ${s}곳을 정리했어요. 나머지는 형식이 맞지 않아 받지 않았어요.`,
  no_ai: () => "지금은 AI를 쓸 수 없어 가맹점명을 그대로 두었어요. 감지·합계는 규칙으로 계산돼요.",
  limit: () => "이번 체험에서 쓸 수 있는 AI 정리 횟수를 다 썼어요. 감지·합계는 규칙으로 계산돼요.",
  failed: () => "AI 응답을 받지 못해 가맹점명을 그대로 두었어요. 감지·합계는 규칙으로 계산돼요.",
};

export default function SpendApp() {
  const [box, setBox] = useState<Sandbox | null>(null);
  const [api, setApi] = useState<Client | null>(null);
  const [persona, setPersona] = useState<string>("jisoo");
  const [view, setView] = useState<Analysis | null>(null);
  const [tab, setTab] = useState<Tab>("series");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<string | null>(null);

  const start = useCallback(() => {
    setError(null);
    createSandbox()
      .then((b) => {
        setBox(b);
        setApi(client(b.token));
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "체험 데이터를 준비하지 못했습니다."));
  }, []);

  useEffect(() => {
    start();
  }, [start]);

  const handle = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 404) {
        setError("체험 시간이 지나 새로 시작합니다.");
        start();
        return;
      }
      setError(e instanceof ApiError ? e.message : "요청을 처리하지 못했습니다.");
    },
    [start],
  );

  useEffect(() => {
    if (!api) return;
    setView(null);
    setNotice(null);
    setFocus(null);
    api.analysis(persona).then(setView).catch(handle);
  }, [api, persona, handle]);

  const enrich = () => {
    if (!api) return;
    setBusy(true);
    api
      .enrich(persona)
      .then((v) => {
        setView(v);
        if (v.enrich) setNotice(ENRICH_TEXT[v.enrich.status](v.enrich.asked, v.enrich.saved));
      })
      .catch(handle)
      .finally(() => setBusy(false));
  };

  const review = (seriesId: string, decision: "confirm" | "reject" | "reset") => {
    if (!api) return;
    api.review(persona, seriesId, decision).then(setView).catch(handle);
  };

  const cancelAction = (seriesId: string, action: "request" | "confirm" | "undo") => {
    if (!api) return;
    setError(null);
    api.cancel(persona, seriesId, action).then(setView).catch(handle);
  };

  // 간편해지(가상 처리)는 몇 초 뒤 완료된다. 처리 중인 해지가 있으면 잠시 뒤 다시 불러온다.
  const processing = view?.series.some((s) => s.cancel?.status === "processing") ?? false;
  useEffect(() => {
    if (!api || !processing) return;
    const timer = setTimeout(() => api.analysis(persona).then(setView).catch(handle), 4500);
    return () => clearTimeout(timer);
  }, [api, persona, processing, view, handle]);

  const showTransactions = (seriesId: string) => {
    setFocus(seriesId);
    setTab("transactions");
  };

  if (!box || !api) {
    return (
      <div className="sp-card sp-center">
        {error ? (
          <>
            <p>{error}</p>
            <button className="sp-btn" onClick={start}>
              다시 시도
            </button>
          </>
        ) : (
          <p className="sp-muted">가상 거래내역을 준비하고 있어요…</p>
        )}
      </div>
    );
  }

  return (
    <>
      <section className="sp-hero">
        <h1>거래내역에서 구독·고정지출 찾기</h1>
        <p>
          카드·계좌 거래내역에서 반복 결제를 찾아 묶고, 가격 인상·무료체험 전환·중복 구독 같은 신호와 줄일 수 있는 금액을 보여 줍니다. 사전에 없는 가맹점은 AI가
          서비스명과 분류를 정리합니다.
        </p>
        <p className="sp-small sp-muted">
          가상 사용자 3명의 거래내역({box.period.from} ~ {box.period.to}) · 기준일 {box.as_of} · 입력한 정보는 받지 않으며 체험 데이터는 2시간 뒤 지워집니다.
        </p>
      </section>

      <div className="sp-personas" role="tablist" aria-label="가상 사용자">
        {box.personas.map((p) => (
          <button key={p.id} role="tab" aria-selected={persona === p.id} className={`sp-persona ${persona === p.id ? "is-on" : ""}`} onClick={() => setPersona(p.id)}>
            <strong>{p.name}</strong>
            <span>{p.summary}</span>
            <span className="sp-small sp-muted">{p.accounts.map((a) => a.label).join(" · ")}</span>
          </button>
        ))}
      </div>

      {error && <p className="sp-msg sp-msg-bad">{error}</p>}

      {!view ? (
        <div className="sp-card sp-center sp-muted">거래내역을 분석하고 있어요…</div>
      ) : (
        <>
          <section className="sp-summary">
            <div className="sp-stat sp-stat-main">
              <span>매달 나가는 돈 (월 환산)</span>
              <strong>{won(view.summary.monthly_total)}</strong>
              <em>1년이면 {won(view.summary.yearly_total)}</em>
            </div>
            <div className="sp-stat">
              <span>구독 {view.summary.subscription_count}개</span>
              <strong>{won(view.summary.subscription_monthly)}</strong>
              <em>해지·변경할 수 있는 결제</em>
            </div>
            <div className="sp-stat">
              <span>고정지출 {view.summary.fixed_count}개</span>
              <strong>{won(view.summary.fixed_monthly)}</strong>
              <em>통신·보험·관리비·공과금</em>
            </div>
          </section>
          {view.summary.saved_monthly > 0 && (
            <p className="sp-msg sp-msg-ok">
              해지한 구독 덕분에 매달 <b>{won(view.summary.saved_monthly)}</b>, 1년이면 {won(view.summary.saved_monthly * 12)}을 아껴요. (가상 처리)
            </p>
          )}

          <div className="sp-ai-bar">
            <div>
              <b>AI 가맹점 정리</b>{" "}
              {view.ai_pending > 0 ? (
                <span>사전에 없는 반복 결제 가맹점 {view.ai_pending}곳이 아직 가맹점명 그대로예요.</span>
              ) : (
                <span className="sp-muted">모든 반복 결제에 서비스 정보가 붙어 있어요.</span>
              )}
              <div className="sp-small sp-muted">AI에는 가상 가맹점명·금액·주기만 보내고, 정해진 분류값인지 확인한 뒤 반영합니다.</div>
            </div>
            <button className="sp-btn" onClick={enrich} disabled={busy || view.ai_pending === 0}>
              {busy ? "AI가 정리하는 중…" : "AI로 정리하기"}
            </button>
          </div>
          {notice && <p className="sp-msg">{notice}</p>}

          <div className="sp-layout">
            <div className="sp-col-main">
              <div className="sp-tabs" role="tablist">
                {TABS.map((t) => (
                  <button key={t.key} role="tab" aria-selected={tab === t.key} className={`sp-tab ${tab === t.key ? "is-on" : ""}`} onClick={() => setTab(t.key)}>
                    {t.label}
                  </button>
                ))}
              </div>
              <div className="sp-card">
                {tab === "series" && <SeriesList view={view} onReview={review} onCancel={cancelAction} onShowTransactions={showTransactions} />}
                {tab === "upcoming" && <UpcomingList view={view} />}
                {tab === "transactions" && <TransactionsTable view={view} focus={focus} onFocus={setFocus} />}
                {tab === "merchants" && <MerchantsTab api={api} version={view} />}
              </div>
            </div>
            <aside className="sp-col-side">
              <SavingsPanel view={view} />
              <SignalsPanel view={view} />
            </aside>
          </div>
        </>
      )}
      <p className="sp-footnote">
        공개된 채용 공고의 업무 범위를 바탕으로 만든 개인 샘플입니다. 사람·거래내역·일부 가맹점(학원·보험사·아파트)은 가상이며, 실제 금융 데이터나 마이데이터와 연결되어
        있지 않습니다.
      </p>
    </>
  );
}
