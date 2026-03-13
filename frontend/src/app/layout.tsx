import type { Metadata } from "next";
import "./globals.css";
import { Inter } from "next/font/google";
import { ClientProviders } from "@/components/client-providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AIDE",
  description: "AI for Discovery & Exploration",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable} translate="no" suppressHydrationWarning>
      <head>
        <meta name="google" content="notranslate" />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var t=localStorage.getItem("aide-theme");if(t==="dark")document.documentElement.setAttribute("data-theme","dark")})()`,
          }}
        />
      </head>
      <body className="notranslate bg-aide-bg-primary" suppressHydrationWarning>
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  );
}
