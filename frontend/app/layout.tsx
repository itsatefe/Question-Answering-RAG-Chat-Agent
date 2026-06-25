import "./globals.css";
import type { ReactNode } from "react";

export const metadata = { title: "RAG Generative UI" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
