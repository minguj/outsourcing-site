"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { client, createSandbox, PERMISSION_LABELS, todayKst, type Client, type DemoUser, type Sandbox, type Site } from "./_pms/api";
import { AuditTab, BillingTab, ContractsTab, OverviewTab, ResidentsTab, UnitsTab } from "./_pms/tabs";

type Tab = "overview" | "units" | "residents" | "contracts" | "billing" | "audit";

const TABS: { key: Tab; label: string; perm: string }[] = [
  { key: "overview", label: "운영 현황", perm: "site.read" },
  { key: "units", label: "호실 현황판", perm: "unit.read" },
  { key: "residents", label: "입주자", perm: "resident.read" },
  { key: "contracts", label: "계약", perm: "contract.read" },
  { key: "billing", label: "청구·수납", perm: "billing.read" },
  { key: "audit", label: "감사 기록", perm: "audit.read" },
];

const DEFAULT_USER = "u-mgr-garam";

export default function PmsApp() {
  const [box, setBox] = useState<Sandbox | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [userId, setUserId] = useState(DEFAULT_USER);
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState<string>("");
  const [tab, setTab] = useState<Tab>("overview");
  const [month, setMonth] = useState(""); // 현재 날짜는 화면이 뜬 뒤에 읽는다 (Cache Components 사전 렌더 규칙)
  const [version, setVersion] = useState(0); // 데이터가 바뀌면 탭을 다시 불러온다

  const start = useCallback(() => {
    setFailed(null);
    createSandbox()
      .then((b) => {
        setBox(b);
        setUserId(DEFAULT_USER);
        setVersion((v) => v + 1);
      })
      .catch((e: Error) => setFailed(e.message));
  }, []);

  useEffect(() => {
    setMonth(todayKst().slice(0, 7));
    start();
  }, [start]);

  const api: Client | null = useMemo(() => (box ? client(box.token, userId) : null), [box, userId]);
  const user: DemoUser | undefined = box?.users.find((u) => u.id === userId);
  const can = useCallback((perm: string) => !!user?.permissions.includes(perm), [user]);

  useEffect(() => {
    if (!api) return;
    let alive = true;
    api
      .sites()
      .then((list) => {
        if (!alive) return;
        setSites(list);
        setSiteId((current) => (list.some((s) => s.id === current) ? current : list[0]?.id ?? ""));
      })
      .catch(() => alive && setSites([]));
    return () => {
      alive = false;
    };
  }, [api]);

  const changed = useCallback(() => setVersion((v) => v + 1), []);
  const site = sites.find((s) => s.id === siteId);

  if (failed) {
    return (
      <div className="pm-card pm-center">
        <p>체험 데이터를 준비하지 못했습니다. ({failed})</p>
        <button className="pm-btn" onClick={start}>다시 시도</button>
      </div>
    );
  }
  if (!box || !api || !user || !month) {
    return <div className="pm-card pm-center pm-muted">가상 운영사 데이터를 준비하는 중…</div>;
  }

  const current = TABS.find((t) => t.key === tab)!;

  return (
    <>
      <section className="pm-hero">
        <h1>여러 사업장을 하나의 운영 플랫폼으로</h1>
        <p>
          소유주가 다른 시니어하우징·임대주택 두 곳을 위탁 운영하는 가상 운영사 <b>{box.operator.name}</b>입니다. 위에서 역할을
          바꾸면 볼 수 있는 사업장, 메뉴, 개인정보가 달라집니다. 데이터는 이 체험에만 쓰이는 가상 데이터이며 2시간 뒤 사라집니다.
        </p>
      </section>

      <section className="pm-card" aria-label="체험할 역할">
        <div className="pm-card-head">
          <h2>체험할 역할</h2>
          <button className="pm-btn pm-btn-ghost" onClick={start}>데이터 처음으로</button>
        </div>
        <div className="pm-roles">
          {box.users.map((u) => (
            <button
              key={u.id}
              className={`pm-role ${u.id === userId ? "on" : ""}`}
              onClick={() => {
                setUserId(u.id);
                setTab("overview");
                changed();
              }}
              aria-pressed={u.id === userId}
            >
              <span className="pm-role-label">{u.role_label}</span>
              <span className="pm-role-name">{u.name}</span>
              <span className="pm-role-sites">{u.sites.join(" · ")}</span>
            </button>
          ))}
        </div>
        <div className="pm-perms">
          {Object.entries(PERMISSION_LABELS).map(([perm, label]) => (
            <span key={perm} className={`pm-chip ${can(perm) ? "yes" : "no"}`} title={perm}>
              {can(perm) ? "✓" : "✕"} {label}
            </span>
          ))}
        </div>
      </section>

      <div className="pm-toolbar">
        <label className="pm-field">
          사업장
          <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.asset_label})
              </option>
            ))}
          </select>
        </label>
        {site && (
          <span className="pm-muted pm-small">
            소유주 {site.owner} · {site.city} · 납부일 매월 {site.billing.due_day}일 · 연체 이율 연 {site.billing.late_rate_pct}%
          </span>
        )}
      </div>

      <nav className="pm-tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={`pm-tab ${tab === t.key ? "on" : ""} ${can(t.perm) ? "" : "locked"}`} onClick={() => setTab(t.key)}>
            {t.label}
            {!can(t.perm) && <span aria-label="권한 없음"> 🔒</span>}
          </button>
        ))}
      </nav>

      <section className="pm-card">
        {!can(current.perm) ? (
          <Locked perm={current.perm} role={user.role_label} />
        ) : !site ? (
          <p className="pm-muted">볼 수 있는 사업장이 없습니다.</p>
        ) : (
          <TabBody tab={tab} api={api} site={site} sites={sites} can={can} month={month} setMonth={setMonth} version={version} changed={changed} />
        )}
      </section>

      <p className="pm-foot pm-small pm-muted">
        공개된 채용 공고의 업무 범위를 바탕으로 첫 버전을 어떻게 설계할지 보여 주는 개인 샘플입니다. 운영사·소유주·사업장·사람은 모두 가상입니다.
        권한 검사는 화면이 아니라 서버에서 합니다. 화면의 🔒 표시는 안내용입니다.
      </p>
    </>
  );
}

function Locked({ perm, role }: { perm: string; role: string }) {
  return (
    <div className="pm-locked">
      <b>{role}</b> 역할에는 <b>{PERMISSION_LABELS[perm] ?? perm}</b> 권한이 없습니다.
      <span className="pm-muted pm-small"> 서버도 같은 기준으로 요청을 거절합니다(403).</span>
    </div>
  );
}

type BodyProps = {
  tab: Tab;
  api: Client;
  site: Site;
  sites: Site[];
  can: (perm: string) => boolean;
  month: string;
  setMonth: (m: string) => void;
  version: number;
  changed: () => void;
};

function TabBody({ tab, ...p }: BodyProps) {
  const key = `${p.site.id}-${p.version}`;
  switch (tab) {
    case "overview":
      return <OverviewTab key={key} {...p} />;
    case "units":
      return <UnitsTab key={key} {...p} />;
    case "residents":
      return <ResidentsTab key={key} {...p} />;
    case "contracts":
      return <ContractsTab key={key} {...p} />;
    case "billing":
      return <BillingTab key={key} {...p} />;
    case "audit":
      return <AuditTab key={p.version} {...p} />;
  }
}
