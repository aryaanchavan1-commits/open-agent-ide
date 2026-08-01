import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Arynox AI — Local AI Software Engineering Platform",
  description: "Describe a software project, and specialized AI agents plan, code, test and debug it locally.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}
