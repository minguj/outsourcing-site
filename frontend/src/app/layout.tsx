import type { Metadata } from "next";
import { Geist, Geist_Mono, IBM_Plex_Sans_KR } from "next/font/google";
import "./globals.css";
import { SEARCH_VERIFY, SITE, SITE_URL } from "./site-config";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const plexKr = IBM_Plex_Sans_KR({
  variable: "--font-plex-kr",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE.name,
  description: SITE.description,
  verification: {
    ...(SEARCH_VERIFY.google ? { google: SEARCH_VERIFY.google } : {}),
    ...(SEARCH_VERIFY.naver ? { other: { "naver-site-verification": SEARCH_VERIFY.naver } } : {}),
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ko"
      className={`${geistSans.variable} ${geistMono.variable} ${plexKr.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
