"use client";

import { useEffect, useState } from "react";

// 데이터를 불러오는 동안의 표시. 계산 결과가 바뀌는 중에 이전 결과로 보고서를 저장하는 일을 막기 위해
// 화면 위쪽 진행 막대 + 버튼 비활성화를 함께 쓴다.

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="zb-spinner-wrap" role="status" aria-live="polite">
      <span className="zb-spinner" aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
}

/** 화면 맨 위에 붙는 진행 막대 (계산 중일 때만) */
export function BusyBar({ show }: { show: boolean }) {
  return show ? <div className="zb-busybar" role="progressbar" aria-label="계산 중" /> : null;
}

/** 다른 화면으로 넘어가는 중 표시(누른 항목 id). 브라우저 뒤로 가기로 돌아오면 지워진다.
 *  - 화면을 떠날 때(언마운트·Next 가 화면을 숨길 때) 정리 함수에서 지운다.
 *  - 브라우저가 페이지를 통째로 보관했다가 되살린 경우(bfcache)는 pageshow 에서 지운다. */
export function useNavPending<T>() {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    const onShow = (e: PageTransitionEvent) => {
      if (e.persisted) setValue(null);
    };
    window.addEventListener("pageshow", onShow);
    return () => {
      window.removeEventListener("pageshow", onShow);
      setValue(null);
    };
  }, []);
  return [value, setValue] as const;
}

/** 첫 화면 전체 로딩 */
export function LoadingCard({ label }: { label: string }) {
  return (
    <div className="zb-card zb-loading-card">
      <Spinner label={label} />
    </div>
  );
}
