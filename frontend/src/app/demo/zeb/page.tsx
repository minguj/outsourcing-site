import type { Metadata } from "next";
import ZebHome from "./home";

export const metadata: Metadata = { title: "대상지 검색" };

export default function ZebPage() {
  return <ZebHome />;
}
