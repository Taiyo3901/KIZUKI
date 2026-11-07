/** Shown after a successful upload. Deliberately nothing else for now (no rewards: CLAUDE.md section 1). */
export default function DonePage() {
  return (
    <main className="center done">
      <svg viewBox="0 0 64 64" width="72" height="72" aria-hidden>
        <circle cx="32" cy="32" r="29" fill="none" stroke="var(--aligned)" strokeWidth="4" />
        <path d="M19 33l9 9 17-19" fill="none" stroke="var(--aligned)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <h1>撮影が完了しました</h1>
    </main>
  );
}
