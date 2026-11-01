import type { Metadata } from "next";
import ContractView from "./contract-view";
import "../_site/site.css";
import { SITE } from "../site-config";

export const metadata: Metadata = { title: `계약서(안) | ${SITE.name}`, robots: { index: false, follow: false } };

export default function ContractPage() {
  return <ContractView />;
}
