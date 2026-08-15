import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "SmileCare AI | مساعد الاستقبال الذكي",
  description:
    "عيادة SmileCare للأسنان — مساعد الاستقبال الذكي. احجز موعدك واستفسر عن خدماتنا على مدار الساعة.",
  keywords: ["عيادة أسنان", "حجز مواعيد", "SmileCare", "مساعد ذكي"],
  openGraph: {
    title: "SmileCare AI | مساعد الاستقبال الذكي",
    description:
      "عيادة SmileCare للأسنان — احجز موعدك واستفسر عن خدماتنا على مدار الساعة.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${inter.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-slate-50">{children}</body>
    </html>
  );
}

