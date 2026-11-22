import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

export const GROUPBUYS_PER_PAGE = 20;
const MAX_PAGE = 500; // The API accepts offsets through 10,000.
const WINDOW_SIZE = 5;

function lastPage(total: number) {
  return Math.max(0, Math.min(MAX_PAGE, Math.ceil(total / GROUPBUYS_PER_PAGE) - 1));
}

export function useGroupbuyPageNavigation(page: number, total: number | undefined, ready: boolean) {
  const [, setParams] = useSearchParams();
  const grid = useRef<HTMLDivElement>(null);
  const requested = useRef<number | null>(null);

  function go(next: number, replace = false) {
    requested.current = next;
    setParams(current => {
      const params = new URLSearchParams(current);
      params.set("page", String(next));
      return params;
    }, { replace });
  }

  useEffect(() => {
    if (!ready) return;
    if (total !== undefined && page > lastPage(total)) {
      go(lastPage(total), true);
    } else if (requested.current === page) {
      requested.current = null;
      grid.current?.focus({ preventScroll: true });
      grid.current?.scrollIntoView({ block: "start" });
    }
  }, [page, total, ready, setParams]);

  return { grid, go };
}

type PageControls = {
  page: number;
  hasMore: boolean;
  total?: number;
  disabled?: boolean;
  change: (page: number) => void;
};

export function GroupbuyPages({ page, total, hasMore, disabled = false, change }: PageControls) {
  const last = total === undefined ? undefined : lastPage(total);
  if (page === 0 && !hasMore && !last) return null;
  const count = last === undefined ? 0 : last + 1;
  const start = Math.max(0, Math.min(page - Math.floor(WINDOW_SIZE / 2), count - WINDOW_SIZE));
  const numbers = Array.from({ length: Math.min(count, WINDOW_SIZE) }, (_, i) => start + i);
  return <nav className={`groupbuy-pagination${numbers.length > 3 ? " many-pages" : ""}`} aria-label="공구 목록 페이지">
    <button type="button" className="secondary" disabled={disabled || page === 0}
      onClick={() => change(page - 1)}>이전</button>
    <span className="groupbuy-page-numbers">{count ? numbers.map(index => <button type="button" key={index} className="secondary"
      aria-label={`${index + 1}페이지`} aria-current={index === page ? "page" : undefined}
      disabled={disabled} onClick={() => { if (index !== page) change(index); }}>{index + 1}</button>)
      : <span aria-current="page">{page + 1}페이지</span>}</span>
    <button type="button" className="secondary" disabled={disabled || !hasMore || page >= MAX_PAGE}
      onClick={() => change(page + 1)}>다음</button>
    {count > WINDOW_SIZE && <label className="groupbuy-page-jump">페이지 이동
      <select value={Math.min(page, count - 1)} disabled={disabled} onChange={e => change(Number(e.target.value))}>
        {Array.from({ length: count }, (_, index) =>
          <option key={index} value={index}>{index + 1} / {count}</option>)}
      </select>
    </label>}
  </nav>;
}
