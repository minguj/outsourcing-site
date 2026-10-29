import type { Metadata } from "next";
import AdminApp from "./admin-app";
import "../_site/site.css";
import { SITE } from "../site-config";

export const metadata: Metadata = { title: `관리 | ${SITE.name}`, robots: { index: false, follow: false } };

export default function AdminPage() {
  return <AdminApp />;
}
