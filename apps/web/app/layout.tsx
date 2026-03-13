import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AuthProvider } from "../components/auth-provider";
import { SiteHeader } from "../components/site-header";

export const metadata: Metadata = {
  title: "Midas",
  description: "Local-first reflection workspace with account auth and live LLM streaming.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <div className="site-shell">
            <SiteHeader />
            {children}
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
