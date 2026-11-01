import { useState } from "react";
import { CategoryIcon } from "./brand";
import { IconArrowRight, IconBabyBottle, IconSearch } from "@tabler/icons-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  api,
  categories,
  date,
  money,
  safeExternalUrl,
  statusName,
} from "./api";
import {
  PageTitle,
  ResourceState,
  useResource,
  Field,
  Feedback,
  useAction,
  useAuth,
} from "./shared";
import type { Brand, Campaign, Hotdeal, Question } from "./types";
import {
  recruitmentLabel,
  recruitmentStatus,
  remainingQuantity,
} from "./recruitment";
export function CampaignCard({ item }: { item: Campaign }) {
  return (
    <article className="product">
      <Link className="product-link" to={"/campaigns/" + item.id}>
        <div className="category-art" aria-hidden="true"><CategoryIcon category={item.category} size={60} /><span>상품 이미지 준비 중</span></div>
        <div className="product-label">
          <span>{item.category}</span>
          <span className="badge">
            {statusName[item.status] || item.status}
          </span>
        </div>
        <p className="brand-name">{item.brand_name}</p>
        <h2>{item.title}</h2>
        <p className="price">
          {money(item.price)} <small>/ {item.unit}</small>
        </p>
        <p className="muted">
          배송비 {money(item.shipping_fee)}
          <br />
          현재 예약 {item.reserved_quantity}단위 / 최소 {item.minimum_quantity}단위
          <br />1단위 = {item.unit}
        </p>
        <p className="recruitment-label">{recruitmentLabel(item)}</p>
        <div
          className="meter"
          aria-label={`현재 예약 수량 ${item.reserved_quantity}, 최소 모집수량 ${item.minimum_quantity}. 독립 참여 인원 수가 아닙니다.`}
        >
          <span
            style={{
              width:
                Math.min(
                  100,
                  (item.reserved_quantity /
                    Math.max(1, item.minimum_quantity)) *
                    100,
                ) + "%",
            }}
          />
        </div>
        <p className="muted">{date(item.ends_at)}까지</p>
      </Link>
    </article>
  );
}
function Filters({ hotdeal = false }: { hotdeal?: boolean }) {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  return (
    <>
      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          const p = new URLSearchParams(params);
          if (q) p.set("q", q);
          else p.delete("q");
          setParams(p);
        }}
      >
        <label className="sr-only" htmlFor="search">
          {hotdeal ? "핫딜" : "공동구매"} 검색
        </label>
        <input
          id="search"
          type="search"
          name="q"
          placeholder="필요한 육아템을 검색하세요"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button aria-label="검색"><IconSearch size={22} aria-hidden="true" /></button>
      </form>
      <div className="categories" aria-label="카테고리">
        {["", ...categories].map((c) => (
          <button
            key={c}
            aria-pressed={(params.get("category") || "") === c}
            className={
              (params.get("category") || "") === c ? "chip selected" : "chip"
            }
            onClick={() => {
              const p = new URLSearchParams(params);
              if (c) p.set("category", c);
              else p.delete("category");
              setParams(p);
            }}
          >
            {c || "전체"}
          </button>
        ))}
      </div>
    </>
  );
}
export function Home() {
  const [params] = useSearchParams();
  const result = useResource<{ items: Campaign[] }>("/campaigns?" + params.toString());
  return (
    <div className="home-catalog">
      <h1 className="sr-only">우리에게 필요한 공동구매</h1>
      <Filters />
      {!params.get("q") && !params.get("category") && (
        <section className="home-feature" aria-label="수유용품 공동구매 안내">
          <div>
            <p>매일 쓰는 육아용품</p>
            <h2>함께 고르고<br />가볍게 준비해요.</h2>
            <Link to={"/?category=" + encodeURIComponent("수유·이유식")}>수유·이유식 살펴보기 <IconArrowRight size={17} aria-hidden="true" /></Link>
          </div>
          <IconBabyBottle className="feature-illustration" size={112} stroke={1.1} aria-hidden="true" />
        </section>
      )}
      <p className="catalog-note">참여 전 가격·배송·환불 조건을 확인해 주세요.</p>
      <div className="section-heading">
        <h2>지금 모집 중</h2>
        <span className="muted">결제 없는 모집 단계</span>
      </div>
      <ResourceState {...result} retry={result.reload} empty={result.data?.items.length === 0} />
      <div className="product-grid">
        {!result.loading && !result.error && result.data?.items.map((item) => <CampaignCard key={item.id} item={item} />)}
      </div>
    </div>
  );
}
export function Hotdeals() {
  const [params] = useSearchParams();
  const result = useResource<{ items: Hotdeal[] }>(
    "/hotdeals?" + params.toString(),
  );
  return (
    <>
      <PageTitle eyebrow="육아만 골라 모은" title="핫딜 모음">
        <p>
          공동구매와 별도로 모은 외부 정보입니다. 가격과 재고는 원 판매처에서
          확인하세요.
        </p>
      </PageTitle>
      <Filters hotdeal />
      <ResourceState
        {...result}
        retry={result.reload}
        empty={result.data?.items.length === 0}
      />
      <div className="product-grid">
        {!result.loading &&
          !result.error &&
          result.data?.items.map((item) => {
            const url = safeExternalUrl(item.source_url);
            return (
              <article className="product" key={item.id}>
                <div className="product-label">
                  <span>{item.category}</span>
                  <span className="badge">{statusName[item.status]}</span>
                </div>
                <p className="brand-name">
                  {item.source_name} · {item.seller_name}
                </p>
                <h2>{item.title}</h2>
                <p className="price">{money(item.price)}</p>
                <p>배송비 {money(item.shipping_fee)}</p>
                <p className="muted">
                  정보 확인 {date(item.verified_at)}
                  <br />
                  종료 {date(item.ends_at)}
                </p>
                {url && item.status === "active" ? (
                  <a
                    className="button secondary"
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    판매처에서 확인 ↗
                  </a>
                ) : (
                  <>
                    <button disabled className="secondary">
                      판매처 이동 불가
                    </button>
                    <p className="hint">
                      {!url
                        ? "실제 구매 링크가 없는 개발용 정보입니다."
                        : "종료되거나 재확인이 필요한 정보입니다."}
                    </p>
                  </>
                )}
              </article>
            );
          })}
      </div>
    </>
  );
}
export function Brands() {
  const result = useResource<{ items: Brand[] }>("/brands");
  return (
    <>
      <PageTitle title="브랜드관">
        <p>브랜드별 소개와 모집 중인 공구를 확인하세요.</p>
      </PageTitle>
      <ResourceState
        {...result}
        retry={result.reload}
        empty={result.data?.items.length === 0}
      />
      <div className="brand-grid">
        {!result.loading &&
          !result.error &&
          result.data?.items.map((b) => (
            <Link className="brand-card" key={b.id} to={"/brands/" + b.id}>
              <span className="brand-monogram">{b.logo_text}</span>
              <div>
                <h2>{b.name}</h2>
                <p>{b.description}</p>
              </div>
              <span aria-hidden="true">→</span>
            </Link>
          ))}
      </div>
    </>
  );
}
export function BrandDetail() {
  const { id } = useParams();
  const result = useResource<{ brand: Brand; campaigns: Campaign[] }>(
    "/brands/" + id,
  );
  return (
    <>
      <Link to="/brands">← 브랜드관</Link>
      <ResourceState {...result} retry={result.reload} />
      {result.data && !result.loading && !result.error && (
        <>
          <PageTitle title={result.data.brand.name}>
            <p>{result.data.brand.description}</p>
          </PageTitle>
          <div className="product-grid">
            {result.data.campaigns.map((item) => (
              <CampaignCard key={item.id} item={item} />
            ))}
          </div>
          {!result.data.campaigns.length && (
            <p className="state">아직 공개된 공동구매가 없습니다.</p>
          )}
        </>
      )}
    </>
  );
}
export function CampaignDetail() {
  const { id } = useParams();
  const result = useResource<Campaign>("/campaigns/" + id),
    questions = useResource<{ items: Question[] }>(
      "/campaigns/" + id + "/questions",
    );
  const { user, requireLogin } = useAuth(),
    action = useAction();
  const [quantity, setQuantity] = useState(() => {
      const n = Number(sessionStorage.getItem("moduyuga.quantity." + id) || 1);
      return Number.isInteger(n) && n > 0 ? n : 1;
    }),
    [confirmed, setConfirmed] = useState(false),
    [body, setBody] = useState(""),
    [report, setReport] = useState<{ type: string; id: string } | null>(null),
    [reason, setReason] = useState("");
  const c = result.data;
  async function sendReport() {
    if (!requireLogin() || !report) return;
    await action.run(async () => {
      await api("/reports", "POST", {
        target_type: report!.type,
        target_id: report!.id,
        reason,
      });
      setReport(null);
      setReason("");
    }, "신고를 접수했습니다. 운영 검토 후 처리됩니다.");
  }
  return (
    <>
      <Link to="/">← 공동구매 목록</Link>
      <ResourceState {...result} retry={result.reload} />
      {c && !result.loading && !result.error && (
        <>
          <PageTitle eyebrow={c.brand_name} title={c.title}>
            <p>
              {c.category} ·{" "}
              <span className="badge">{statusName[c.status]}</span>
            </p>
          </PageTitle>
          <div className="detail-columns">
            <section>
              <p className="price">
                {money(c.price)} <small>/ {c.unit}</small>
              </p>
              <dl className="facts">
                <div>
                  <dt>배송비</dt>
                  <dd>{money(c.shipping_fee)}</dd>
                </div>
                <div>
                  <dt>현재 예약 수량</dt>
                  <dd>
                    {c.reserved_quantity}단위
                  </dd>
                </div>
                <div>
                  <dt>최소 모집수량</dt>
                  <dd>
                    {c.minimum_quantity}단위
                  </dd>
                </div>
                <div>
                  <dt>최소 기준까지 부족 수량</dt>
                  <dd>
                    {Math.max(0, c.minimum_quantity - c.reserved_quantity)}단위
                  </dd>
                </div>
                <div>
                  <dt>모집 가능 수량</dt>
                  <dd>
                    {remainingQuantity(c)}단위
                  </dd>
                </div>
                <div>
                  <dt>마감</dt>
                  <dd>{date(c.ends_at)} (한국시간)</dd>
                </div>
              </dl>
              <div className="notice">
                <strong>{recruitmentLabel(c)}</strong>
                <p>
                  현재 예약 수량 기준입니다. 수량의 합이며 독립 참여 인원 수가
                  아닙니다. 참여 철회에 따라 현황이 달라질 수 있습니다.
                </p>
                <p>
                  {recruitmentStatus(c) === "closed_shortfall"
                    ? "모집은 종료되었고 현재 예약 수량이 최소 모집수량에 미달합니다. "
                    : ""}
                  실물 주문·결제·배송·할인이 확정된 상태를 의미하지 않습니다.
                </p>
              </div>
              <h2>상품 안내</h2>
              <p className="preserve">{c.description}</p>
              <section className="policy">
                <h2>판매·배송 정보</h2>
                <p>판매자: {c.seller_name}</p>
                <h3>배송 조건</h3>
                <p className="preserve">{c.shipping_policy}</p>
                <h3>교환·환불 조건</h3>
                <p className="preserve">{c.refund_policy}</p>
              </section>
              <button
                className="text-button"
                onClick={() => {
                  if (requireLogin()) setReport({ type: "campaign", id: c.id });
                }}
              >
                이 공구 신고하기
              </button>
            </section>
            <aside className="panel purchase-panel">
              <h2>공동구매 참여</h2>
              <p className="notice">
                참여는 <strong>결제 없는 모집 의사 표시</strong>입니다.
                주문·결제·배송 확정이 아닙니다.
              </p>
              <Field
                label="참여 수량"
                type="number"
                min={1}
                max={Math.max(1, Math.min(20, remainingQuantity(c)))}
                step={1}
                value={quantity}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  setQuantity(n);
                  sessionStorage.setItem("moduyuga.quantity." + id, String(n));
                  setConfirmed(false);
                }}
              />
              <p>
                예상 상품금액 <strong>{money(c.price * quantity)}</strong>
                <br />
                배송비 포함{" "}
                <strong>{money(c.price * quantity + c.shipping_fee)}</strong>
              </p>
              <label className="check">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                <span>
                  결제 없는 모집 참여이며 배송·환불 조건을 확인했습니다.
                </span>
              </label>
              <button
                disabled={action.busy || c.status !== "active"}
                onClick={() => {
                  if (!requireLogin()) return;
                  if (
                    !Number.isInteger(quantity) ||
                    quantity < 1 ||
                    quantity > Math.min(20, remainingQuantity(c))
                  ) {
                    action.setError(
                      "현재 모집 가능한 수량 안에서 1개 이상, 최대 20개의 정수를 입력해 주세요.",
                    );
                    return;
                  }
                  if (!confirmed) {
                    action.setError(
                      "참여 안내와 배송·환불 조건 확인에 동의해 주세요.",
                    );
                    return;
                  }
                  void action.run(async () => {
                    await api("/campaigns/" + id + "/reservations", "POST", {
                      quantity,
                      revision: c.revision,
                    });
                    setConfirmed(false);
                    result.reload();
                  }, "참여를 등록했습니다. 마이의 참여 내역에서 확인하거나 철회할 수 있어요.");
                }}
              >
                {action.busy
                  ? "처리 중…"
                  : c.status === "active"
                    ? "모집 참여하기"
                    : "모집이 종료되었습니다"}
              </button>
              <button
                className="secondary"
                disabled={action.busy}
                onClick={() => {
                  if (requireLogin())
                    void action.run(
                      async () => {
                        await api("/saved/" + id, c.saved ? "DELETE" : "PUT");
                        result.reload();
                      },
                      c.saved ? "저장을 해제했습니다." : "저장했습니다.",
                    );
                }}
              >
                {c.saved ? "저장 해제" : "관심 공구 저장"}
              </button>
              <Link to="/my/reservations">내 참여 내역 보기</Link>
            </aside>
          </div>
          <Feedback {...action} />
          <section className="questions">
            <h2>궁금한 점을 남겨주세요</h2>
            <p className="muted">주소·전화번호 등 개인정보는 쓰지 마세요.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (requireLogin())
                  void action.run(async () => {
                    await api("/campaigns/" + id + "/questions", "POST", {
                      body,
                    });
                    setBody("");
                    questions.reload();
                  }, "질문을 등록했습니다.");
              }}
            >
              <label className="field">
                <span>질문 내용</span>
                <textarea
                  required
                  minLength={2}
                  maxLength={2000}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                />
              </label>
              <button disabled={action.busy}>질문 등록</button>
            </form>
            <ResourceState
              {...questions}
              retry={questions.reload}
              empty={questions.data?.items.length === 0}
            />
            {!questions.loading &&
              !questions.error &&
              questions.data?.items.map((q) => (
                <article className="question" key={q.id}>
                  <p>
                    <strong>{q.author_name}</strong>{" "}
                    <small>{date(q.created_at)}</small>
                  </p>
                  <p className="preserve">{q.body}</p>
                  <div className="link-row">
                    <button
                      className="text-button"
                      onClick={() => {
                        if (requireLogin())
                          setReport({ type: "question", id: q.id });
                      }}
                    >
                      신고
                    </button>
                    {q.author_id !== user?.id && (
                      <button
                        className="text-button"
                        disabled={action.busy}
                        onClick={() => {
                          if (
                            requireLogin() &&
                            window.confirm(
                              "이 작성자를 차단할까요? 앞으로 질문 목록에서 숨겨집니다.",
                            )
                          )
                            void action.run(async () => {
                              await api("/blocks/" + q.author_id, "POST");
                              questions.reload();
                            }, "차단했습니다. 이 작성자의 질문을 숨깁니다.");
                        }}
                      >
                        작성자 차단
                      </button>
                    )}
                  </div>
                </article>
              ))}
          </section>
          {report && (
            <section className="panel" aria-label="신고 양식">
              <h2>신고 사유</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void sendReport();
                }}
              >
                <label className="field">
                  <span>검토할 내용을 구체적으로 알려주세요</span>
                  <textarea
                    required
                    minLength={2}
                    maxLength={1000}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <div className="actions">
                  <button disabled={action.busy}>신고 접수</button>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => setReport(null)}
                  >
                    취소
                  </button>
                </div>
              </form>
            </section>
          )}
        </>
      )}
    </>
  );
}
