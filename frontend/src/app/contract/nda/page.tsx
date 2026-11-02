import type { Metadata } from "next";
import NdaView from "./nda-view";
import "../../_site/site.css";
import { SITE } from "../../site-config";

export const metadata: Metadata = { title: `비밀유지계약서 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function NdaPage() {
  return <NdaView />;
}
