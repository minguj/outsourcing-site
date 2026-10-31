import type { Metadata } from "next";
import Landing from "../_site/landing";
import "../_site/site.css";
import { SITE_EN } from "../site-config";

export const metadata: Metadata = {
  title: `${SITE_EN.name} | ${SITE_EN.tagline}`,
  description: SITE_EN.description,
  // 보류 중: 검색에 노출하지 않는다. 다시 열 때 robots를 지우고 alternates를 되살린다.
  robots: { index: false, follow: false },
};

export default function EnglishHome() {
  return <Landing lang="en" />;
}
