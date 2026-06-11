export function EmptyState() {
  return (
    <div className="empty-state print:hidden" id="empty">
      <svg
        width="52"
        height="52"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
      <p>
        Select a patient to begin. Choose a stored patient ID from the pilot
        cohort, or use the Appendix&nbsp;A inline preset, then press{" "}
        <kbd>Run</kbd>.
      </p>
    </div>
  );
}
