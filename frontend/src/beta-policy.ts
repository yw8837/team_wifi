/** Build and runtime share this policy so a beta cannot fall back to a local API. */
export function betaApiOrigin(beta: boolean, base: string | undefined): string | null {
  if (!base && !beta) return null;
  let url: URL;
  try { url = new URL(base || ""); } catch {
    if (beta) throw new Error("베타 빌드에는 HTTPS VITE_API_BASE_URL이 필요합니다.");
    return null;
  }
  const host = url.hostname.replace(/^\[|\]$/g, "").replace(/\.$/, "").toLowerCase();
  if (beta && (url.protocol !== "https:" || url.username || url.password ||
    host === "localhost" || host.endsWith(".localhost") || host === "::1" ||
    /^127\./.test(host) || host === "0.0.0.0" || url.search || url.hash)) {
    throw new Error("베타 API는 localhost가 아닌 HTTPS 주소여야 합니다.");
  }
  return url.origin;
}

export function buildCsp(beta: boolean, base: string | undefined): string {
  const origin = betaApiOrigin(beta, base);
  const connections = beta ? (origin ? ` ${origin}` : "") :
    ` http://10.0.2.2:8000 http://127.0.0.1:8000${origin ? ` ${origin}` : ""}`;
  return `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'${connections}; object-src 'none'; base-uri 'none'; form-action 'self'`;
}

export function isPublicRead(path: string, method = "GET"): boolean {
  if (method !== "GET") return false;
  if (/^\/release\/(?:offers(?:\/[^/?]+)?|demands(?:\/[^/?]+(?:\/comments)?)?)(?:\?.*)?$/.test(path)) return true;
  return /^\/(?:config|health|hotdeals|coupons|brands(?:\/[^/?]+)?|campaigns(?:\/[^/?]+(?:\/questions)?)?)(?:\?.*)?$/.test(path);
}

export function signupDestination(track: string, returnTo: string): string {
  return returnTo !== "/" ? returnTo : track === "seller" ? "/seller" : "/";
}
