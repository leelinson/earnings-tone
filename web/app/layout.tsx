import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Earnings Call Tone", template: "%s · Earnings Call Tone" },
  description: "Does hedging on an earnings call predict the stock's reaction? 1,735 calls from 64 US tech and communication services firms.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site">
          <div className="wrap">
            <Link href="/" className="brand">Earnings Call Tone</Link>
            <Link href="/">Explore a company</Link>
            <Link href="/walkthrough/">Project walkthrough</Link>
            <Link href="/results/">Main results</Link>
            <Link href="/robustness/">Does it hold up?</Link>
            <Link href="/data/">Data and glossary</Link>
          </div>
        </header>
        <main className="wrap">{children}</main>
        <footer className="site">
          <div className="wrap">
            A research portfolio project by Linson. Tone is scored with the Loughran-McDonald finance dictionary.
            Abnormal returns use a market model against SPY. EPS results are shown only as beat or miss; Q&amp;A text is
            shown as short excerpts. Not investment advice.
          </div>
        </footer>
      </body>
    </html>
  );
}
