import type { Metadata } from "next";
import MaintenanceView from "./maintenance-view";
import "../../_site/site.css";
import { SITE } from "../../site-config";

export const metadata: Metadata = { title: `유지보수 계약서 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function MaintenancePage() {
  return <MaintenanceView />;
}
