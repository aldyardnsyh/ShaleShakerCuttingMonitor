import type { Metadata } from "next";
import "./globals.css";
import { DashboardProvider } from "@/components/DashboardContext";
import { ToastProvider } from "@/components/Toast";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Shale Shaker Cutting Monitoring",
  description: "Estimasi cutting shale shaker berbasis computer vision",
  icons: {
    icon: [{ url: "/icon.png", type: "image/png" }, { url: "/favicon.ico" }],
    shortcut: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body>
        <ToastProvider>
          <DashboardProvider>
            <AppShell>{children}</AppShell>
          </DashboardProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
