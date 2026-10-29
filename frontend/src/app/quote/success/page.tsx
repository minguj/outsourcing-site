import type { Metadata } from "next";
import QuoteView from "../quote-view";
import "../../_site/site.css";
import { SITE } from "../../site-config";

export const metadata: Metadata = { title: `결제 확인 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function QuoteSuccessPage() {
  return <QuoteView mode="success" />;
}
