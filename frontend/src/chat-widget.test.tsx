import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { ChatWidget } from "./chat-widget";
import { chatEnterSubmits } from "./chat";

describe("floating chat entry", () => {
  it("starts closed without mounting a conversation", () => {
    const html = renderToStaticMarkup(<MemoryRouter><ChatWidget/></MemoryRouter>);
    expect(html).toContain('aria-label="챗봇 열기"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain('role="dialog"');
  });
  it("avoids duplicate chat and authentication screens", () => {
    for (const path of ["/chat", "/login", "/signup", "/auth/complete"]) {
      expect(renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><ChatWidget/></MemoryRouter>)).toBe("");
    }
  });
  it("submits Enter while preserving Shift+Enter and Korean composition", () => {
    const enter = {key:"Enter", shiftKey:false, isComposing:false};
    expect(chatEnterSubmits(enter)).toBe(true);
    expect(chatEnterSubmits({...enter, shiftKey:true})).toBe(false);
    expect(chatEnterSubmits({...enter, isComposing:true})).toBe(false);
    expect(chatEnterSubmits({...enter, keyCode:229})).toBe(false);
    expect(chatEnterSubmits({...enter, key:"a"})).toBe(false);
  });
});
