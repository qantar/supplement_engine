export function EmptyState() {
  return (
    <div className="empty-state print:hidden" id="empty">
      <svg
        width="58"
        height="58"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        aria-hidden
      >
        <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
      <p>
        Results appear here. Select a pilot patient or use the Appendix A inline
        preset, then press <kbd>Run</kbd>.
      </p>
    </div>
  );
}
