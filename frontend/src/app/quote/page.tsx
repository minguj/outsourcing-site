import type { Metadata } from "next";
import QuoteView from "./quote-view";
import "../_site/site.css";
import { SITE } from "../site-config";

export const metadata: Metadata = { title: `견적서 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function QuotePage() {
  return <QuoteView mode="view" />;
}
