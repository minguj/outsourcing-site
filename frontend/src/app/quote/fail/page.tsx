import type { Metadata } from "next";
import QuoteView from "../quote-view";
import "../../_site/site.css";
import { SITE } from "../../site-config";

export const metadata: Metadata = { title: `결제 실패 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function QuoteFailPage() {
  return <QuoteView mode="fail" />;
}
