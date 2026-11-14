import type { Metadata } from "next";
import SiteView from "./site-view";

export const metadata: Metadata = { title: "홈페이지" };

export default function NurseSitePage() {
  return <SiteView />;
}
