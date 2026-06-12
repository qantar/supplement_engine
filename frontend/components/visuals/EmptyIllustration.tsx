/** Coded empty-state illustration: shield + checkmark with pulse rings.
 *  Pure SVG — theme-aware via CSS variables, crisp at any scale. */
export function EmptyIllustration() {
  return (
    <svg
      className="empty-illus"
      viewBox="0 0 160 160"
      width="132"
      height="132"
      fill="none"
      aria-hidden
    >
      {/* Pulse rings */}
      <circle className="empty-illus-ring" cx="80" cy="80" r="54" />
      <circle
        className="empty-illus-ring empty-illus-ring--2"
        cx="80"
        cy="80"
        r="54"
      />

      {/* Soft disc */}
      <circle cx="80" cy="80" r="46" className="empty-illus-disc" />

      {/* Shield */}
      <path
        className="empty-illus-shield"
        d="M80 46l26 12v16c0 17-11.5 26.5-26 30-14.5-3.5-26-13-26-30V58l26-12z"
      />

      {/* Checkmark — draws itself in */}
      <path className="empty-illus-check" d="M68 80l8 8 16-16" />

      {/* Orbit dots */}
      <circle className="empty-illus-dot" cx="80" cy="22" r="3" />
      <circle
        className="empty-illus-dot empty-illus-dot--2"
        cx="132"
        cy="100"
        r="2.5"
      />
      <circle
        className="empty-illus-dot empty-illus-dot--3"
        cx="32"
        cy="108"
        r="2.5"
      />
    </svg>
  );
}
