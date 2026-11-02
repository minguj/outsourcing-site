import type { Metadata } from "next";
import CompletionView from "./completion-view";
import "../../_site/site.css";
import { SITE } from "../../site-config";

export const metadata: Metadata = { title: `완료 확인서 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function CompletionPage() {
  return <CompletionView />;
}
