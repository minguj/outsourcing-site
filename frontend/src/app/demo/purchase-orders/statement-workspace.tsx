"use client";

import { Fragment, useState } from "react";

export type Source = { file: string; sheet: string; row: number; cells: Record<string, string> };
export type PreviewRow = { number: number; cells: { address: string; text: string; colspan: number; rowspan: number; style: number }[] };
export type Item = { code: string; name: string; unit: string; price: string; registered?: boolean; pending?: boolean };
export type Line = { id: string; item_code: string; name: string; unit: string; quantity: string; price: string; supply: string; vat: string; total: string; due: string; sources: Source[] };
export type Row = { id: number; source: Source; original: Record<string, string | null>; name: string; item_code: string | null; item_registered?: boolean; unit: string; quantity: string | null; price: string; supply: string | null; vat: string | null; total: string | null; due: string; status: string; candidates: string[]; issues: { code: string; message: string }[]; audit: object[]; exclude_reason: string; restored?: boolean; restored_only?: boolean };
export type Order = { sample: string; customer: string; ordered: string; filename: string; sheet: string; rows: Row[]; lines: Line[]; preview: PreviewRow[]; layout_rows: { row: number; kind: string; label: string }[]; accepted: number; review: number; excluded: number; canceled: number; ready: boolean; totals: { supply: string; vat: string; total: string } };
export type Session = { revision: number; csrf: string; orders: Order[]; master: Item[]; summary: { source_rows: number; accepted: number; review: number; canceled: number } };
export type Action = { action: "resolve" | "exclude" | "reset" | "register" | "restore"; quantity?: string; item_code?: string; confirmed_amount?: string; reason?: string; new_code?: string; new_name?: string; new_unit?: string; new_price?: string };
export const COLUMNS = ["순번", "품목코드", "표준품명", "단위", "수량", "단가", "공급가액", "부가세", "합계"];
export const won = (value: string | null) => value === null ? "미계산" : `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 3 }).format(Number(value))}원`;
const status: Record<string, { icon: string; text: string }> = {
  accepted: { icon: "✓", text: "정상" }, review: { icon: "!", text: "확인 필요" },
  excluded: { icon: "−", text: "사유 기재 제외" }, canceled: { icon: "×", text: "취소 제외" },
};
type Entry = { key: string; row?: Row; line?: Line; sources: Source[]; number?: number; state: string };

function entries(order: Order): Entry[] {
  const seen = new Set<string>();
  return order.rows.flatMap<Entry>(row => {
    if (row.status !== "accepted") return [{ key: `row-${row.id}`, row, sources: [row.source], state: row.status }];
    const index = order.lines.findIndex(line => line.sources.some(s => s.row === row.id));
    const line = order.lines[index];
    if (!line || seen.has(line.id)) return [];
    seen.add(line.id);
    return [{ key: `group-${line.sources.map(s => s.row).join("-")}`, line, sources: line.sources, number: index + 1, state: "accepted" }];
  });
}

export function Original({ sample, filename, sheet, rows }: { sample: string; filename: string; sheet: string; rows: PreviewRow[] }) {
  return <><div className="po-pane-heading"><div><span className="po-kicker">거래처 {sample}의 발주서</span><h2>원본</h2><p>{filename} · {sheet}</p></div>
    <a href={`/samples/purchase-orders/${filename}`} download>원본 받기 ↗</a></div>
    <p className="po-help">실제 XLSX 셀·병합 정보를 표시합니다. 좌우 스크롤로 모든 열을 확인하고, 셀 위에서 원본 주소를 확인하세요.</p>
    <div className="po-source-scroll" tabIndex={0} role="region" aria-label={`거래처 ${sample} 원본 가로 스크롤 표`}>
      <table className={`po-source-table po-source-${sample}`}><tbody>{rows.map(row => <tr key={row.number}>
        <th className="po-row-number" scope="row">{row.number}</th>{row.cells.map(cell => <td key={cell.address} colSpan={cell.colspan} rowSpan={cell.rowspan} title={cell.address} className={`po-s${cell.style}`}>{cell.text}</td>)}
      </tr>)}</tbody></table>
    </div>
    <p className="po-help">미리보기는 Excel의 인쇄 화면과 차이가 있습니다.</p></>;
}

const FIELD_LABELS: Record<string, string> = {
  line: "순번", code: "품목코드", name: "품명", spec: "규격·옵션", unit: "단위",
  quantity: "수량", price: "단가", amount: "기재 금액", due: "납기",
  order_id: "주문번호", order_status: "주문상태", vendor_sku: "거래처 상품번호",
  ordered: "주문일시", note: "비고",
};

function SourceDetails({ entry, order, busy, submit }: { entry: Entry; order: Order; busy: boolean; submit: (row: Row, action: Action) => void }) {
  const members = entry.sources.map(source => order.rows.find(r => r.id === source.row)!);
  const count = (entry.line ?? entry.row!).quantity;
  const quantities = members.map(row => row.quantity);
  const arithmetic = quantities.every(q => q !== null)
    ? quantities.length > 1 ? quantities.join("+") + "=" + count : String(count)
    : "미입력";
  return <details className="po-trace"><summary>{"원본 " + entry.sources.map(s => s.row).join("·") + "행 / 수량 " + arithmetic}</summary>
    {entry.sources.map(source => {
      const original = order.rows.find(r => r.id === source.row)!;
      return <div className="po-trace-item" key={source.row}><strong>{"원본 " + source.row + "행"}</strong><p>파일명 {source.file} · 시트 {source.sheet}</p>
        <p className="po-korean-cells">{Object.entries(source.cells).map(([key, address]) => (FIELD_LABELS[key] ?? "참고 셀") + " " + address).join(" · ")}</p>
        <p>원본 품목 {original.original.name} {original.original.spec} / 수량 {original.original.quantity ?? "누락"} / 단가 {won(original.original.price)} / 기재 금액 {won(original.original.amount)}</p>
        {original.exclude_reason && <p>제외 사유: {original.exclude_reason}</p>}
        {original.audit.length > 0 && original.status !== "canceled" && <><p>변경 기록 {original.audit.length}건{original.restored ? " · 원본은 취소 주문" : ""}</p><button className="po-text-button" disabled={busy} onClick={() => submit(original, { action: "reset" })}>{original.restored_only ? `원본 ${source.row}행 다시 취소 상태로` : `원본 ${source.row}행 수정 되돌리기`}</button></>}
      </div>;
    })}
  </details>;
}

function StatementRow({ entry, order, master, busy, submit }: { entry: Entry; order: Order; master: Item[]; busy: boolean; submit: (row: Row, action: Action) => void }) {
  const { row, line, state } = entry;
  const [quantity, setQuantity] = useState(row?.quantity ?? "");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [excludeOpen, setExcludeOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newName, setNewName] = useState(row?.original.name ?? "");
  const [newUnit, setNewUnit] = useState(row?.original.unit ?? row?.unit ?? "");
  const [newPrice, setNewPrice] = useState(row?.original.price ?? "");
  const issues = state === "review" ? row!.issues : [];
  const missing = issues.some(i => i.code === "MISSING_QUANTITY");
  const mismatch = issues.some(i => i.code === "AMOUNT_MISMATCH");
  const needsItem = issues.some(i => ["UNKNOWN_ITEM", "AMBIGUOUS_ITEM"].includes(i.code));
  const unknown = issues.some(i => i.code === "UNKNOWN_ITEM");
  const nextCode = "S" + String(Math.max(0, ...master.map(m => /^S\d+$/.test(m.code) ? Number(m.code.slice(1)) : 0)) + 1).padStart(3, "0");
  const label = (code: string | null) => code === null ? null : master.some(m => m.code === code && m.pending) ? "미정" : code;
  const codeTaken = newCode.trim() !== "" && master.some(m => m.code === newCode.trim().toUpperCase());
  const codeInvalid = newCode.trim() !== "" && !/^[A-Za-z0-9][A-Za-z0-9-]{1,9}$/.test(newCode.trim());
  const units = [...new Set(master.map(m => m.unit))];
  const canRegister = !codeTaken && !codeInvalid && newName.trim().length >= 2 && newUnit.trim().length >= 1 && newPrice.trim().length > 0;
  const candidates = row && row.candidates.length > 1 ? master.filter(m => row.candidates.includes(m.code)) : master;
  const data = line ?? row!;
  const badge = status[state];
  const active = state === "accepted";
  const expanded = detailsOpen || excludeOpen || registerOpen;
  const registeredCode = line ? master.some(m => m.code === line.item_code && m.registered) : !!row?.item_registered;
  function toggleDetails() {
    if (expanded) { setDetailsOpen(false); setExcludeOpen(false); setRegisterOpen(false); } else setDetailsOpen(true);
  }
  return <Fragment>
    <tr className={"po-data-row po-status-" + state} data-review-row={row?.id} data-row-state={state} data-group={line?.id} data-editing={editing} data-expanded={expanded}>
      <td className="po-sequence">{entry.number ?? (state === "review" ? "미정" : "—")}</td>
      <td className={"po-cell-code " + (needsItem ? "po-problem-cell" : "")} data-problem={needsItem || undefined} data-label="품목 선택">
        <span className="po-desktop-code">{label(data.item_code) ?? "미정"}{registeredCode && <small className="po-new-item-tag">신규</small>}</span>
        {needsItem && <label className="po-cell-edit po-editor"><span>품목 선택</span><select aria-label={row!.id + "행 마스터 품목"} value="" disabled={busy} onChange={e => { if (e.target.value) { setConfirmed(false); submit(row!, { action: "resolve", item_code: e.target.value }); } }}>
          <option value="">선택…</option>{candidates.map(m => <option value={m.code} key={m.code}>{m.pending ? "미정" : m.code} · {m.name} · {m.unit} · {won(m.price)}{m.registered ? " · 신규 등록" : ""}</option>)}
        </select><small>표준명·단위·기준단가로 재검증</small>{unknown && <button className="po-text-button po-register-link" disabled={busy} onClick={() => { setRegisterOpen(true); setDetailsOpen(true); }}>+ 신규 등록</button>}</label>}
      </td>
      <td className={"po-cell-name " + (needsItem ? "po-problem-cell" : "")}>
        <div className="po-name-line">
          <span className={"po-state-badge po-badge-" + state}><b aria-hidden="true">{badge.icon}</b>{badge.text}</span>
          <strong className="po-item-name" title={data.name}>{data.name}</strong>{row?.restored && <small className="po-restored-tag">취소 철회</small>}
          {state === "review" && <button className="po-mobile-edit" aria-expanded={editing} aria-label={row!.id + "행 수정"} disabled={busy} onClick={() => { setEditing(!editing); setConfirmed(false); }}>{editing ? "닫기" : "수정"}</button>}
          <button className="po-details-toggle" aria-expanded={expanded} aria-label={"원본 " + entry.sources.map(s => s.row).join("·") + "행 상세"} onClick={toggleDetails}>{expanded ? "접기" : "상세"}</button>
          <small className="po-mobile-code">{state === "canceled" ? "취소 주문" : label(data.item_code) ?? "미등록"} · {data.unit}</small>
        </div>
        {issues.length > 0 && <div className="po-cell-issue"><span aria-hidden="true">⚠ </span>{issues.map(i => ({ MISSING_QUANTITY: "수량 누락", UNKNOWN_ITEM: "미등록 품목", AMBIGUOUS_ITEM: "M/L 선택 필요", AMOUNT_MISMATCH: "기재·계산 금액 차이" }[i.code] ?? i.message)).join(" · ")}</div>}
        {state === "review" && <div className="po-error-actions"><button className="po-text-button" disabled={busy} onClick={() => { setExcludeOpen(true); setDetailsOpen(true); }}>사유 입력·제외</button></div>}
        {state === "excluded" && <small className="po-exclusion-reason">제외 사유: {row!.exclude_reason}</small>}
        {state === "canceled" && <div className="po-cancel-actions"><button className="po-text-button" disabled={busy} aria-label={row!.id + "행 취소 철회"} onClick={() => submit(row!, { action: "restore" })}>↺ 취소 철회</button><small>철회하면 일반 주문처럼 다시 검수합니다</small></div>}
      </td>
      <td className="po-cell-unit">{data.unit}</td>
      <td className={"po-cell-quantity " + (missing ? "po-problem-cell" : "")} data-problem={missing || undefined} data-label="수량">
        {missing ? <><span className="po-mobile-rest-value">수량 누락</span><div className="po-quantity-edit po-editor"><label><span>! 필수 수량</span><input aria-label={row!.id + "행 수량"} inputMode="decimal" maxLength={24} value={quantity} disabled={busy} onChange={e => setQuantity(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && quantity.trim()) submit(row!, { action: "resolve", quantity }); }} placeholder="수량" /></label>
          <button disabled={busy || !quantity.trim()} onClick={() => submit(row!, { action: "resolve", quantity })}>적용·재검증</button></div></> : <span>{data.quantity ?? "누락"}<small className="po-mobile-unit"> {data.unit}</small></span>}
      </td>
      <td className="po-cell-price po-money" data-label="단가">{won(data.price)}</td>
      <td className={"po-cell-supply po-money " + (mismatch ? "po-problem-cell" : "")} data-problem={mismatch || undefined} data-label="계산 공급가액">
        <strong>{state === "canceled" || state === "excluded" ? "—" : won(data.supply)}</strong>
        {mismatch && <div className="po-amount-confirm po-editor"><small>원본 기재 {won(row!.original.amount)}</small><label><input type="checkbox" aria-label={row!.id + "행 계산 금액 사용 확인"} checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} /> 계산 금액 사용 확인</label>
          <button disabled={busy || !confirmed} onClick={() => submit(row!, { action: "resolve", confirmed_amount: row!.supply! })}>금액 확정</button></div>}
      </td>
      <td className="po-cell-vat po-money">{active ? won(data.vat) : "—"}</td>
      <td className="po-cell-total po-money" data-label={active ? "금액 (VAT 포함)" : "금액"}>{active ? won(data.total) : state === "review" ? "발행 보류" : "—"}</td>
    </tr>
    {expanded && <tr className={"po-row-tools po-status-" + state} data-tools-row={row?.id} data-tools-key={entry.key}>
      <td colSpan={9}><div className="po-row-detail">
        <div className="po-row-meta"><strong>행 상세</strong><span>납기 {data.due}</span><span>단위 {data.unit}</span><span>단가 {won(data.price)}</span>{active && <span>부가세 {won(data.vat)}</span>}</div>
        {registerOpen && row && unknown && <form className="po-inline-register" aria-label={row.id + "행 신규 품목 등록"} onSubmit={e => { e.preventDefault(); if (canRegister) submit(row, { action: "register", new_code: newCode.trim(), new_name: newName, new_unit: newUnit, new_price: newPrice }); }}>
          <div className="po-register-head"><strong>마스터에 없는 품목 · 신규 등록</strong></div>
          <div className="po-register-fields">
            <label>품목코드<input aria-label={row.id + "행 신규 품목코드"} value={newCode} maxLength={10} disabled={busy} placeholder={"예: " + nextCode + " · 비우면 미정"} aria-invalid={codeTaken || codeInvalid} onChange={e => setNewCode(e.target.value)} />
              {codeTaken ? <em className="po-field-error">이미 있는 코드입니다</em> : codeInvalid ? <em className="po-field-error">영문·숫자·하이픈 2~10자</em> : !newCode.trim() && <em className="po-field-hint">미정으로 등록</em>}</label>
            <label>표준품명<input aria-label={row.id + "행 신규 표준품명"} value={newName} maxLength={40} disabled={busy} onChange={e => setNewName(e.target.value)} /></label>
            <label>단위<input aria-label={row.id + "행 신규 단위"} list={"po-units-" + row.id} value={newUnit} maxLength={10} disabled={busy} onChange={e => setNewUnit(e.target.value)} /><datalist id={"po-units-" + row.id}>{units.map(u => <option key={u} value={u} />)}</datalist></label>
            <label>기준단가(원)<input aria-label={row.id + "행 신규 기준단가"} inputMode="decimal" value={newPrice} maxLength={14} disabled={busy} onChange={e => setNewPrice(e.target.value)} /></label>
          </div>
          <small>품명·단위·단가는 원본 값으로 미리 채웠습니다. 품목코드를 비워 두면 &apos;미정&apos;으로 등록되어 거래명세서에도 미정으로 표시됩니다. 이번 체험에만 등록되며 실제 품목 마스터 파일은 바뀌지 않습니다. 기준단가가 원본 단가와 다르면 금액 확인이 추가로 필요합니다.</small>
          <div className="po-register-actions"><button type="submit" disabled={busy || !canRegister}>등록 후 재검증</button><button type="button" className="po-text-button" disabled={busy} onClick={() => setRegisterOpen(false)}>취소</button></div>
        </form>}
        <SourceDetails entry={entry} order={order} busy={busy} submit={submit} />
        {excludeOpen && row && state === "review" && <div className="po-inline-exclude"><label>제외 사유<textarea aria-label={row.id + "행 제외 사유"} value={reason} maxLength={200} disabled={busy} onChange={e => setReason(e.target.value)} placeholder="예: 거래처 확인 전 이번 발행에서 제외" /></label>
          <small>실제 개인정보 없이 세 글자 이상 입력하세요.</small><button disabled={busy || reason.trim().length < 3} onClick={() => submit(row, { action: "exclude", reason })}>사유 기록 후 제외</button></div>}
        {row && state === "excluded" && <button className="po-text-button" disabled={busy} onClick={() => submit(row, { action: "reset" })}>제외 취소·다시 검수</button>}
      </div></td>
    </tr>}
  </Fragment>;
}

export const REPLY_FORMS = [
  { id: "A", label: "A 거래처 · 인쇄용 발주서 양식" },
  { id: "B", label: "B 거래처 · 쇼핑몰 주문 내역 양식" },
  { id: "C", label: "C 거래처 · 제조업 구매 발주서 양식" },
];

export function Statement({ order, master, busy, review, download }: { order: Order; master: Item[]; busy: boolean; review: (row: Row, action: Action) => void; download: (layout?: string) => void }) {
  const [filter, setFilter] = useState<"all" | "review" | "excluded">("all");
  const [layout, setLayout] = useState(order.sample);
  const all = entries(order);
  const counts = { all: all.length, review: order.review, excluded: order.excluded + order.canceled };
  const shown = all.filter(entry => filter === "all" || (filter === "review" ? entry.state === "review" : ["excluded", "canceled"].includes(entry.state)));
  return <><div className="po-pane-heading"><div><span className="po-kicker">우리 회사의 공통 양식</span><h2>거래명세서</h2><p>{order.sample} 거래처 개별 출력 · {order.customer}</p></div><span className={`po-document-state ${order.ready ? "po-ready" : ""}`}>{order.ready ? "✓ 검수 완료" : `! 확인 ${order.review}행 남음`}</span></div>
    <div className="po-document-info"><span>공급자 <b>(가상)모아소모품 도매</b></span><span>발주일 {order.ordered}</span><span>금액 KRW · 세전 단가</span></div>
    <p className="po-help">A/B/C를 합치지 않습니다. 각 거래처를 아래의 동일한 9열 양식으로 발행합니다.</p>
    <div className="po-filter-bar" aria-label="결과 행 필터">{([["all", "전체"], ["review", "확인 필요"], ["excluded", "제외"]] as const).map(([key, label]) => <button key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label} <b>{counts[key]}</b></button>)}<span role="status">남은 확인 <strong>{order.review}행</strong></span></div>
    <p className="po-help">확정 원본 {order.accepted}행 → 출력 {order.lines.length}행{order.sample === "B" ? " (품목·단위·단가·납기별 취합)" : ""}. 미해결 행은 표에 남겨 두고 합계에서 제외합니다. 납기와 원본 추적은 각 행의 상세에서 확인하세요.</p>
    <div className="po-result-scroll" tabIndex={0} role="region" aria-label="공통 거래명세서 결과 표">
      <table className="po-statement-table"><caption className="po-sr-only">{order.customer} 거래명세서 — 다운로드 XLSX와 동일한 열 순서</caption><colgroup>{[40,80,260,45,100,84,150,85,105].map((width, i) => <col key={i} style={{ width }} />)}</colgroup>
        <thead><tr>{COLUMNS.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead>
        <tbody>{shown.map(entry => <StatementRow key={`${order.sample}-${entry.key}-${entry.row?.status ?? "group"}`} entry={entry} order={order} master={master} busy={busy} submit={review} />)}
          {shown.length === 0 && <tr><td colSpan={9} className="po-empty-result">{filter === "review" ? "✓ 남은 확인 행이 없습니다. 전체 필터에서 결과를 확인하세요." : "이 필터에 해당하는 행이 없습니다."}</td></tr>}</tbody>
        <tfoot><tr><th colSpan={6} scope="row">{order.ready ? "검수 완료 합계" : "정상 행 부분 합계 · 최종 금액 아님"}</th><td>{won(order.totals.supply)}</td><td>{won(order.totals.vat)}</td><td data-total={order.totals.total}>{won(order.totals.total)}</td></tr></tfoot>
      </table>
    </div>
    <div className="po-amount-summary" aria-label="현재 거래처 합계"><div><span>공급가액</span><strong>{won(order.totals.supply)}</strong></div><div><span>부가세</span><strong>{won(order.totals.vat)}</strong></div><div><span>{order.ready ? "검수 완료 합계" : "정상 행 부분 합계"}</span><strong>{won(order.totals.total)}</strong></div></div>
    <p className="po-totals-note">합계는 필터와 무관하게 서버가 확정한 행만 계산합니다. {order.review > 0 ? `미해결 ${order.review}행이 있어 이 거래처의 최종 발행은 보류됩니다.` : "확인 필요 행이 없어 이 거래처를 발행할 수 있습니다."}</p>
    <div className="po-download-bar"><div><strong>{order.sample} 거래처만 개별 다운로드</strong><p>동일한 거래명세서 양식 + 원본추적·납기별내역</p></div><button disabled={!order.ready || busy} onClick={() => download()}>검수 완료 XLSX 다운로드 ↓</button></div>
    <div className="po-reply-bar">
      <div><strong>거래처 양식으로 회신 <span className="po-reverse-tag">반대 방향</span></strong><p>검수 결과를 거래처가 쓰는 원래 양식에 다시 채워 내려받습니다. 품번·품명·규격은 그 거래처의 기존 발주 기록으로 되돌려 쓰고, 기록이 없는 품목은 표준품명으로 표기해 비고와 변환기록 시트에 남깁니다.</p></div>
      <div className="po-reply-controls">
        <label><span>회신 양식</span><select aria-label="회신할 거래처 양식" value={layout} disabled={busy} onChange={e => setLayout(e.target.value)}>{REPLY_FORMS.map(f => <option key={f.id} value={f.id}>{f.label}{f.id === order.sample ? " (이 거래처)" : ""}</option>)}</select></label>
        <button className="po-secondary" disabled={!order.ready || busy} onClick={() => download(layout)}>{layout} 양식 XLSX 다운로드 ↓</button>
      </div>
    </div>
    {!order.ready && <p className="po-reply-note">확인 필요 행을 모두 처리하면 거래처 양식 회신도 내려받을 수 있습니다.</p>}
    {order.layout_rows.length > 0 && <details className="po-layout-log"><summary>원본의 비주문 행 처리 기록</summary>{order.layout_rows.map(r => <p key={r.row}>원본 {r.row}행 · {({ blank: "빈 행", subtotal: "소계", total: "합계", layout: "안내·구분행", section: "구분행" }[r.kind] ?? "기타 행")} · {r.label || "빈 행"} — 주문 제외</p>)}</details>}
  </>;
}
