import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "产品手册助手",
  description: "产品使用与安全问答",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
