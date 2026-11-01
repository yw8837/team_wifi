import { isPublicRead } from "./beta-policy";
export const TOKEN_KEY = "moduyuga.session";
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(
  /\/$/,
  "",
);
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function safeReturnPath(value: unknown): string {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    /[\\\r\n]/.test(value)
  )
    return "/";
  try {
    const url = new URL(value, "https://local.invalid");
    if (
      url.origin !== "https://local.invalid" ||
      ["/login", "/signup", "/reset"].some((p) => url.pathname === p)
    )
      return "/";
    return url.pathname + url.search + url.hash;
  } catch {
    return "/";
  }
}
export function formatError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) =>
        typeof e === "object" && e
          ? `${Array.isArray(e.loc) ? e.loc.filter((x: string) => x !== "body").join(" · ") : "입력"}: ${e.msg || "값을 확인해 주세요."}`
          : "입력값을 확인해 주세요.",
      )
      .join("\n");
  return "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}
export function safeExternalUrl(
  value: string | null | undefined,
): string | null {
  try {
    if (!value) return null;
    const u = new URL(value);
    return u.protocol === "https:" && !u.username && !u.password
      ? u.href
      : null;
  } catch {
    return null;
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  try {
    let response: Response;
    try {
      response = await fetch(API_BASE + path, {
        method,
        headers: {
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch {
      throw new ApiError(0, controller.signal.aborted
        ? "응답 시간이 초과되었습니다. 처리 여부를 먼저 확인한 뒤 다시 시도해 주세요. 입력 내용은 유지됩니다."
        : "서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요. 입력 내용은 유지됩니다.");
    }
    const data = await response.json().catch(() => {
      if (controller.signal.aborted) throw new ApiError(0, "응답 시간이 초과되었습니다. 처리 여부를 확인한 뒤 다시 시도해 주세요.");
      return {};
    });
    if (!response.ok) {
      if (response.status === 401 && token) {
        sessionStorage.removeItem(TOKEN_KEY);
        window.dispatchEvent(new CustomEvent("auth-expired", {
          detail: { redirect: method !== "GET", publicRead: isPublicRead(path, method) },
        }));
      }
      throw new ApiError(response.status, formatError(data.detail));
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
}
export const money = (value: number) =>
  new Intl.NumberFormat("ko-KR").format(value) + "원";
export const date = (value: string) =>
  value
    ? new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul",
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "미정";
export const categories = [
  "기저귀·물티슈",
  "수유·이유식",
  "목욕·위생",
  "외출·안전",
  "놀이·도서",
  "육아생활",
];
export const statusName: Record<string, string> = {
  draft: "임시저장",
  pending: "심사 중",
  needs_changes: "보완 필요",
  approved: "승인 완료",
  suspended: "이용 정지",
  active: "모집 중",
  ended: "종료",
  rejected: "반려",
  withdrawn: "참여 철회",
  stale: "정보 재확인 필요",
  available: "사용 가능",
  used: "사용됨",
  expired: "만료",
};
