import type { Metadata } from "next";
import ReportView from "./report-view";

export const metadata: Metadata = { title: "초기 기획 검토 보고서" };

export default function ZebReportPage() {
  return <ReportView />;
}
