import type { Metadata } from "next";
import SpendApp from "./spend-app";

export const metadata: Metadata = { title: "한눈에 보기" };

export default function SpendPage() {
  return <SpendApp />;
}
