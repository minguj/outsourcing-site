"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Meta, ParcelSummary, Redevelopment, vworldConf } from "./_zeb/api";
import { searchParcels as vworldSearch, type VWorldConf } from "./_zeb/vworld";
import { area } from "./_zeb/format";
import { Spinner, useNavPending } from "./_zeb/loading";

type Tab = "parcel" | "redev" | "manual";

export default function ZebHome() {
  const [tab, setTab] = useState<Tab>("parcel");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [source, setSource] = useState<"auto" | "sample">("auto");

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  return (
    <>
      <section className="zb-hero">
        <h1>이 땅에 얼마나 짓고, ZEB는 몇 등급까지 가능할까?</h1>
        <p>
          대상지를 고르면 용도지역·건폐율·용적률·높이 제한으로 건축 규모를 산정하고, ZEB 등급별로 필요한 신재생
          설비 조합과 도입비용을 계산합니다. 모든 숫자에는 근거 조항과 가정값이 함께 기록됩니다.
        </p>
      </section>

      <div className="zb-card" style={{ marginTop: 16 }}>
        <div className="zb-tabs" role="tablist">
          {(
            [
              ["parcel", "지번 검색"],
              ["redev", "정비사업 검색"],
              ["manual", "직접 입력"],
            ] as const
          ).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={`zb-tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>
              {label}
            </button>
          ))}
          <span style={{ marginLeft: "auto", alignSelf: "center" }} className="zb-small zb-muted">
            데이터:{" "}
            {meta?.parcel_source === "vworld" ? (
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as "auto" | "sample")}
                style={{ width: "auto", padding: "2px 6px", fontSize: 13 }}
              >
                <option value="auto">브이월드 실데이터</option>
                <option value="sample">데모 샘플 필지</option>
              </select>
            ) : (
              <span className="zb-pill warn">데모 샘플 필지 (브이월드 키 미설정)</span>
            )}
          </span>
        </div>
        {tab === "parcel" && (
          <ParcelSearch key={searchSource(meta, source)} source={searchSource(meta, source)} conf={vworldConf(meta)} />
        )}
        {tab === "redev" && <RedevSearch />}
        {tab === "manual" && <ManualForm meta={meta} />}
      </div>

      <div className="zb-grid zb-grid-3" style={{ marginTop: 16 }}>
        <Explainer n="1" title="규모 산정" body="조례와 법정 상한 중 작은 값을 적용하고, 높이·층수 제한 중 어떤 조건이 규모를 결정하는지 보여줍니다." />
        <Explainer n="2" title="ZEB 시나리오" body="단위 생산량당 비용이 낮은 설비부터 옥상·입면·공지·열수요 한계까지 채워 등급별 최소비용 조합을 찾습니다." />
        <Explainer n="3" title="근거와 재현성" body="결과마다 계산 ID와 규칙 버전이 찍힙니다. 검증 안 된 규칙을 쓰면 '검토 필요'로 표시됩니다." />
      </div>
    </>
  );
}

function Explainer({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="zb-stat">
      <div className="zb-stat-label">STEP {n}</div>
      <h3 style={{ margin: "2px 0 4px" }}>{title}</h3>
      <div className="zb-small zb-muted">{body}</div>
    </div>
  );
}

/** sample: 데모 필지 / browser: 브라우저가 브이월드 조회 / auto: 서버가 브이월드 조회 */
function searchSource(meta: Meta | null, choice: "auto" | "sample") {
  if (meta?.parcel_source !== "vworld" || choice === "sample") return "sample";
  return meta.vworld_mode === "browser" ? "browser" : "auto";
}

function ParcelSearch({ source, conf }: { source: string; conf: VWorldConf | null }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ParcelSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // 결과를 누른 뒤 계산 화면이 뜰 때까지 표시 (여러 번 누르는 것 방지)
  const [opening, setOpening] = useNavPending<string>();

  const run = async (query: string) => {
    setLoading(true);
    setErr(null);
    try {
      setItems(
        source === "browser" && conf ? await vworldSearch(conf, query) : (await api.searchParcels(query, source)).items,
      );
    } catch (e) {
      setErr((e as Error).message);
      setItems(null);
    } finally {
      setLoading(false);
    }
  };

  // 샘플 모드는 목록 전체를 먼저 보여 준다. (source 가 바뀌면 부모가 key 로 이 컴포넌트를 새로 만든다)
  useEffect(() => {
    if (source !== "sample") return;
    let alive = true;
    api
      .searchParcels("", source)
      .then((r) => alive && setItems(r.items))
      .catch((e) => alive && setErr((e as Error).message));
    return () => {
      alive = false;
    };
  }, [source]);

  return (
    <>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(q);
        }}
        style={{ display: "flex", gap: 8 }}
      >
        <input placeholder="예: 서울특별시 마포구 아현동 123-4" value={q} onChange={(e) => setQ(e.target.value)} />
        <button disabled={loading}>{loading ? <Spinner label="검색 중" /> : "검색"}</button>
      </form>
      {err && <div className="zb-alert critical" style={{ marginTop: 12 }}>{err}</div>}
      <div style={{ marginTop: 14 }}>
        {items?.length === 0 && <div className="zb-empty">검색 결과가 없습니다</div>}
        <div className={opening ? "zb-opening" : undefined}>
          {items?.map((p) => (
            <Link
              key={p.pnu}
              className={`zb-result-row${opening === p.pnu ? " is-opening" : ""}`}
              href={`/demo/zeb/plan?pnu=${p.pnu}&source=${source}`}
              onClick={() => setOpening(p.pnu)}
            >
              <span>{p.address}</span>
              {opening === p.pnu ? <Spinner label="불러오는 중…" /> : <span className="zb-mono zb-muted">{p.pnu}</span>}
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

function RedevSearch() {
  const [items, setItems] = useState<Redevelopment[]>([]);
  const [q, setQ] = useState("");
  const [opening, setOpening] = useNavPending<string>();
  useEffect(() => {
    api.searchRedevelopment(q).then((r) => setItems(r.items));
  }, [q]);
  return (
    <>
      <input placeholder="사업명·지역으로 검색 (예: 상계, 재개발)" value={q} onChange={(e) => setQ(e.target.value)} />
      <p className="zb-small zb-muted" style={{ margin: "8px 0 12px" }}>
        데모 목록입니다. 실서비스에서는 지자체 정비사업 공개 데이터와 연동하는 자리입니다.
      </p>
      <div className={opening ? "zb-opening" : undefined}>
      {items.map((p) => (
        <Link
          key={p.id}
          className={`zb-result-row${opening === p.id ? " is-opening" : ""}`}
          href={`/demo/zeb/plan?pnu=${p.representative_pnu}&source=sample`}
          onClick={() => setOpening(p.id)}
        >
          <span>
            <strong>{p.name}</strong>
            <br />
            <span className="zb-small zb-muted">
              {p.district} · {p.stage} · 대표필지 {area(p.area_m2)}
            </span>
          </span>
          {opening === p.id ? <Spinner label="불러오는 중…" /> : <span className="zb-pill">{p.type}</span>}
        </Link>
      ))}
      </div>
    </>
  );
}

function ManualForm({ meta }: { meta: Meta | null }) {
  const router = useRouter();
  const [f, setF] = useState({ area: "1000", zone: "제2종일반주거지역", juris: "11", addr: "" });
  const [opening, setOpening] = useNavPending<boolean>();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const p = new URLSearchParams({ area: f.area, zone: f.zone, juris: f.juris, addr: f.addr });
        setOpening(true);
        router.push(`/demo/zeb/plan?${p}`);
      }}
    >
      <div className="zb-grid zb-grid-2">
        <label className="zb-field">
          <span>대지면적 (㎡)</span>
          <input type="number" min={1} step="0.01" value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })} required />
        </label>
        <label className="zb-field">
          <span>용도지역</span>
          <select value={f.zone} onChange={(e) => setF({ ...f, zone: e.target.value })}>
            {(meta?.zones ?? [f.zone]).map((z) => (
              <option key={z}>{z}</option>
            ))}
          </select>
        </label>
        <label className="zb-field">
          <span>관할 (시도코드 2자리 또는 시군구코드 5자리)</span>
          <input value={f.juris} onChange={(e) => setF({ ...f, juris: e.target.value })} placeholder="11 = 서울특별시" />
        </label>
        <label className="zb-field">
          <span>대상지 이름 (선택)</span>
          <input value={f.addr} onChange={(e) => setF({ ...f, addr: e.target.value })} placeholder="예: OO동 검토 부지" />
        </label>
      </div>
      <button disabled={!!opening}>{opening ? <Spinner label="계산 화면 여는 중…" /> : "검토 시작"}</button>
    </form>
  );
}
