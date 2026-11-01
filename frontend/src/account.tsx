import { useState } from "react";
import { BETA_MODE, BetaRecoveryCodeSettings, LegalLinks } from "./beta";
import { Link, useNavigate } from "react-router-dom";
import { api, date, money, statusName } from "./api";
import type { Campaign, Coupon, Reservation, Wallet } from "./types";
import { CampaignCard } from "./catalog";
import {
  PageTitle,
  ResourceState,
  useResource,
  useAuth,
  useAction,
  Feedback,
  PasswordField,
} from "./shared";
export function Benefits() {
  const { user, requireLogin, refresh } = useAuth();
  const offers = useResource<{ items: Coupon[] }>("/coupons"),
    wallet = useResource<Wallet>(user ? "/wallet" : null),
    action = useAction();
  return (
    <>
      <PageTitle title="내 혜택">
        <p>쿠폰과 포인트를 한눈에 확인하세요.</p>
      </PageTitle>
      <div className="notice">
        <strong>개발용 혜택 · 실제 매장 사용 불가</strong>
        <p>
          쿠폰 코드는 로컬 시험용입니다. 포인트는 관리자가 확인한 개발용 외부
          주문으로만 적립되며 출금·양도할 수 없습니다.
        </p>
      </div>
      {user ? (
        <>
          <section className="balance">
            <span>보유 포인트</span>
            <strong>{wallet.data?.balance ?? user.points_balance} P</strong>
            <p>포인트는 실험용이며 현금 가치가 없습니다.</p>
          </section>
          <ResourceState {...wallet} retry={wallet.reload} />
          {wallet.data && wallet.data.balance < 0 && (
            <p className="notice">
              환불로 포인트 잔액이 음수입니다. 잔액이 회복되기 전에는 포인트
              교환을 할 수 없습니다.
            </p>
          )}
        </>
      ) : (
        <p className="panel">
          <Link to="/login?returnTo=%2Fbenefits">로그인</Link>하면 보유 혜택을
          확인할 수 있어요.
        </p>
      )}
      <h2>받을 수 있는 쿠폰</h2>
      <Feedback {...action} />
      <ResourceState
        {...offers}
        retry={offers.reload}
        empty={offers.data?.items.length === 0}
      />
      <div className="product-grid">
        {!offers.loading &&
          !offers.error &&
          offers.data?.items.map((c) => (
            <article className="coupon" key={c.id}>
              <p className="brand-name">{c.brand_name}</p>
              <h3>{c.title}</h3>
              <p className="price">{money(c.amount)}</p>
              <p>
                {money(c.min_spend)} 이상 사용 · {c.points_cost} P 필요
              </p>
              <p className="muted">
                {date(c.ends_at)}까지 · 잔여{" "}
                {Math.max(0, c.stock - c.issued_count)}장
              </p>
              <button
                disabled={
                  action.busy ||
                  c.claimed ||
                  c.issued_count >= c.stock ||
                  new Date(c.ends_at) <= new Date()
                }
                onClick={() => {
                  if (requireLogin())
                    void action.run(async () => {
                      await api("/coupons/" + c.id + "/claim", "POST");
                      offers.reload();
                      wallet.reload();
                      await refresh();
                    }, "쿠폰을 받았습니다. 아래 내 쿠폰에서 확인하세요.");
                }}
              >
                {c.claimed
                  ? "이미 받은 쿠폰"
                  : c.issued_count >= c.stock
                    ? "수량 소진"
                    : new Date(c.ends_at) <= new Date()
                      ? "기간 만료"
                      : "쿠폰 받기"}
              </button>
            </article>
          ))}
      </div>
      {user && wallet.data && (
        <>
          <h2>내 쿠폰</h2>
          {!wallet.data.coupons.length && (
            <p className="state">보유한 쿠폰이 없습니다.</p>
          )}
          <div className="product-grid">
            {wallet.data.coupons.map((c) => (
              <article className="coupon" key={c.id}>
                <span className="badge">{statusName[c.status]}</span>
                <p>{c.brand_name}</p>
                <h3>{c.title}</h3>
                <strong>
                  {money(c.amount)} · {money(c.min_spend)} 이상
                </strong>
                <p className="muted">{date(c.ends_at)}까지</p>
                <code>{c.code}</code>
                <p className="hint">
                  개발용 코드 · 실제 판매처에서 사용할 수 없습니다.
                </p>
              </article>
            ))}
          </div>
          <h2>포인트 내역</h2>
          {!wallet.data.ledger.length && (
            <p className="state">아직 적립·사용 내역이 없습니다.</p>
          )}
          <ul className="plain-list">
            {wallet.data.ledger.map((l) => (
              <li key={l.id}>
                <div>
                  {l.reason}
                  <small>{date(l.created_at)}</small>
                </div>
                <strong>
                  {l.delta > 0 ? "+" : ""}
                  {l.delta} P
                </strong>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
export function My() {
  const { user } = useAuth();
  return (
    <>
      <PageTitle title={user ? user.nickname + "님의 육아생활" : "마이"}>
        <p>{user ? user.email : "필요한 순간에 가입하고 함께 준비하세요."}</p>
      </PageTitle>
      {user ? (
        <>
          <nav className="menu-list">
            <Link to="/my/saved">
              저장한 공구 <span>→</span>
            </Link>
            <Link to="/my/reservations">
              참여 내역 <span>→</span>
            </Link>
            <Link to="/benefits">
              쿠폰·포인트 <span>→</span>
            </Link>
            <Link to="/seller">
              판매자센터{" "}
              <small>
                {user.seller_status
                  ? statusName[user.seller_status]
                  : "입점 신청 가능"}
              </small>
            </Link>
            {user.is_admin && (
              <Link to="/admin">
                관리자 심사·운영 <span>→</span>
              </Link>
            )}
            <Link to="/settings">
              계정·설정 <span>→</span>
            </Link>
          </nav>
          <p className="muted">
            이메일 인증: 미확인 · 외부 본인 인증을 완료한 계정이 아닙니다.
          </p>
        </>
      ) : (
        <section className="panel">
          <Link className="button" to="/login?returnTo=%2Fmy">
            로그인
          </Link>
          <p>
            <Link to="/signup">구매자로 시작</Link> ·{" "}
            <Link to="/signup?track=seller">판매자로 입점</Link>
          </p>
        </section>
      )}
      <LegalLinks />
      <Link to="/welcome">서비스 소개 다시 보기</Link>
    </>
  );
}
export function Saved() {
  const result = useResource<{ items: Campaign[] }>("/saved");
  return (
    <>
      <PageTitle title="저장한 공구" />
      <ResourceState
        {...result}
        retry={result.reload}
        empty={result.data?.items.length === 0}
      />
      <div className="product-grid">
        {!result.loading &&
          !result.error &&
          result.data?.items.map((c) => <CampaignCard key={c.id} item={c} />)}
      </div>
    </>
  );
}
export function Reservations() {
  const result = useResource<{ items: Reservation[] }>("/reservations"),
    action = useAction();
  return (
    <>
      <PageTitle title="참여 내역">
        <p>결제 없는 모집 참여 내역입니다. 실제 주문 내역이 아닙니다.</p>
      </PageTitle>
      <Feedback {...action} />
      <ResourceState
        {...result}
        retry={result.reload}
        empty={result.data?.items.length === 0}
      />
      {!result.loading &&
        !result.error &&
        result.data?.items.map((r) => (
          <article className="panel" key={r.id}>
            <span className="badge">{statusName[r.status]}</span>
            <h2>
              <Link to={"/campaigns/" + r.campaign_id}>{r.title}</Link>
            </h2>
            <p>
              참여 수량 {r.quantity} · {r.created_at && date(r.created_at)}
            </p>
            {r.status === "active" && (
              <button
                disabled={action.busy}
                className="secondary"
                onClick={() => {
                  if (window.confirm("이 공구 모집 참여를 철회할까요?"))
                    void action.run(async () => {
                      await api("/reservations/" + r.id + "/withdraw", "POST");
                      result.reload();
                    }, "참여를 철회했습니다.");
                }}
              >
                참여 철회
              </button>
            )}
          </article>
        ))}
    </>
  );
}
export function Settings() {
  const { user, clear } = useAuth(),
    nav = useNavigate(),
    action = useAction();
  const [deleting, setDeleting] = useState(false),
    [password, setPassword] = useState(""),
    [confirmed, setConfirmed] = useState(false);
  return (
    <div className="narrow">
      <PageTitle title="계정·설정" />
      <section className="panel">
        <h2>현재 계정</h2>
        <p>
          {user?.nickname} · {user?.email}
        </p>
        <p className="muted">로그인은 현재 탭·앱 세션에만 유지됩니다.</p>
        <button
          className="secondary"
          disabled={action.busy}
          onClick={() =>
            void action.run(async () => {
              await api("/auth/logout", "POST");
              clear();
              nav("/");
            })
          }
        >
          로그아웃
        </button>
      </section>
      {BETA_MODE && <BetaRecoveryCodeSettings />}
      <section className="panel">
        <h2>신고·차단 안내</h2>
        <p>
          공구 상세에서 콘텐츠를 신고하거나 질문 작성자를 차단할 수 있습니다.
          차단한 작성자의 질문은 로그인한 목록에서 숨겨집니다. 이 빌드에는 차단
          해제 기능이 없습니다.
        </p>
        <Link to="/">공동구매 둘러보기</Link>
      </section>
      <section className="panel">
        <h2>계정 탈퇴</h2>
        <p>
          {BETA_MODE
            ? "계정 정보와 직접 작성한 시험 기록을 삭제하고 모든 로그인과 복구코드를 폐기합니다. 판매 중인 시험 공구도 종료되며 해당 공구의 참여는 모두 철회됩니다."
            : "프로필을 익명화하고 모든 로그인 세션을 폐기합니다. 미완료 모집 참여는 철회됩니다. 진행 중인 판매 공구는 먼저 종료해야 합니다."}
        </p>
        {!deleting ? (
          <button
            className="danger secondary"
            onClick={() => setDeleting(true)}
          >
            회원탈퇴 진행
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!confirmed) return;
              void action.run(async () => {
                await api("/me", "DELETE", { password });
                clear();
                nav("/welcome", { replace: true });
              });
            }}
          >
            <PasswordField
              label="계정 비밀번호 확인"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <label className="check">
              <input
                type="checkbox"
                checked={confirmed}
                required
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>탈퇴 결과를 확인했으며 계정을 탈퇴합니다.</span>
            </label>
            <div className="actions">
              <button className="danger" disabled={action.busy}>
                탈퇴 확정
              </button>
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  setDeleting(false);
                  setPassword("");
                }}
              >
                취소
              </button>
            </div>
          </form>
        )}
      </section>
      <Feedback {...action} />
      <LegalLinks />
      <Link to="/welcome">서비스 소개</Link>
    </div>
  );
}
