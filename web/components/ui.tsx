// Shared building blocks so every page uses the same header, stat tile and chart card.
import Link from "next/link";

export function PageHead({ eyebrow, title, lead, crumbs, children }: {
  eyebrow?: string; title: React.ReactNode; lead?: React.ReactNode;
  crumbs?: { href?: string; label: string }[]; children?: React.ReactNode;
}) {
  return (
    <header className="page-head">
      {crumbs && (
        <nav className="crumbs" aria-label="Breadcrumb">
          {crumbs.map((c, i) => (
            <span key={c.label} style={{ display: "contents" }}>
              {i > 0 && <span className="sep">/</span>}
              {c.href ? <Link href={c.href}>{c.label}</Link> : <span>{c.label}</span>}
            </span>
          ))}
        </nav>
      )}
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      {typeof title === "string" ? <h1>{title}</h1> : title}
      {lead && <p className="lead">{lead}</p>}
      {children}
    </header>
  );
}

export function Stat({ label, value, note, tone, accent }: {
  label: string; value: React.ReactNode; note?: React.ReactNode; tone?: string; accent?: boolean;
}) {
  return (
    <div className={`tile${accent ? " accent" : ""}`}>
      <div className="k">{label}</div>
      <div className={`v ${tone ?? ""}`}>{value}</div>
      {note && <div className="s">{note}</div>}
    </div>
  );
}

/** A titled card: heading, a one-line takeaway, then the chart or table. */
export function Section({ id, title, takeaway, children, flush, foot }: {
  id?: string; title: string; takeaway?: React.ReactNode; children: React.ReactNode; flush?: boolean; foot?: React.ReactNode;
}) {
  return (
    <section className="section" id={id} aria-labelledby={id ? `${id}-h` : undefined}>
      <div className="head">
        <h2 id={id ? `${id}-h` : undefined}>{title}</h2>
        {takeaway && <p className="takeaway">{takeaway}</p>}
      </div>
      <div className={`body${flush ? " flush" : ""}`}>{children}</div>
      {foot && <div className="foot note">{foot}</div>}
    </section>
  );
}

export function Takeaway({ children }: { children: React.ReactNode }) {
  return <><b>Takeaway:</b> {children}</>;
}

export function InfoCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="callout" role="note">
      <svg className="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" strokeLinecap="round" />
      </svg>
      <div>{children}</div>
    </div>
  );
}

export function BeatPill({ beat }: { beat: string | null }) {
  if (!beat) return <span className="muted">–</span>;
  const cls = beat === "Beat" ? "beat" : beat === "Miss" ? "miss" : "";
  return <span className={`pill ${cls}`}>{beat}</span>;
}

export function Toc({ items }: { items: [string, string][] }) {
  return (
    <nav className="toc" aria-label="On this page">
      {items.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
    </nav>
  );
}
