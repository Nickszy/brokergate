import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BrokerGate 聚合资产台",
  description: "BrokerGate 多券商、多账户统一资产与交易页面。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
