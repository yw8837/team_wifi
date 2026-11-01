import { beforeAll, beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "./shared";
import type { Offer, Demand, Comment } from "./release-data";
const state=vi.hoisted(()=>({data:new Map<string,unknown>(),loading:false,error:""}));
vi.mock("./release-data",async()=>{
 const actual=await vi.importActual<typeof import("./release-data")>("./release-data");
 return {...actual,usePublicResource:(path:string|null)=>({data:path?state.data.get(path.split("?")[0])??[]:null,loading:state.loading,error:state.error,reload:vi.fn()})};
});
let PublicApp:typeof import("./public-app").PublicApp,PublicGate:typeof import("./public-app").PublicGate;
let PublicAdmin:typeof import("./public-app").PublicAdmin;
let policy:typeof import("./release-policy");
function render(path:string){return renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><AuthProvider><PublicApp/></AuthProvider></MemoryRouter>);}
const offer:Offer={id:"ref-1",title:"안전한 용품 선택",category:"외출·안전",summary:"공식 안전 정보",source_name:"공식 기관",source_url:"https://example.org/safety",source_checked_at:"2026-11-01T00:00:00Z",entry_type:"shopping_reference",price:null,shipping_fee:null,unit:null,expires_at:null,comparison_notes:["규격을 확인하세요."],is_affiliate:false,saved:false};
const demand:Demand={id:"d1",title:"안전용품 수요",body:'<img src=x onerror="alert(1)"> 육아용품 질문',category:"외출·안전",author:{id:"u1",nickname:"작성자"},created_at:"2026-11-01T00:00:00Z",interest_count:0,interested:false,comment_count:1,own:false};
beforeAll(async()=>{vi.stubEnv("VITE_PUBLIC_RELEASE","1");vi.stubEnv("VITE_BETA_MODE","0");({PublicApp,PublicGate,PublicAdmin}=await import("./public-app"));policy=await import("./release-policy");});
beforeEach(()=>{
 vi.stubGlobal("sessionStorage",{getItem:()=>null,setItem:vi.fn(),removeItem:vi.fn()});
 vi.stubGlobal("navigator",{onLine:true});vi.stubGlobal("window",{location:{origin:"https://app.example.test"}});
 vi.stubGlobal("fetch",vi.fn());state.data.clear();state.loading=false;state.error="";
 state.data.set("/config",{public_release:true,beta_mode:false});state.data.set("/release/offers",[offer]);state.data.set("/release/offers/ref-1",offer);state.data.set("/release/demands",[demand]);state.data.set("/release/demands/d1",demand);
 const comment:Comment={id:"c1",body:"규격 확인이 궁금해요",author:{id:"u2",nickname:"질문자"},created_at:demand.created_at,own:false};state.data.set("/release/demands/d1/comments",[comment]);
});
afterEach(()=>vi.unstubAllGlobals());
describe("public release navigation and safe content",()=>{
 it("opens useful browse first and omits legacy transactional navigation",()=>{const html=render("/");expect(html).toContain("육아템, 꼼꼼히 알아보고 준비해요");expect(html).toContain('type="search"');expect(html).toContain("공식 참고 정보");expect(html).toContain('href="/calculator"');expect(html).not.toMatch(/href="\/(?:seller|benefits|campaigns|brands|hotdeals)/);expect(html).not.toContain("포인트");expect(fetch).not.toHaveBeenCalled();});
 it.each(["/my/saved","/settings","/demands/new","/admin"])("protects owned route %s without hiding guest exploration",path=>{const html=render(path);expect(html).toContain("로그인이 필요해요");expect(html).toContain("/login?returnTo="+encodeURIComponent(path));expect(fetch).not.toHaveBeenCalled();});
 it("does not expose legacy beta routes",()=>{expect(render("/benefits")).toContain("화면을 찾을 수 없어요");expect(render("/seller")).not.toContain("입점 신청");});
 it("renders null prices as unknown and labels official reference sources",()=>{const html=render("/offers/ref-1");expect(html).toContain("가격 정보 없음");expect(html).toContain("배송비 정보 없음");expect(html).toContain("공식 참고 정보 · 특가 아님");expect(html).toContain('href="https://example.org/safety"');expect(html).not.toContain("0원");});
 it("escapes UGC, shows accurate zero interest and report/block for post and comment",()=>{const html=render("/demands/d1");expect(html).toContain("&lt;img");expect(html).not.toContain('<img src="x"');expect(html).toContain("현재 관심 0명");expect(html).toContain("아이의 이름·생일·사진");expect(html).toContain("이 글 신고");expect(html).toContain("이 댓글 신고");expect(html).toContain("작성자 작성자 차단");expect(html).not.toContain("내 글 삭제");});
 it("provides own delete on UGC when server marks it owned",()=>{state.data.set("/release/demands/d1",{...demand,own:true});expect(render("/demands/d1")).toContain("내 글 삭제");});
 it("makes public signup buyer-only with adult consent and no marketing/invite",()=>{const html=render("/signup?track=seller");expect(html).toContain("구매자로 시작하기");expect(html).toContain("만 18세 이상");expect(html).toContain("[필수] 이용약관");expect(html).not.toContain("초대코드");expect(html).not.toContain("마케팅 정보");expect(html).not.toContain("판매자로 시작하기");});
 it("uses recovery code reset instead of development outbox",()=>{const html=render("/reset");expect(html).toContain("복구코드로 비밀번호 재설정");expect(html).not.toContain("outbox");});
 it("keeps guest return to original public detail without automatic actions",()=>{const html=render("/login?returnTo="+encodeURIComponent("/demands/d1?view=comments#question"));expect(html).toContain('href="/demands/d1?view=comments#question"');expect(fetch).not.toHaveBeenCalled();});
 it("offers useful empty states without fabricated records",()=>{state.data.set("/release/demands",[]);const html=render("/demands");expect(html).toContain("아직 올라온 수요가 없어요");expect(html).toContain("첫 수요 제안하기");expect(html).not.toContain("안전용품 수요");});
 it("blocks mismatched server mode before rendering public children",()=>{state.data.set("/config",{public_release:false,beta_mode:true});const html=renderToStaticMarkup(<MemoryRouter><PublicGate enabled><p>SHOULD_NOT_RENDER</p></PublicGate></MemoryRouter>);expect(html).toContain("현재 서버와 앱 버전이 맞지 않아");expect(html).not.toContain("SHOULD_NOT_RENDER");expect(html).toContain("연결 다시 확인");});
 it("lets an admin inspect real active report context before selecting an action",()=>{state.data.set("/release/admin/reports",[{id:"r1",target_type:"comment",target_id:"c1",reason:"개인정보 노출 의심",status:"active",target_preview:"<script>unsafe</script>",demand_id:"d1",author_nickname:"작성자"}]);const html=renderToStaticMarkup(<MemoryRouter><PublicAdmin/></MemoryRouter>);expect(html).toContain("접수 · 검토 필요");expect(html).toContain("&lt;script&gt;");expect(html).toContain('href="/demands/d1"');expect(html).toContain('value="hide"');expect(html).toContain('value="dismiss"');expect(html).toContain('value="suspend"');expect(html).toContain("대상 확인 후 선택하세요");});
 it("keeps calculator usable while server is offline without exposing network routes",()=>{state.error="인터넷 연결을 확인하세요.";const html=renderToStaticMarkup(<MemoryRouter initialEntries={["/calculator"]}><PublicGate enabled><p>NETWORK_ROUTES</p></PublicGate></MemoryRouter>);expect(html).toContain("단가 비교 계산기");expect(html).not.toContain("NETWORK_ROUTES");expect(html).toContain("서버에 전송하거나 저장하지 않습니다");});
});
describe("release policy and calculator",()=>{
 it("treats only release browse GETs as guest readable",async()=>{const {isPublicRead}=await import("./beta-policy");expect(isPublicRead("/release/demands/d1/comments")).toBe(true);expect(isPublicRead("/release/offers?q=safe")).toBe(true);expect(isPublicRead("/release/saved")).toBe(false);expect(isPublicRead("/release/demands/d1/interest","PUT")).toBe(false);});
 it("keeps deployed security enabled for public release independently of beta",()=>{expect(policy.PUBLIC_RELEASE).toBe(true);expect(policy.DEPLOYED_MODE).toBe(true);});
 it.each([null,{}, {public_release:true},{public_release:false,beta_mode:false},{public_release:true,beta_mode:true}])("fails closed for config %j",config=>expect(policy.publicConfigMatches(config)).toBe(false));
 it("accepts only explicit public server config",()=>expect(policy.publicConfigMatches({public_release:true,beta_mode:false})).toBe(true));
 it.each(["/demands/new","/DEMANDS/new/","/%64emands/new","/settings","/admin","/my/saved","/seller"])("keeps guest escape away from owned/legacy path %s",path=>expect(policy.publicBrowsePath(path)).toBe("/"));
 it("preserves full public detail return path",()=>expect(policy.publicBrowsePath("/demands/d1?view=comments#q")).toBe("/demands/d1?view=comments#q"));
 it("includes shipping before dividing by quantity",()=>expect(policy.compareUnit({price:"12000",shipping:"3000",quantity:"30"})).toEqual({total:15000,unit:500}));
 it("supports zero price/shipping with a positive quantity",()=>expect(policy.compareUnit({price:"0",shipping:"0",quantity:"5"})).toEqual({total:0,unit:0}));
 it.each([{price:"",shipping:"0",quantity:"1"},{price:"100",shipping:"",quantity:"1"},{price:"-1",shipping:"0",quantity:"1"},{price:"100",shipping:"-1",quantity:"1"},{price:"100",shipping:"0",quantity:"0"},{price:"100",shipping:"0",quantity:"-5"},{price:"NaN",shipping:"0",quantity:"1"},{price:"Infinity",shipping:"0",quantity:"1"},{price:"100",shipping:"0",quantity:"1e-320"}])("rejects invalid comparison %j",input=>expect(policy.compareUnit(input)).toBeNull());
});
