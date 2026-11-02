import type { Metadata } from "next";
import Landing from "./_site/landing";
import "./_site/site.css";
import { SITE } from "./site-config";

export const metadata: Metadata = {
  title: `${SITE.name} | ${SITE.tagline}`,
  description: SITE.description,
  // 카카오톡·슬랙 등 링크 미리보기에 쓰인다.
  openGraph: {
    title: `${SITE.name} | ${SITE.tagline}`,
    description: SITE.description,
    url: "https://fitagent.co.kr",
    siteName: SITE.name,
    locale: "ko_KR",
    type: "website",
  },
};

export default function Home() {
  return <Landing />;
}
