import type { MetadataRoute } from "next";
import { SITE_URL } from "./site-config";

// 견적서·계약서·관리 화면은 고객별 주소라 검색에 올리지 않는다(각 페이지에도 noindex가 있다).
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/admin", "/quote", "/contract", "/en", "/api/"] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
