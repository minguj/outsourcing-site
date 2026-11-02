import type { MetadataRoute } from "next";
import { SITE_URL } from "./site-config";

// 검색엔진에 알리는 공개 페이지 목록. 공개 페이지를 새로 만들면 여기에 추가한다.
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: SITE_URL, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/demo/purchase-orders`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/privacy`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${SITE_URL}/terms`, changeFrequency: "yearly", priority: 0.2 },
  ];
}
