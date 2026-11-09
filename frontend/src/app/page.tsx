import type { Metadata } from "next";
import Landing from "./_site/landing";
import "./_site/site.css";
import { KEYWORDS, OPERATOR, SITE, SITE_URL } from "./site-config";
import { content } from "./site-content";

export const metadata: Metadata = {
  title: `${SITE.name} | ${SITE.tagline}`,
  description: SITE.description,
  keywords: KEYWORDS,
  alternates: { canonical: "/" },
  // 카카오톡·슬랙 등 링크 미리보기에 쓰인다.
  openGraph: {
    title: `${SITE.name} | ${SITE.tagline}`,
    description: SITE.description,
    url: SITE_URL,
    siteName: SITE.name,
    locale: "ko_KR",
    type: "website",
  },
};

// 검색엔진이 제품 성격과 자주 묻는 질문을 이해하도록 구조화 데이터를 함께 싣는다.
// 가격은 공개하지 않으므로 offers는 넣지 않는다.
function jsonLd() {
  const { FAQ, FLOW } = content("ko");
  return [
    {
      "@context": "https://schema.org", "@type": "SoftwareApplication",
      name: SITE.name, url: SITE_URL, description: SITE.description,
      applicationCategory: "BusinessApplication", operatingSystem: "Web", inLanguage: "ko",
      featureList: FLOW.map(s => `${s.title}: ${s.text}`),
      publisher: { "@type": "Organization", name: OPERATOR.brand, email: OPERATOR.email, url: SITE_URL },
    },
    {
      "@context": "https://schema.org", "@type": "FAQPage",
      mainEntity: FAQ.map(f => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
    },
  ];
}

export default function Home() {
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd()).replace(/</g, "\\u003c") }} />
    <Landing />
  </>;
}
