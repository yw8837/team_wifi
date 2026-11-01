import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AuthProvider, Protected, useAuth } from "./shared";
import { Welcome, Login, Signup, Reset } from "./auth-pages";
import { Home, Hotdeals, Brands, BrandDetail, CampaignDetail } from "./catalog";
import { Benefits, My, Saved, Reservations, Settings } from "./account";
import {
  Seller,
  SellerCampaigns,
  SellerCoupons,
  SellerReservations,
} from "./seller";
import { Admin } from "./admin";
import { BrandLockup, APP_NAME } from "./brand";
import { IconHome, IconFlame, IconBuildingStore, IconGift, IconUser } from "@tabler/icons-react";
import { BETA_MODE, BETA_NOTICE } from "./beta";
import "./styles.css";
import "./brand-theme.css";
import "./beta.css";
function Layout() {
  const loc = useLocation(),
    { user } = useAuth();
  const [offline, setOffline] = useState(!navigator.onLine);
  useEffect(() => {
    const on = () => setOffline(false),
      off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
    const titles: Record<string, string> = {
      "/": "공동구매",
      "/welcome": "서비스 소개",
      "/login": "로그인",
      "/signup": "회원가입",
      "/reset": "비밀번호 재설정",
      "/hotdeals": "핫딜 모음",
      "/brands": "브랜드관",
      "/benefits": "내 혜택",
      "/my": "마이",
      "/my/saved": "저장한 공구",
      "/my/reservations": "참여 내역",
      "/settings": "계정·설정",
      "/seller": "판매자센터",
      "/seller/campaigns": "공구 관리",
      "/seller/coupons": "쿠폰 발행",
      "/seller/reservations": "내 공구 참여자",
      "/admin": "관리자 심사·데이터 실험실",
    };
    const title =
      titles[loc.pathname] ||
      (loc.pathname.startsWith("/campaigns/")
        ? "공동구매 상세"
        : loc.pathname.startsWith("/brands/")
          ? "브랜드 상세"
          : "모두의육아");
    document.title = title === "모두의육아" ? APP_NAME : `${title} | ${APP_NAME}`;
  }, [loc.pathname]);
  return (
    <>
      <a className="skip-link" href="#main">
        본문으로 이동
      </a>
      <div className="demo-banner">
        {BETA_MODE ? BETA_NOTICE : "모두의육아 · 첫 개발 빌드 · 실제 거래·결제 없음"}
      </div>
      {offline && (
        <div role="alert" className="offline">
          오프라인입니다. 연결 후 다시 시도해 주세요. 입력 내용은 화면에
          유지됩니다.
        </div>
      )}
      <header className="app-header">
        <Link className="wordmark" to="/">
          <BrandLockup />
        </Link>
        <Link className="header-account" to={user ? "/my" : "/login"}>
          {user ? user.nickname : "로그인"}
        </Link>
      </header>
      <main id="main" className={["/welcome", "/login", "/signup", "/reset"].includes(loc.pathname) ? "auth-main" : undefined}>
        <Routes>
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/reset" element={<Reset />} />
          <Route path="/hotdeals" element={<Hotdeals />} />
          <Route path="/brands" element={<Brands />} />
          <Route path="/brands/:id" element={<BrandDetail />} />
          <Route path="/campaigns/:id" element={<CampaignDetail />} />
          <Route path="/benefits" element={<Benefits />} />
          <Route path="/my" element={<My />} />
          <Route
            path="/my/saved"
            element={
              <Protected>
                <Saved />
              </Protected>
            }
          />
          <Route
            path="/my/reservations"
            element={
              <Protected>
                <Reservations />
              </Protected>
            }
          />
          <Route
            path="/settings"
            element={
              <Protected>
                <Settings />
              </Protected>
            }
          />
          <Route
            path="/seller"
            element={
              <Protected>
                <Seller />
              </Protected>
            }
          />
          <Route
            path="/seller/campaigns"
            element={
              <Protected>
                <SellerCampaigns />
              </Protected>
            }
          />
          <Route
            path="/seller/coupons"
            element={
              <Protected>
                <SellerCoupons />
              </Protected>
            }
          />
          <Route
            path="/seller/reservations"
            element={
              <Protected>
                <SellerReservations />
              </Protected>
            }
          />
          <Route
            path="/admin"
            element={
              <Protected admin>
                <Admin />
              </Protected>
            }
          />
          <Route
            path="*"
            element={
              <section className="panel">
                <h1>화면을 찾을 수 없어요</h1>
                <Link to="/">홈으로 돌아가기</Link>
              </section>
            }
          />
        </Routes>
      </main>
      <nav className="bottom-nav" aria-label="주요 메뉴" hidden={["/welcome", "/login", "/signup", "/reset"].includes(loc.pathname)}>
        {[
          ["/", "공동구매", "홈"],
          ["/hotdeals", "핫딜 모음", "딜"],
          ["/brands", "브랜드관", "브"],
          ["/benefits", "내 혜택", "혜"],
          ["/my", "마이", "나"],
        ].map(([to, label, icon]) => (
          <NavLink end={to === "/"} to={to} key={to}>
            <span className="nav-icon" aria-hidden="true">
              {icon === "홈" ? <IconHome size={23} stroke={1.7} /> : icon === "딜" ? <IconFlame size={23} stroke={1.7} /> : icon === "브" ? <IconBuildingStore size={23} stroke={1.7} /> : icon === "혜" ? <IconGift size={23} stroke={1.7} /> : <IconUser size={23} stroke={1.7} />}
            </span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Layout />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
