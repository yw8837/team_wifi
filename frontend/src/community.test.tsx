import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { CommunityFilters, communityFilterSummary, communityQuery, communityTime, periodError, postType } from "./community";
import type { Demand } from "./release-data";

describe("community URL and date contract",()=>{
 it("accepts inclusive same-day Korea date periods and all dates",()=>{expect(periodError("2026-11-06","2026-11-06")).toBe("");expect(periodError("","")).toBe("");});
 it.each([["2026-02-30",""],["0000-01-01",""],["2026-1-01",""],["2026-11-07","2026-11-06"],["invalid",""]])("rejects invalid or inverted periods %s %s",(from,to)=>expect(periodError(from,to)).not.toBe(""));
 it("preserves query, type, category and dates when paging",()=>{const input=new URLSearchParams({q:"유모차",post_type:"experience",category:"외출·안전",start_date:"2026-11-01",end_date:"2026-11-06",page:"2"});const actual=new URLSearchParams(communityQuery(input));expect(Object.fromEntries(actual)).toEqual({q:"유모차",limit:"20",offset:"40",category:"외출·안전",post_type:"experience",start_date:"2026-11-01",end_date:"2026-11-06"});});
 it("uses activity tabs without sending unsupported type/category filters",()=>{const actual=new URLSearchParams(communityQuery(new URLSearchParams("tab=comments&post_type=question&category=a&page=-1"),true));expect(actual.get("tab")).toBe("comments");expect(actual.get("offset")).toBe("0");expect(actual.has("post_type")).toBe(false);expect(actual.has("category")).toBe(false);});
 it("defaults historical posts to demand without changing explicit types",()=>{expect(postType({} as Demand)).toBe("demand");expect(postType({post_type:"information"} as Demand)).toBe("information");});
 it("always summarizes the applied URL rather than an unsubmitted draft",()=>{expect(communityFilterSummary(new URLSearchParams("q=유모차&post_type=question&category=외출·안전&start_date=2026-11-01&end_date=2026-11-06"))).toEqual({count:4,text:"검색: 유모차 · 질문 · 외출·안전 · 2026-11-01 ~ 2026-11-06"});});
 it("keeps advanced conditions closed initially while exposing applied filters and a semantic period group",()=>{const html=renderToStaticMarkup(<MemoryRouter initialEntries={["/?category=외출·안전&start_date=2026-11-01"]}><CommunityFilters/></MemoryRouter>);expect(html).toContain('<details class="community-advanced">');expect(html).not.toMatch(/<details[^>]*\sopen(?:[\s=>])/);expect(html).toContain("적용 중 2개");expect(html).toContain("외출·안전");expect(html).toContain("2026-11-01 ~ 현재");expect(html).toContain("<legend>기간</legend>");expect(html.indexOf('<details')).toBeLessThan(html.indexOf('name="start_date"'));expect(html).toContain('name="end_date"');});
 it("formats server instants in Korea with a stable 24-hour display",()=>{expect(communityTime("2026-11-05T15:04:00Z")).toBe("2026.11.06 00:04");expect(communityTime("2026-11-06T14:59:00Z")).toBe("2026.11.06 23:59");expect(communityTime("invalid")).toBe("시각 미확인");});
});
