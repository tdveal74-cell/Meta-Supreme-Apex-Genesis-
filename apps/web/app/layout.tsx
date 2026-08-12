import type { Metadata } from "next";
import { brand } from "@meta-supreme/ui";
import "./globals.css";

export const metadata: Metadata = {
  title: `${brand.name} — ${brand.category}`,
  description: brand.principle,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-surface text-navy antialiased">{children}</body>
    </html>
  );
}
