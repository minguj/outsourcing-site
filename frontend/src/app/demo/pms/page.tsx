import type { Metadata } from "next";
import PmsApp from "./pms-app";

export const metadata: Metadata = { title: "운영 대시보드" };

export default function PmsPage() {
  return <PmsApp />;
}
