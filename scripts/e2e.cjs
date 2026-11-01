// Real browser + real API. Creates only local example accounts; never touches external services.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const base = process.env.WEB_URL || 'http://127.0.0.1:5173';
const apiBase = process.env.API_URL || 'http://127.0.0.1:8000/api';
if (!['localhost','127.0.0.1'].includes(new URL(base).hostname) || !['localhost','127.0.0.1'].includes(new URL(apiBase).hostname)) throw new Error('Local test endpoints required');
const out = path.join(root, 'artifacts', 'e2e');
fs.mkdirSync(out, { recursive: true });
const accounts = JSON.parse(fs.readFileSync(path.join(root,'backend/runtime/demo-accounts.json'),'utf8'));
const run = Date.now().toString();
const password = 'Local-E2E-Only-123!';
const steps = [];
let cspEvidence = null;
async function step(name, fn) { await fn(); steps.push({name, result:'pass'}); console.log('PASS '+name); }
async function signup(page, nickname) {
  await page.locator('[name=email]').fill(`qa-${nickname === '구매검증' ? 'buyer' : 'seller'}-${run}@example.com`);
  await page.locator('[name=password]').fill(password);
  await page.locator('[name=nickname]').fill(nickname+run.slice(-5));
  await page.getByLabel('[필수] 이용약관에 동의합니다', {exact:true}).check();
  await page.getByLabel('[필수] 개인정보 처리에 동의합니다', {exact:true}).check();
  await expect(page.getByLabel('[선택] 마케팅 정보 수신에 동의합니다')).not.toBeChecked();
  await page.getByRole('button', {name:/^계정 만들/}).click();
}
async function login(page, account) {
  await page.goto(base+'/login');
  await page.getByLabel(/^이메일/).fill(account.email);
  await page.locator('input[type=password]').fill(account.password);
  await page.getByRole('button',{name:'로그인',exact:true}).click();
  await expect(page).not.toHaveURL(/\/login/);
}
(async()=>{
  const browser = await chromium.launch({channel:process.env.BROWSER_CHANNEL || 'chrome',headless:true});
  const contexts = [];
  let current;
  const errors = [];
  try {
    const buyer = await browser.newContext({viewport:{width:390,height:844},locale:'ko-KR'}); contexts.push(buyer);
    const page = await buyer.newPage(); current=page; page.on('pageerror',e=>errors.push(e.message)); page.on('dialog',d=>d.accept());
    const campaigns = await (await fetch(apiBase+'/campaigns')).json();
    const id = campaigns.items[0].id;
    await step('guest browse, signup return, selection preserved, no automatic participation',async()=>{
      await page.goto(base);
      if (process.env.REQUIRE_CSP === '1') {
        cspEvidence = await page.evaluate(() => {
          const meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
          const firstScript = document.querySelector('script');
          const precedesScripts = !!meta && !!firstScript && !!(meta.compareDocumentPosition(firstScript) & Node.DOCUMENT_POSITION_FOLLOWING);
          const probe = document.createElement('script');
          probe.textContent = 'window.__moduCspProbe = true';
          document.head.appendChild(probe);
          probe.remove();
          return {policy: meta?.getAttribute('content'), precedesScripts, inlineScriptBlocked: window.__moduCspProbe !== true};
        });
        assert.equal(cspEvidence.precedesScripts, true);
        assert.equal(cspEvidence.inlineScriptBlocked, true);
      }
      await expect(page.getByRole('link',{name:'육아템 둘러보기'})).toBeVisible();
      await page.screenshot({path:path.join(out,'01-welcome.png'),fullPage:true});
      await page.getByRole('link',{name:'육아템 둘러보기'}).click();
      await expect(page.locator('article.product').first()).toBeVisible();
      await page.screenshot({path:path.join(out,'02-home-mobile.png'),fullPage:true});
      await page.goto(base+'/campaigns/'+id);
      await page.getByLabel('참여 수량',{exact:true}).fill('2');
      await page.getByRole('button',{name:'모집 참여하기',exact:true}).click();
      await expect(page).toHaveURL(/\/login\?returnTo=/);
      await page.getByRole('link',{name:'회원가입',exact:true}).click();
      await signup(page,'구매검증');
      await expect(page).toHaveURL(new RegExp('/campaigns/'+id+'$'));
      await expect(page.getByLabel('참여 수량',{exact:true})).toHaveValue('2');
      await expect(page.getByLabel('결제 없는 모집 참여이며 배송·환불 조건을 확인했습니다.')).not.toBeChecked();
      await page.getByRole('button',{name:'모집 참여하기',exact:true}).click();
      await expect(page.getByRole('alert')).toContainText('동의');
    });
    await step('participation, save, withdrawal and persisted coupon wallet',async()=>{
      await page.getByLabel('결제 없는 모집 참여이며 배송·환불 조건을 확인했습니다.').check();
      await page.getByRole('button',{name:'모집 참여하기',exact:true}).click();
      await expect(page.locator('.feedback.success')).toContainText('참여를 등록');
      await page.getByRole('button',{name:'관심 공구 저장'}).click();
      await expect(page.getByRole('button',{name:'저장 해제',exact:true})).toBeVisible();
      await page.screenshot({path:path.join(out,'03-detail-mobile.png'),fullPage:true});
      await page.goto(base+'/my/reservations');
      await page.getByRole('button',{name:/철회/}).first().click();
      await expect(page.locator('.feedback.success')).toContainText('철회');
      await page.goto(base+'/benefits');
      await page.getByRole('button',{name:'쿠폰 받기',exact:true}).first().click();
      await expect(page.locator('.feedback.success')).toContainText('쿠폰을 받았습니다');
      await page.reload();
      await expect(page.locator('code').first()).toContainText('DEMO-');
      await page.screenshot({path:path.join(out,'04-wallet-mobile.png'),fullPage:true});
    });
    await step('curated feed is separate, source absent disables external link',async()=>{
      await page.goto(base+'/hotdeals');
      await expect(page.getByRole('heading',{name:'핫딜 모음',exact:true})).toBeVisible();
      await expect(page.getByRole('button',{name:'판매처 이동 불가'}).first()).toBeDisabled();
      await page.screenshot({path:path.join(out,'05-curated-mobile.png'),fullPage:true});
    });
    const seller = await browser.newContext({viewport:{width:390,height:844},locale:'ko-KR'}); contexts.push(seller);
    const sp = await seller.newPage(); current=sp; sp.on('dialog',d=>d.accept()); sp.on('pageerror',e=>errors.push(e.message));
    const sellerAlias='판매검증'+run.slice(-5), title='화면 검증 공구 '+run;
    await step('seller signup, staged application, save and pending lock',async()=>{
      await sp.goto(base+'/signup?track=seller'); await signup(sp,'판매검증');
      await expect(sp).toHaveURL(/\/seller$/);
      await expect(sp.locator('[name=business_name]')).toBeVisible();
      const fields={business_name:'개발용 가상업체',business_number:'1234567891',representative:'예시대표',contact_phone:'01000000000',
                    contact_email:'qa@example.com',business_address:'개발용 주소',return_address:'개발용 반품주소',commerce_exempt_reason:'개발용 예시'};
      for(const [key,value] of Object.entries(fields)) {
        const input=sp.locator(`form [name=${key}]`); if(await input.count()) await input.fill(value);
      }
      await sp.getByRole('button',{name:'임시저장',exact:true}).click();
      await expect(sp.locator('.feedback.success')).toContainText('임시저장');
      await sp.getByRole('button',{name:'2 운영 조건'}).click();
      for(const [key,value] of Object.entries({return_address:'개발용 반품주소',brand_name:'검증 브랜드 '+run,brand_description:'개발용 가상 브랜드',shipping_policy:'실제 배송 없음',refund_policy:'실제 결제 없음'})) {
        const input=sp.locator(`form [name=${key}]`); if(await input.count()) await input.fill(value);
      }
      await sp.getByRole('checkbox').check();
      await sp.getByRole('button',{name:'저장하고 입점 신청'}).click();
      await expect(sp.locator('.feedback.success')).toContainText('입점 신청을 접수');
      await expect(sp.getByRole('button',{name:'저장하고 입점 신청'})).toBeDisabled();
      await sp.screenshot({path:path.join(out,'06-seller-pending.png'),fullPage:true});
    });
    const admin = await browser.newContext({viewport:{width:1440,height:1000},locale:'ko-KR'}); contexts.push(admin);
    const ap=await admin.newPage(); current=ap; ap.on('pageerror',e=>errors.push(e.message));
    await step('admin approves seller, seller drafts and submits, admin publishes',async()=>{
      await login(ap,accounts.admin); await ap.goto(base+'/admin');
      const application=ap.locator('article').filter({has:ap.getByRole('heading',{name:sellerAlias,exact:true})});
      await application.getByLabel('심사 의견',{exact:true}).fill('개발용 예시 검토');
      await application.getByRole('button',{name:'승인 완료',exact:true}).click();
      await expect(ap.locator('.feedback.success').first()).toContainText('심사 상태');
      await sp.goto(base+'/seller/campaigns');
      for(const [key,value] of Object.entries({title,description:'실거래 없는 브라우저 검증 공구입니다',price:'12000',shipping_fee:'3000',minimum_quantity:'2',stock:'10',unit:'1개',ends_at:'2026-11-08T18:00'})) await sp.locator(`form [name=${key}]`).fill(value);
      await sp.getByRole('button',{name:'공구 임시저장',exact:true}).click();
      await expect(sp.locator('.feedback.success')).toContainText('저장');
      const campaign=sp.locator('article').filter({has:sp.getByRole('heading',{name:title,exact:true})});
      await campaign.getByRole('button',{name:/심사/}).click();
      await expect(sp.locator('.feedback.success')).toContainText('심사');
      await ap.reload();
      const review=ap.locator('article').filter({has:ap.getByRole('heading',{name:title,exact:true})});
      await review.getByLabel('게시 심사 의견').fill('개발용 상품조건 검토');
      await review.getByRole('button',{name:'승인하고 공개'}).click();
      await expect(ap.locator('.feedback.success').first()).toContainText('심사 결과');
      await page.goto(base+'/brands');
      await page.getByRole('link').filter({hasText:'검증 브랜드 '+run}).click();
      await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
    });
    current=ap;
    await step('real aggregate report and model inference in admin lab',async()=>{
      await ap.goto(base+'/admin');
      await expect(ap.getByText('LightGBM',{exact:true}).first()).toBeVisible();
      await ap.getByRole('button',{name:'로컬 모델 실험 실행'}).click();
      await expect(ap.getByLabel('실험 응답')).toContainText('probability');
      await ap.getByRole('heading',{name:'데이터 실험실',exact:true}).scrollIntoViewIfNeeded();
      await ap.screenshot({path:path.join(out,'07-research-desktop.png'),fullPage:true});
    });
    current=page;
    await step('offline preserves input, role denial, no horizontal mobile overflow',async()=>{
      await page.goto(base+'/login');
      await page.getByLabel(/^이메일/).fill('retained@example.com');
      await page.locator('input[type=password]').fill(password);
      await buyer.setOffline(true);
      await page.getByRole('button',{name:'로그인',exact:true}).click();
      await expect(page.getByRole('alert').first()).toBeVisible();
      await expect(page.getByLabel(/^이메일/)).toHaveValue('retained@example.com');
      await buyer.setOffline(false);
      await page.goto(base+'/admin');
      await expect(page.getByRole('heading',{name:'관리자 전용 화면'})).toBeVisible();
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
      assert.equal(overflow,false);
    });
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({date:new Date().toISOString(),browser:'Chrome',webUrl:base,apiUrl:apiBase,realApi:true,csp:cspEvidence,steps,pageErrors:errors},null,2));
    console.log('MODU_YUGA_E2E_PASS');
  } catch(e) {
    if(current) { await current.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{}); fs.writeFileSync(path.join(out,'failure.txt'),await current.locator('body').innerText().catch(()=>'')); }
    fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({date:new Date().toISOString(),steps,error:String(e)},null,2));
    throw e;
  } finally { for(const c of contexts) await c.close(); await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1});
