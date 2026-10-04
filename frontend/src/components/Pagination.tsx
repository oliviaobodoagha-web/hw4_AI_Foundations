// Numbered page links: ‹ Prev 1 2 3 … 9 Next ›
function pageList(current: number, total: number): (number | '…')[] {
  if (total <= 10) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = new Set([1, total, current - 1, current, current + 1])
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b)
  const out: (number | '…')[] = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push('…')
    out.push(p)
  })
  return out
}

export default function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number
  totalPages: number
  onChange: (page: number) => void
}) {
  if (totalPages <= 1) return null
  return (
    <nav className="pagination" aria-label="Product pages">
      <button disabled={page === 1} onClick={() => onChange(page - 1)}>
        ‹ Prev
      </button>
      {pageList(page, totalPages).map((p, i) =>
        p === '…' ? (
          <span key={`gap-${i}`} className="gap">
            …
          </span>
        ) : (
          <button
            key={p}
            className={p === page ? 'active' : ''}
            aria-current={p === page ? 'page' : undefined}
            onClick={() => onChange(p)}
          >
            {p}
          </button>
        ),
      )}
      <button disabled={page === totalPages} onClick={() => onChange(page + 1)}>
        Next ›
      </button>
    </nav>
  )
}
