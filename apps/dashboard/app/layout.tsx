import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PortalSentinel Replay",
  description: "Judge-friendly replay dashboard for Portaldot identity and workflow runs."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

