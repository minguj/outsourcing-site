import type { Metadata } from "next";
import Landing from "./_site/landing";
import "./_site/site.css";
import { SITE } from "./site-config";

export const metadata: Metadata = {
  title: `${SITE.name} | ${SITE.tagline}`,
  description: SITE.description,
};

export default function Home() {
  return <Landing />;
}
