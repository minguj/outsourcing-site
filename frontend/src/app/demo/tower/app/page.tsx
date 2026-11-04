import type { Metadata } from "next";
import AppView from "./app-view";

export const metadata: Metadata = { title: "앱 화면" };

export default function TowerAppPage() {
  return <AppView />;
}
