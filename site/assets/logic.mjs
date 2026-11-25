// Pure helpers (no DOM) so they can be unit-tested with node --test.

export function detectPlatform(ua = "", platform = "", maxTouchPoints = 0) {
  if (/Android|iPhone|iPad|iPod/i.test(ua)) return "mobile";
  if (/Mac/i.test(platform) && maxTouchPoints > 1) return "mobile"; // iPadOS reports MacIntel
  if (/Win/i.test(platform) || /Windows/i.test(ua)) return "windows";
  if (/Mac/i.test(platform) || /Macintosh|Mac OS X/i.test(ua)) return "mac";
  return "other";
}

const LABELS = {
  vi: { windows: "⬇ Tải cho Windows", mac: "⬇ Tải cho macOS", other: "Xem bản tải" },
  en: { windows: "⬇ Download for Windows", mac: "⬇ Download for macOS", other: "See downloads" },
};

export function primaryDownload(p, links, lang) {
  const l = LABELS[lang] || LABELS.en;
  if (p === "windows") return { href: links.win, label: l.windows };
  if (p === "mac") return { href: links.mac, label: l.mac };
  return { href: "#download", label: l.other };
}

export function chooseLang(navLanguages, stored) {
  if (stored === "vi" || stored === "en") return stored;
  const list = Array.isArray(navLanguages) ? navLanguages : [];
  return list.some((l) => String(l).toLowerCase().startsWith("vi")) ? "vi" : "en";
}

// `suffix` (location.search + location.hash) is kept so deep links survive the redirect.
export function redirectTarget(pageLang, chosen, base, suffix = "") {
  if (pageLang === chosen) return null;
  return (chosen === "en" ? "en/" : base + "") + suffix;
}

export function parseLatestTag(json) {
  const tag = json && typeof json === "object" ? json.tag_name : null;
  if (typeof tag !== "string") return null;
  const m = /^v?(\d+\.\d+\.\d+)/.exec(tag);
  return m ? m[1] : null;
}

// Auto-redirect only on a true first visit: nothing stored and not arriving
// from one of our own pages (covers blocked storage, e.g. Safari private mode).
export function isBot(ua = "") {
  return /bot|crawl|spider|slurp|facebookexternalhit|discordbot|twitterbot/i.test(ua);
}

// Crawlers are never redirected, so each language URL stays indexable.
export function shouldAutoRedirect(stored, referrer, origin, ua = "") {
  if (isBot(ua)) return false;
  if (stored === "vi" || stored === "en") return false;
  if (referrer && origin && (referrer === origin || referrer.startsWith(origin + "/"))) return false;
  return true;
}

// How the "open this on a PC" button hands the link over.
export function shareAction(nav) {
  if (!nav) return "none";
  if (typeof nav.share === "function") return "share";
  if (nav.clipboard && typeof nav.clipboard.writeText === "function") return "copy";
  return "none";
}

// Feedback form → mailto: link for the visitor's own mail app. Returns null when there is no message.
export function feedbackMailto(to, topic, name, msg, lang) {
  const body = String(msg || "").trim();
  if (!body) return null;
  const who = String(name || "").trim() || "(no name)";
  const subject = `[ARAM Helper] ${String(topic || "").trim()}`.trim();
  const text = `${body}\n\n— ${who}\n(ARAM Helper website · ${lang})`;
  return `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(text)}`;
}

// Scroll button state: percent read (0–100) and whether we are at the end (≥ 97%, or nothing to scroll).
export function scrollState(scrollY, scrollHeight, viewport) {
  const max = scrollHeight - viewport;
  const p = max > 0 ? Math.min(1, Math.max(0, scrollY / max)) : 1;
  return { pct: Math.round(p * 100), atEnd: p > 0.97 };
}
