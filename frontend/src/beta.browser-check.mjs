// Run after a beta build: node src/beta.browser-check.mjs [preview URL].
// All API requests below are intercepted fixtures; this is a browser contract check.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const base = process.argv[2] || "http://127.0.0.1:4181";
const browser = await chromium.launch({ headless: true, channel: process.env.BETA_BROWSER_CHANNEL || "msedge" });
const page = await browser.newPage({ viewport: { width: 320, height: 740 } });
page.setDefaultTimeout(10_000);
const requests = [];
const user = { id: "buyer-fixture", email: "beta@example.test", nickname: "베타테스터", is_admin: false, seller_status: null };
const campaign = { id: "fixture", title: "베타 시험 공구", brand_name: "가상 브랜드", seller_name: "가상 판매자",
  category: "육아생활", status: "active", price: 1000, shipping_fee: 0, unit: "개", reserved_quantity: 0,
  minimum_quantity: 10, stock: 100, ends_at: "2099-01-01T00:00:00Z", description: "시험용 상품", shipping_policy: "실배송 없음",
  refund_policy: "실결제 없음", revision: 1, saved: false };
let application = { status: "draft", fields: {}, review_note: null };
let expireSession = false;
await page.route("https://api.example.test/api/**", async (route) => {
  const req = route.request(), path = new URL(req.url()).pathname.replace(/^\/api/, "");
  requests.push({ path, method: req.method(), body: req.postDataJSON() });
  if (path === "/me" && expireSession) {
    await route.fulfill({ status: 401, json: { detail: "세션 만료" }, headers: { "Access-Control-Allow-Origin": "*" } });
    return;
  }
  let body;
  if (path === "/config") body = { legal: {} };
  else if (path === "/auth/register") body = { access_token: "fixture-session", user, recovery_code: "TEST-ONLY-" + "RECOVERY".repeat(8) };
  else if (path === "/auth/recover") body = { message: "재설정 완료", recovery_code: "TEST-ONLY-ROTATED-RECOVERY" };
  else if (path === "/auth/login") body = { access_token: "fixture-session", user };
  else if (path === "/me") body = user;
  else if (path === "/campaigns/fixture") body = campaign;
  else if (path === "/campaigns/fixture/questions") body = { items: [{ id: "question-fixture", author_id: "other-user", author_name: "다른 작성자", body: "시험 질문", created_at: "2026-11-01T00:00:00Z" }] };
  else if (path === "/reports") body = { message: "접수" };
  else if (path === "/seller/application/beta") { application.fields = req.postDataJSON(); body = application; }
  else if (path === "/seller/application/submit") { application.status = "pending"; body = application; }
  else if (path === "/seller/application") body = application;
  else throw new Error(`Unmocked request: ${req.method()} ${path}`);
  await route.fulfill({ json: body, headers: { "Access-Control-Allow-Origin": "*" } });
});
try {
  await page.goto(base + "/campaigns/fixture");
  await page.getByRole("heading", { name: "베타 시험 공구", exact: true }).waitFor();
  await page.getByLabel("참여 수량").fill("3");
  await page.getByRole("button", { name: "모집 참여하기", exact: true }).click();
  await page.waitForURL(/\/login\?returnTo=/);
  await page.getByRole("link", { name: "회원가입", exact: true }).click();
  await page.getByRole("button", { name: "판매자", exact: true }).click();
  await page.locator('input[name="email"]').fill(user.email);
  await page.locator('input[name="password"]').fill("Fixture-only-password");
  await page.locator('input[name="nickname"]').fill(user.nickname);
  await page.locator('input[name="invite_code"]').fill("TEST-INVITE");
  await page.getByLabel("[필수] 만 18세 이상입니다.", { exact: true }).check();
  await page.getByLabel("[필수] 이용약관에 동의합니다", { exact: true }).check();
  await page.getByLabel("[필수] 개인정보 처리에 동의합니다", { exact: true }).check();
  assert.equal(await page.getByText("[선택] 마케팅 정보 수신에 동의합니다", { exact: true }).count(), 0);
  assert.equal(await page.getByRole("navigation", { name: "이용 안내" }).getByRole("link").count(), 4);
  await page.getByRole("button", { name: "계정 만들고 입점 신청", exact: true }).click();
  await page.getByRole("heading", { name: "복구코드를 안전하게 보관해 주세요", exact: true }).waitFor();
  assert.match(page.url(), /\/signup/);
  assert.equal(await page.getByRole("button", { name: "확인하고 계속", exact: true }).isDisabled(), true);
  assert.equal(await page.evaluate(() => sessionStorage.getItem("moduyuga.session")), null);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, "320px horizontal overflow");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "확인하고 계속", exact: true }).click();
  await page.waitForURL(base + "/campaigns/fixture");
  assert.equal(await page.getByLabel("참여 수량").inputValue(), "3");
  assert.equal(requests.filter((r) => r.path.endsWith("/reservations") && r.method === "POST").length, 0);
  const registration = requests.find((r) => r.path === "/auth/register");
  assert.equal(registration.body.adult_confirmed, true);
  assert.equal(registration.body.marketing_opt_in, false);
  assert.equal(registration.body.invite_code, "TEST-INVITE");

  await page.getByRole("button", { name: "작성자 신고", exact: true }).click();
  await page.getByLabel("검토할 내용을 구체적으로 알려주세요").fill("작성자 신고 시험");
  await page.getByRole("button", { name: "신고 접수", exact: true }).click();
  await page.getByText("신고를 접수했습니다. 운영 검토 후 처리됩니다.", { exact: true }).waitFor();
  assert.deepEqual(requests.find((r) => r.path === "/reports").body, { target_type: "user", target_id: "other-user", reason: "작성자 신고 시험" });

  await page.goto(base + "/seller");
  await page.locator('input[name="brand_name"]').fill("시험 브랜드");
  assert.equal(await page.locator('input[name="business_number"], input[name="contact_phone"], input[name*="address"]').count(), 0);
  await page.getByLabel("가상 브랜드 소개", { exact: true }).fill("베타 체험용 가상 브랜드입니다.");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "저장하고 베타 입점 신청", exact: true }).click();
  await page.getByText("베타 입점 신청을 접수했습니다.", { exact: true }).waitFor();
  assert.deepEqual(Object.keys(requests.find((r) => r.path === "/seller/application/beta").body).sort(), ["brand_description", "brand_name", "seller_terms_accepted"]);

  await page.goto(base + "/reset");
  await page.locator('input[name="email"]').fill(user.email);
  await page.locator('input[name="recovery_code"]').fill("TEST-ONLY-OLD-RECOVERY");
  await page.locator('input[name="new-password"]').fill("Fixture-only-new-password");
  await page.getByRole("button", { name: "비밀번호 재설정", exact: true }).click();
  await page.getByText("TEST-ONLY-ROTATED-RECOVERY", { exact: true }).waitFor();
  assert.match(page.url(), /\/reset$/);
  assert.equal(await page.getByRole("button", { name: "새 코드 확인 후 로그인", exact: true }).isDisabled(), true);
  const storage = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
  assert.doesNotMatch(storage, /RECOVERY|password|TEST-INVITE/i);
  assert.equal(await page.evaluate(() => sessionStorage.getItem("moduyuga.session")), null);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "새 코드 확인 후 로그인", exact: true }).click();
  await page.waitForURL(base + "/login");
  expireSession = true;
  await page.evaluate(() => sessionStorage.setItem("moduyuga.session", "expired-fixture-session"));
  await page.goto(base + "/campaigns/fixture");
  await page.getByRole("heading", { name: "베타 시험 공구", exact: true }).waitFor();
  await page.getByRole("link", { name: "로그인", exact: true }).waitFor();
  assert.equal(page.url(), base + "/campaigns/fixture");
  assert.equal(await page.getByLabel("참여 수량").inputValue(), "3");
  assert.equal(await page.evaluate(() => sessionStorage.getItem("moduyuga.session")), null);
  console.log("PASS: 320px guest browse, signup acknowledgment, original quantity, no auto participation, user report, fake seller form, rotated recovery acknowledgment, no secret storage and guest browsing after session expiry (mocked API).");
} finally {
  await browser.close();
}
