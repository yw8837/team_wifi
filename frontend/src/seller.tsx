import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, categories, date, money, statusName } from "./api";
import type { Application, Campaign, Reservation } from "./types";
import {
  Field,
  Feedback,
  PageTitle,
  ResourceState,
  useAction,
  useAuth,
  useResource,
} from "./shared";
const businessFields = [
  ["business_name", "상호"],
  ["business_number", "사업자등록번호 (10자리)"],
  ["representative", "대표자명"],
  ["contact_phone", "연락처"],
  ["contact_email", "사업 이메일"],
  ["business_address", "사업장 주소"],
  ["return_address", "반품 주소"],
  ["commerce_number", "통신판매업 신고번호"],
  ["commerce_exempt_reason", "신고 면제 사유 (해당하는 경우)"],
];
const operatingFields = [
  ["brand_name", "브랜드명"],
  ["brand_description", "브랜드 소개"],
  ["shipping_policy", "배송 정책"],
  ["refund_policy", "교환·환불 정책"],
];
export function Seller() {
  const { user, refresh } = useAuth();
  const result = useResource<Application>("/seller/application"),
    action = useAction();
  const [fields, setFields] = useState<Record<string, string | boolean>>({
      seller_terms_accepted: false,
    }),
    [step, setStep] = useState(1),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (result.data) {
      setFields({
        ...result.data.fields,
        seller_terms_accepted: !!result.data.fields.seller_terms_accepted,
      });
      setDirty(false);
    }
  }, [result.data]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  const status = result.data?.status || user?.seller_status || "draft",
    locked = ["pending", "approved", "suspended"].includes(status);
  useEffect(() => {
    if (result.data?.status && result.data.status !== user?.seller_status)
      void refresh();
  }, [result.data?.status, user?.seller_status, refresh]);
  async function save() {
    await api("/seller/application", "PUT", fields);
    setDirty(false);
    await refresh();
  }
  return (
    <>
      <PageTitle eyebrow="판매자센터" title="판매를 시작하기 전에">
        <p>
          사업 정보와 운영 조건을 저장하고 입점을 신청하세요. 구매자 기능은 심사
          중에도 사용할 수 있습니다.
        </p>
      </PageTitle>
      <Feedback {...action} />
      <ResourceState {...result} retry={result.reload} />
      {!result.loading && !result.error && (
        <>
          <section className="panel">
            <div className="section-heading">
              <h2>입점 상태</h2>
              <span className="badge">{statusName[status]}</span>
            </div>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                result.reload();
                void refresh();
              }}
            >
              심사 상태 새로 확인
            </button>
            {result.data?.review_note && (
              <p className="notice">
                <strong>심사 의견</strong>
                <br />
                {result.data.review_note}
              </p>
            )}
            {status === "approved" ? (
              <>
                <p>
                  승인된 판매자로 공구와 쿠폰을 등록할 수 있습니다. 사업 정보는
                  이 화면에서 변경할 수 없습니다.
                </p>
                <div className="actions">
                  <Link className="button" to="/seller/campaigns">
                    공구 관리
                  </Link>
                  <Link className="button secondary" to="/seller/coupons">
                    쿠폰 발행
                  </Link>
                  <Link className="button secondary" to="/seller/reservations">
                    내 공구 참여자
                  </Link>
                </div>
              </>
            ) : (
              <p>
                {status === "pending"
                  ? "신청 내용을 검토 중입니다. 심사 중에는 내용을 수정하거나 공구를 게시할 수 없습니다."
                  : status === "suspended"
                    ? "판매 기능이 정지되어 있습니다. 심사 의견을 확인하세요."
                    : "임시저장은 일부 항목만 입력해도 가능합니다. 입점 신청 시 필수 정보·사업자번호·정책을 검증합니다."}
              </p>
            )}
            <p className="hint">
              개발용 심사입니다. 실제 본인·사업자 인증이나 제휴 승인이 아닙니다.
              실정보 대신 승인된 테스트 정보를 사용하세요.
            </p>
          </section>
          <div className="stepper" aria-label="입점 신청 단계">
            <button
              className={step === 1 ? "selected" : "secondary"}
              onClick={() => setStep(1)}
            >
              1 사업 정보
            </button>
            <button
              className={step === 2 ? "selected" : "secondary"}
              onClick={() => setStep(2)}
            >
              2 운영 조건
            </button>
          </div>
          <form
            className="narrow"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(
                save,
                "임시저장했습니다. 입점 신청 전까지 수정할 수 있어요.",
              );
            }}
          >
            <fieldset disabled={locked || action.busy}>
              <legend className="sr-only">입점 신청 정보</legend>
              {(step === 1 ? businessFields : operatingFields).map(
                ([key, label]) =>
                  key.includes("policy") || key === "brand_description" ? (
                    <label className="field" key={key}>
                      <span>{label}</span>
                      <textarea
                        name={key}
                        value={String(fields[key] || "")}
                        onChange={(e) => {
                          setFields({ ...fields, [key]: e.target.value });
                          setDirty(true);
                        }}
                      />
                    </label>
                  ) : (
                    <Field
                      key={key}
                      label={label}
                      name={key}
                      type={
                        key === "contact_email"
                          ? "email"
                          : key === "contact_phone"
                            ? "tel"
                            : "text"
                      }
                      autoComplete={
                        key === "contact_email"
                          ? "email"
                          : key === "contact_phone"
                            ? "tel"
                            : key.includes("address")
                              ? "street-address"
                              : "off"
                      }
                      value={String(fields[key] || "")}
                      onChange={(e) => {
                        setFields({ ...fields, [key]: e.target.value });
                        setDirty(true);
                      }}
                    />
                  ),
              )}
              {step === 1 && (
                <p className="hint">
                  통신판매업 신고번호 또는 신고 면제 사유 중 하나가 필요합니다.
                </p>
              )}
              {step === 2 && (
                <label className="check">
                  <input
                    type="checkbox"
                    checked={!!fields.seller_terms_accepted}
                    onChange={(e) => {
                      setFields({
                        ...fields,
                        seller_terms_accepted: e.target.checked,
                      });
                      setDirty(true);
                    }}
                  />
                  <span>
                    [필수] 상품 정보·배송·환불 정책을 정확히 제공하고 판매자
                    운영 조건에 동의합니다.
                  </span>
                </label>
              )}
              <div className="actions">
                <button type="submit">임시저장</button>
                {step === 1 ? (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setStep(2)}
                  >
                    운영 조건 입력 →
                  </button>
                ) : (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setStep(1)}
                  >
                    ← 사업 정보
                  </button>
                )}
              </div>
              {step === 2 && (
                <button
                  type="button"
                  onClick={() =>
                    void action.run(async () => {
                      await save();
                      await api("/seller/application/submit", "POST");
                      result.reload();
                      await refresh();
                    }, "입점 신청을 접수했습니다.")
                  }
                >
                  저장하고 입점 신청
                </button>
              )}
            </fieldset>
            {locked && (
              <p className="hint">
                현재 상태에서는 신청 정보 수정·공구 게시·쿠폰 발행 권한이
                제한됩니다. 승인된 판매자는 위 관리 메뉴를 이용하세요.
              </p>
            )}
            {dirty && (
              <p className="hint">
                저장하지 않은 변경이 있습니다. 이동 전에 임시저장하세요.
              </p>
            )}
          </form>
        </>
      )}
    </>
  );
}
function ApprovedNotice() {
  return (
    <section className="notice">
      <strong>승인된 판매자만 이용할 수 있습니다.</strong>
      <p>입점 상태와 보완 의견을 먼저 확인하세요.</p>
      <Link to="/seller">입점 신청 보기</Link>
    </section>
  );
}
export function SellerCampaigns() {
  const { user } = useAuth();
  const approved = user?.seller_status === "approved",
    result = useResource<{ items: Campaign[] }>(
      approved ? "/seller/campaigns" : null,
    ),
    action = useAction();
  const initial = {
    title: "",
    description: "",
    category: categories[0],
    price: 0,
    shipping_fee: 0,
    unit: "개",
    minimum_quantity: 1,
    stock: 10,
    ends_at: "",
  };
  const [form, setForm] = useState(initial);
  return (
    <>
      <PageTitle title="공구 관리">
        <p>임시저장 → 게시 심사 요청 → 관리자 승인 후 공개됩니다.</p>
      </PageTitle>
      <Feedback {...action} />
      {!approved ? (
        <ApprovedNotice />
      ) : (
        <>
          <section className="panel narrow">
            <h2>새 공구 등록</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action.run(async () => {
                  await api("/seller/campaigns", "POST", {
                    ...form,
                    ends_at: new Date(form.ends_at).toISOString(),
                  });
                  setForm(initial);
                  result.reload();
                }, "공구를 임시저장했습니다. 아래 목록에서 게시 심사를 요청하세요.");
              }}
            >
              <Field
                label="공구명"
                name="title"
                required
                maxLength={200}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
              <label className="field">
                <span>상품 설명</span>
                <textarea
                  required
                  name="description"
                  value={form.description}
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                />
              </label>
              <label className="field">
                <span>육아 카테고리</span>
                <select
                  name="category"
                  value={form.category}
                  onChange={(e) =>
                    setForm({ ...form, category: e.target.value })
                  }
                >
                  {categories.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              {(
                [
                  ["price", "상품 가격 (원)", 1],
                  ["shipping_fee", "배송비 (원)", 0],
                  ["minimum_quantity", "최소 모집 수량", 1],
                  ["stock", "전체 모집 가능 수량", 1],
                ] as const
              ).map(([key, label, min]) => (
                <Field
                  key={key}
                  label={label}
                  name={key}
                  type="number"
                  inputMode="numeric"
                  required
                  min={min}
                  step={1}
                  value={form[key]}
                  onChange={(e) =>
                    setForm({ ...form, [key]: Number(e.target.value) })
                  }
                />
              ))}
              <Field
                label="수량 단위"
                name="unit"
                required
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })}
              />
              <Field
                label="모집 마감 (한국시간)"
                name="ends_at"
                type="datetime-local"
                required
                value={form.ends_at}
                onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
              />
              <button disabled={action.busy}>공구 임시저장</button>
            </form>
          </section>
          <h2>내 공구</h2>
          <ResourceState
            {...result}
            retry={result.reload}
            empty={result.data?.items.length === 0}
          />
          {!result.loading &&
            !result.error &&
            result.data?.items.map((c) => (
              <article className="panel" key={c.id}>
                <span className="badge">{statusName[c.status]}</span>
                <h3>{c.title}</h3>
                <p>
                  {money(c.price)} · {c.reserved_quantity}/{c.stock}
                  {c.unit} · {date(c.ends_at)}
                </p>
                <div className="actions">
                  {["draft", "rejected"].includes(c.status) && (
                    <button
                      disabled={action.busy}
                      onClick={() =>
                        void action.run(async () => {
                          await api(
                            "/seller/campaigns/" + c.id + "/submit",
                            "POST",
                          );
                          result.reload();
                        }, "게시 심사를 요청했습니다.")
                      }
                    >
                      게시 심사 요청
                    </button>
                  )}
                  {["active", "pending", "draft"].includes(c.status) && (
                    <button
                      className="secondary"
                      disabled={action.busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "이 공구를 종료할까요? 신규 참여가 중단됩니다.",
                          )
                        )
                          void action.run(async () => {
                            await api(
                              "/seller/campaigns/" + c.id + "/end",
                              "POST",
                            );
                            result.reload();
                          }, "공구를 종료했습니다.");
                      }}
                    >
                      공구 종료
                    </button>
                  )}
                  {["active", "ended"].includes(c.status) && (
                    <Link to={"/campaigns/" + c.id}>공개 화면</Link>
                  )}
                </div>
              </article>
            ))}
        </>
      )}
      <Link to="/seller">← 판매자센터</Link>
    </>
  );
}
export function SellerCoupons() {
  const { user } = useAuth(),
    action = useAction();
  const [form, setForm] = useState({
    title: "",
    amount: 1000,
    min_spend: 10000,
    stock: 10,
    ends_at: "",
  });
  return (
    <div className="narrow">
      <PageTitle title="브랜드 쿠폰 발행">
        <p>
          자신의 브랜드에만 발행됩니다. 실제 매장에서 사용되지 않는 개발용
          쿠폰입니다.
        </p>
      </PageTitle>
      {user?.seller_status !== "approved" ? (
        <ApprovedNotice />
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              await api("/seller/coupons", "POST", {
                ...form,
                ends_at: new Date(form.ends_at).toISOString(),
                points_cost: 0,
              });
            }, "쿠폰을 발행했습니다. 내 혜택 탭에서 확인할 수 있습니다.");
          }}
        >
          <Field
            label="쿠폰명"
            required
            name="title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          {(
            [
              ["amount", "할인 금액 (원)", 1],
              ["min_spend", "최소 사용금액 (원)", 0],
              ["stock", "발행 수량", 1],
            ] as const
          ).map(([key, label, min]) => (
            <Field
              key={key}
              label={label}
              required
              name={key}
              type="number"
              min={min}
              step={1}
              value={form[key]}
              onChange={(e) =>
                setForm({ ...form, [key]: Number(e.target.value) })
              }
            />
          ))}
          <Field
            label="만료 시각 (한국시간)"
            required
            name="ends_at"
            type="datetime-local"
            value={form.ends_at}
            onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
          />
          <p className="hint">
            판매자 발행 쿠폰은 포인트 차감 없이 받을 수 있습니다.
          </p>
          <Feedback {...action} />
          <button disabled={action.busy}>개발용 쿠폰 발행</button>
        </form>
      )}
      <Link to="/seller">← 판매자센터</Link>
    </div>
  );
}
export function SellerReservations() {
  const { user } = useAuth();
  const result = useResource<{ items: Reservation[] }>(
    user?.seller_status === "approved" ? "/seller/reservations" : null,
  );
  return (
    <>
      <PageTitle title="내 공구 참여자">
        <p>
          구매자의 별칭과 참여 수량만 표시합니다. 결제·배송 고객 명단이
          아닙니다.
        </p>
      </PageTitle>
      {user?.seller_status !== "approved" ? (
        <ApprovedNotice />
      ) : (
        <>
          <ResourceState
            {...result}
            retry={result.reload}
            empty={result.data?.items.length === 0}
          />
          <ul className="plain-list">
            {!result.loading &&
              !result.error &&
              result.data?.items.map((r) => (
                <li key={r.id}>
                  <div>
                    <strong>{r.title}</strong>
                    <small>
                      {r.buyer_alias} · {statusName[r.status]}
                    </small>
                  </div>
                  <span>{r.quantity}개</span>
                </li>
              ))}
          </ul>
        </>
      )}
      <Link to="/seller">← 판매자센터</Link>
    </>
  );
}
