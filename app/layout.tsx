import type { Metadata } from "next";
import { Manrope, DM_Sans } from "next/font/google";
import "./globals.css";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-display" });
const dmSans = DM_Sans({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "Vioum — Scanner les arnaques Mobile Money",
  description: "Analysez un SMS ou une capture suspecte avec Gemma.",
  icons: { icon: "/logo.webp" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body className={`${manrope.variable} ${dmSans.variable}`}>{children}</body></html>;
}
