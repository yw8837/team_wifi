import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { IconMessageCircle, IconX } from "@tabler/icons-react";
import { ChatPage } from "./chat";

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [started, setStarted] = useState(false);
  const launcher = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const location = useLocation();

  useEffect(() => { setOpen(false); }, [location.pathname]);
  useEffect(() => {
    if (open) panel.current?.querySelector<HTMLTextAreaElement>("textarea")?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    launcher.current?.focus();
  }

  if (/^\/(chat|login|signup|reset|auth)(\/|$)/.test(location.pathname)) return null;
  return <aside className="chat-widget" aria-label="육아 도우미">
    {started && <section ref={panel} id="chat-widget-panel" className="chat-widget-panel"
      role="dialog" aria-label="육아 도우미 대화창" hidden={!open}
      onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); close(); } }}>
      <header className="chat-widget-header"><strong>육아 도우미</strong>
        <button type="button" className="secondary" aria-label="대화창 닫기" onClick={close}>
          <IconX size={22} aria-hidden="true"/>
        </button>
      </header>
      <ChatPage embedded/>
    </section>}
    <button ref={launcher} type="button" className="chat-widget-launcher"
      aria-label={open ? "챗봇 닫기" : "챗봇 열기"} aria-expanded={open}
      aria-controls={started ? "chat-widget-panel" : undefined}
      onClick={() => { setStarted(true); setOpen(value => !value); }}>
      {open ? <IconX size={24} aria-hidden="true"/> : <IconMessageCircle size={24} aria-hidden="true"/>}
      <span>챗봇</span>
    </button>
  </aside>;
}
