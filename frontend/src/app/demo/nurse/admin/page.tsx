import type { Metadata } from "next";
import AdminView from "./admin-view";

export const metadata: Metadata = { title: "관리자" };

export default function NurseAdminPage() {
  return <AdminView />;
}
