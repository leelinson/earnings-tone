import type { Metadata, Viewport } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import Link from "next/link";
import Nav from "@/components/Nav";
import "./globals.css";

// Fonts are downloaded at build time and served with the site, so nothing loads from Google at runtime.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const serif = Source_Serif_4({ subsets: ["latin"], weight: ["600"], variable: "--font-serif-display", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Earnings Call Tone", template: "%s · Earnings Call Tone" },
  description: "Does hedging on an earnings call predict the stock's reaction? 1,735 calls from 64 US tech and communication services firms.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#18191c" },
  ],
};

function Mark() {
  // a small waveform: the call's voice, rising and falling
  return (
    <span className="mark" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <path d="M2 8v0M5 5v6M8 2.5v11M11 5.5v5M14 7v2" />
      </svg>
    </span>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${serif.variable}`}>
      <body>
        <header className="site">
          <div className="wrap bar">
            <Link href="/" className="brand"><Mark />Earnings Call Tone</Link>
            <Nav />
          </div>
        </header>
        <main className="wrap">{children}</main>
        <footer className="site">
          <div className="wrap cols">
            <div>
              <b>Earnings Call Tone</b>
              <p style={{ margin: "8px 0 0", maxWidth: 560 }}>
                A research portfolio project by Linson. Tone is scored with the Loughran-McDonald finance dictionary and, in the live feed, FinBERT.
                Abnormal returns use a market model against SPY. EPS results are shown only as beat or miss; Q&amp;A
                text is shown as short excerpts. Not investment advice.
              </p>
            </div>
            <div>
              <b>Pages</b>
              <ul>
                <li><Link href="/">Explore a company</Link></li>
                <li><Link href="/latest/">Live feed</Link></li>
                <li><Link href="/walkthrough/">Project walkthrough</Link></li>
                <li><Link href="/results/">Main results</Link></li>
                <li><Link href="/robustness/">Does it hold up?</Link></li>
                <li><Link href="/data/">Data and glossary</Link></li>
                <li><a href="https://github.com/leelinson/earnings-tone">Source code on GitHub</a></li>
              </ul>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
