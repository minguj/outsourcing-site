import type { Metadata } from "next";
import PurchaseDemo from "./purchase-demo";

export const metadata: Metadata = {
  title: "발주서 자동 변환·검수 체험",
  description: "서로 다른 가상 발주서를 읽고, 검수한 뒤 공통 거래명세서로 내려받는 샘플 전용 체험입니다.",
};

export default function PurchaseOrdersPage() {
  return <PurchaseDemo />;
}
