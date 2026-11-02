"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

const LINKS: [string, string][] = [
  ["/", "Explore a company"],
  ["/walkthrough/", "Project walkthrough"],
  ["/results/", "Main results"],
  ["/robustness/", "Does it hold up?"],
  ["/data/", "Data and glossary"],
];

export default function Nav() {
  const path = usePathname() ?? "/";
  const p = path.endsWith("/") ? path : `${path}/`;
  const active = (href: string) => (href === "/" ? p === "/" || p.startsWith("/company/") : p.startsWith(href));
  const ref = useRef<HTMLElement>(null);
  // on phones the links scroll sideways: keep the current page's link in view
  useEffect(() => {
    const nav = ref.current, on = nav?.querySelector<HTMLElement>('[aria-current="page"]');
    if (nav && on && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = on.offsetLeft - (nav.clientWidth - on.offsetWidth) / 2;
  }, [p]);
  return (
    <nav className="primary" aria-label="Main" ref={ref}>
      {LINKS.map(([href, label]) => (
        <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}>{label}</Link>
      ))}
    </nav>
  );
}
