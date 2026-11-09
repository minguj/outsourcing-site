import type { Metadata } from "next";
import PlanView from "./plan-view";

export const metadata: Metadata = { title: "대상지 검토" };

export default function ZebPlanPage() {
  return <PlanView />;
}
