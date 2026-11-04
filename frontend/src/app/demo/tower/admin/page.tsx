import type { Metadata } from "next";
import AdminView from "./admin-view";

export const metadata: Metadata = { title: "관리자 웹" };

export default function TowerAdminPage() {
  return <AdminView />;
}
