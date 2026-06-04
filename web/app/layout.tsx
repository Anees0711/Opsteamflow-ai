import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "OpsTeamFlow AI",
  description: "Dashboard for AI workflow runs, RAG citations, and reliability metrics.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#ffffff", color: "#111827" }}>{children}</body>
    </html>
  );
}
