"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { ANALYTICS } from "../site-config";

// Google Analytics 4. 측정 ID(site-config.ts ANALYTICS.ga)가 비어 있으면 아무것도 불러오지 않는다.
// 견적서·계약서·관리 화면은 주소에 고객별 토큰이 들어가므로 수집하지 않는다.
const PRIVATE = ["/admin", "/quote", "/contract"];
const isPrivate = (path: string) => PRIVATE.some(p => path === p || path.startsWith(p + "/"));

type Gtag = (...args: unknown[]) => void;
declare global { interface Window { dataLayer?: unknown[]; gtag?: Gtag } }

function gtag(): Gtag | null {
  if (!ANALYTICS.ga || typeof window === "undefined" || isPrivate(window.location.pathname)) return null;
  if (!window.gtag) {
    window.dataLayer = window.dataLayer || [];
    // gtag.js는 arguments 객체 그대로를 기대한다.
    window.gtag = function () { window.dataLayer!.push(arguments); }; // eslint-disable-line prefer-rest-params
    window.gtag("js", new Date());
    // 페이지 조회는 아래에서 토큰 없는 주소로 직접 보낸다.
    window.gtag("config", ANALYTICS.ga, { send_page_view: false });
  }
  return window.gtag;
}

/** 버튼 클릭·접수 같은 행동을 기록한다. 이름·연락처·상담 내용은 넣지 않는다. */
export function track(event: string, params: Record<string, string | number | boolean> = {}) {
  gtag()?.("event", event, params);
}

// 광고 성과를 구분하려고 유입 표시 파라미터(utm_*, gclid 등)만 남긴다. 다른 쿼리는 버린다.
const CAMPAIGN = /^(utm_[a-z_]+|gclid|gbraid|wbraid|fbclid|n_media|n_query)$/;
function campaignQuery() {
  const kept = new URLSearchParams();
  new URLSearchParams(window.location.search).forEach((v, k) => { if (CAMPAIGN.test(k)) kept.append(k, v); });
  const q = kept.toString();
  return q ? "?" + q : "";
}

// 개발 모드에서 effect가 두 번 돌아도 같은 페이지를 두 번 세지 않는다.
let lastPath = "";

export function Analytics() {
  const pathname = usePathname();
  useEffect(() => {
    // 쿼리 문자열은 유입 표시 파라미터만 남기고 뺀다.
    if (pathname === lastPath) return;
    lastPath = pathname;
    gtag()?.("event", "page_view", { page_location: window.location.origin + pathname + campaignQuery(), page_path: pathname, page_title: document.title });
  }, [pathname]);
  if (!ANALYTICS.ga || isPrivate(pathname)) return null;
  return <Script src={`https://www.googletagmanager.com/gtag/js?id=${ANALYTICS.ga}`} strategy="afterInteractive" />;
}
