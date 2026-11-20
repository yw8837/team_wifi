import { useState } from "react";
import { ResearchEvidence } from "./research-summary";
import type { ResearchSummary } from "./research-summary";
import { api, money, statusName } from "./api";
import type { Application, Campaign, Report } from "./types";
import {
  PageTitle,
  ResourceState,
  useResource,
  useAction,
  Feedback,
  Field,
} from "./shared";
export function Admin() {
  const apps = useResource<{ items: Application[] }>("/admin/applications"),
    campaigns = useResource<{ items: Campaign[] }>("/admin/campaigns"),
    reports = useResource<{ items: Report[] }>("/admin/reports"),
    action = useAction();
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [order, setOrder] = useState({
      user_id: "",
      campaign_id: "",
      external_reference: "",
      eligible_amount: 0,
    }),
    [refundId, setRefundId] = useState(""),
    [lastOrder, setLastOrder] = useState("");
  return (
    <>
      <PageTitle
        eyebrow="서버에서 권한을 다시 확인합니다"
        title="관리자 심사·운영"
      >
        <p>
          개발용 심사와 주문 확인 도구입니다. 실제 사업자 인증·결제 확인을
          대신하지 않습니다.
        </p>
      </PageTitle>
      <Feedback {...action} />
      <section>
        <h2>판매자 입점 심사</h2>
        <ResourceState
          {...apps}
          retry={apps.reload}
          empty={apps.data?.items.length === 0}
        />
        {!apps.loading &&
          !apps.error &&
          apps.data?.items.map((a) => (
            <article className="panel" key={a.user_id}>
              <span className="badge">{statusName[a.status]}</span>
              <h3>{a.nickname}</h3>
              <dl className="review-fields">
                {Object.entries(a.fields).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
              </dl>
              {a.review_note && <p>기존 의견: {a.review_note}</p>}
              <Field
                label="심사 의견"
                value={notes[a.user_id!] || ""}
                onChange={(e) =>
                  setNotes({ ...notes, [a.user_id!]: e.target.value })
                }
              />
              <div className="actions">
                {(["approved", "needs_changes", "suspended"] as const).map(
                  (decision) => (
                    <button
                      key={decision}
                      disabled={action.busy}
                      className={decision === "approved" ? "" : "secondary"}
                      onClick={() =>
                        void action.run(async () => {
                          await api(
                            "/admin/applications/" + a.user_id + "/review",
                            "POST",
                            { decision, note: notes[a.user_id!] || "" },
                          );
                          apps.reload();
                        }, "심사 상태를 변경했습니다.")
                      }
                    >
                      {statusName[decision]}
                    </button>
                  ),
                )}
              </div>
            </article>
          ))}
      </section>
      <section>
        <h2>공구 게시 심사</h2>
        <ResourceState
          {...campaigns}
          retry={campaigns.reload}
          empty={campaigns.data?.items.length === 0}
        />
        {!campaigns.loading &&
          !campaigns.error &&
          campaigns.data?.items.map((c) => (
            <article className="panel" key={c.id}>
              <span className="badge">{statusName[c.status]}</span>
              <h3>{c.title}</h3>
              <p>
                {c.seller_name} · {c.brand_name} · {money(c.price)}
              </p>
              <p className="preserve">{c.description}</p>
              <Field
                label="게시 심사 의견"
                value={notes[c.id] || ""}
                onChange={(e) => setNotes({ ...notes, [c.id]: e.target.value })}
              />
              <div className="actions">
                {(["active", "rejected"] as const).map((decision) => (
                  <button
                    key={decision}
                    disabled={action.busy}
                    className={decision === "active" ? "" : "secondary"}
                    onClick={() =>
                      void action.run(async () => {
                        await api(
                          "/admin/campaigns/" + c.id + "/review",
                          "POST",
                          { decision, note: notes[c.id] || "" },
                        );
                        campaigns.reload();
                      }, "공구 심사 결과를 저장했습니다.")
                    }
                  >
                    {decision === "active" ? "승인하고 공개" : "게시 반려"}
                  </button>
                ))}
              </div>
            </article>
          ))}
      </section>
      <section>
        <h2>콘텐츠 신고</h2>
        <ResourceState
          {...reports}
          retry={reports.reload}
          empty={reports.data?.items.length === 0}
        />
        {!reports.loading &&
          !reports.error &&
          reports.data?.items.map((r) => (
            <article className="panel" key={r.id}>
              <h3>
                {r.target_type} · {r.target_id}
              </h3>
              <p>{r.reason}</p>
              <p>처리 상태: {r.status}</p>
              <div className="actions">
                {(["hide", "dismiss"] as const).map((mode) => (
                  <button
                    key={mode}
                    disabled={action.busy || r.status !== "pending"}
                    className="secondary"
                    onClick={() =>
                      void action.run(async () => {
                        await api(
                          "/admin/reports/" + r.id + "/resolve",
                          "POST",
                          { action: mode },
                        );
                        reports.reload();
                      }, "신고를 처리했습니다.")
                    }
                  >
                    {mode === "hide" ? "대상 숨기기" : "신고 기각"}
                  </button>
                ))}
              </div>
            </article>
          ))}
      </section>
      <section className="panel narrow">
        <h2>확인된 개발용 외부 주문 기록</h2>
        <p className="notice">
          외부 결제 증빙은 자동 확인되지 않습니다. 관리자가 확인한 시험 주문만
          입력하세요. 적립은 대상금액의 1%이며 중복 참조는 거부됩니다.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              const result = await api<{ id: string }>(
                "/admin/orders",
                "POST",
                { ...order, status: "confirmed" },
              );
              setLastOrder(result.id);
            }, "개발용 주문을 기록했습니다.");
          }}
        >
          <Field
            label="구매자 ID"
            required
            value={order.user_id}
            onChange={(e) => setOrder({ ...order, user_id: e.target.value })}
          />
          <Field
            label="공구 ID"
            required
            value={order.campaign_id}
            onChange={(e) =>
              setOrder({ ...order, campaign_id: e.target.value })
            }
          />
          <Field
            label="외부 주문 참조 (고유값)"
            required
            value={order.external_reference}
            onChange={(e) =>
              setOrder({ ...order, external_reference: e.target.value })
            }
          />
          <Field
            label="적립 대상금액 (원)"
            required
            type="number"
            min={0}
            step={1}
            value={order.eligible_amount}
            onChange={(e) =>
              setOrder({ ...order, eligible_amount: Number(e.target.value) })
            }
          />
          <button disabled={action.busy}>확인 주문 기록</button>
        </form>
        {lastOrder && (
          <p role="status">
            기록된 주문 ID: <code>{lastOrder}</code>
          </p>
        )}
        <h3>기록 주문 환불</h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (
              window.confirm(
                "주문을 환불 처리하고 원 적립 포인트를 회수할까요?",
              )
            )
              void action.run(async () => {
                await api(
                  "/admin/orders/" + encodeURIComponent(refundId) + "/refund",
                  "POST",
                );
              }, "환불과 포인트 회수를 처리했습니다.");
          }}
        >
          <Field
            label="환불할 주문 ID"
            required
            value={refundId}
            onChange={(e) => setRefundId(e.target.value)}
          />
          <button className="secondary" disabled={action.busy}>
            개발용 주문 환불
          </button>
        </form>
      </section>
      <Research />
    </>
  );
}
function Research() {
  const result = useResource<ResearchSummary>("/research/summary");
  const action = useAction();
  const [features, setFeatures] = useState({
    Administrative: 0,
    Administrative_Duration: 0,
    Informational: 0,
    Informational_Duration: 0,
    ProductRelated: 0,
    ProductRelated_Duration: 0,
    SpecialDay: 0,
    Weekend: 0,
  });
  const [prediction, setPrediction] = useState<Record<string, unknown> | null>(
    null,
  );
  const labels: Record<string, string> = {
    Administrative: "관리 페이지 방문 수",
    Administrative_Duration: "관리 페이지 체류 시간",
    Informational: "정보 페이지 방문 수",
    Informational_Duration: "정보 페이지 체류 시간",
    ProductRelated: "상품 페이지 방문 수",
    ProductRelated_Duration: "상품 페이지 체류 시간",
    SpecialDay: "특별일 근접도 (0~1)",
    Weekend: "주말 여부 (0 또는 1)",
  };
  return (
    <section className="panel">
      <h2>데이터 실험실</h2>
      <p>
        관리자 전용 연구 요약입니다. 과거 데이터의 실험 결과는 육아상품에 대한
        추천 근거 또는 실제 구매 예측으로 표시하지 않습니다.
      </p>
      <ResourceState {...result} retry={result.reload} />
      {!result.loading && !result.error && result.data && (
        <ResearchEvidence summary={result.data} />
      )}
      <h3>완료 세션 기반 구매 의도 실험</h3>
      <p className="notice">
        과거 리테일 완료 세션으로 학습한 로컬 실험입니다. 실제 육아 서비스의
        이탈 성능·실시간 예측 성능을 의미하지 않습니다. PageValues는 입력하지
        않습니다.
      </p>
      <form
        className="narrow"
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(async () => {
            setPrediction(
              await api<Record<string, unknown>>(
                "/research/purchase-intent",
                "POST",
                features,
              ),
            );
          }, "실험 응답을 받았습니다. 적용 한계와 함께 확인하세요.");
        }}
      >
        {(Object.keys(features) as (keyof typeof features)[]).map((key) => (
          <Field
            key={key}
            label={labels[key]}
            name={key}
            type="number"
            required
            min={0}
            max={key === "SpecialDay" || key === "Weekend" ? 1 : undefined}
            step={
              key === "Weekend" ||
              (!key.includes("Duration") && key !== "SpecialDay")
                ? 1
                : "any"
            }
            value={features[key]}
            onChange={(e) =>
              setFeatures({ ...features, [key]: Number(e.target.value) })
            }
          />
        ))}
        <Feedback {...action} />
        <button disabled={action.busy}>로컬 모델 실험 실행</button>
      </form>
      {prediction && (
        <pre className="research-json" aria-label="실험 응답">
          {JSON.stringify(prediction, null, 2)}
        </pre>
      )}
    </section>
  );
}
