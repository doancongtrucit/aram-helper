import {
  detectPlatform, primaryDownload, chooseLang, redirectTarget, parseLatestTag, shouldAutoRedirect, shareAction,
  feedbackMailto, scrollState,
} from "./logic.mjs?v=d9d22673";

const RELEASES_API = "https://api.github.com/repos/doancongtrucit/aram-helper/releases/latest";

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch { /* storage blocked */ }
  return null;
}

const body = document.body;
const pageLang = body.dataset.lang === "en" ? "en" : "vi";

// Language: only redirect on a first visit with nothing stored.
// The language links store the choice, so switching manually never loops.
const stored = store("lang");
if (shouldAutoRedirect(stored, document.referrer, location.origin, navigator.userAgent)) {
  const chosen = chooseLang(navigator.languages || [navigator.language || ""], null);
  const base = pageLang === "en" ? "../" : "";
  const target = redirectTarget(pageLang, chosen, base, location.search + location.hash);
  if (target) { location.replace(target); }
  else { store("lang", pageLang); }
}

document.querySelectorAll("[data-set-lang]").forEach((a) =>
  a.addEventListener("click", () => store("lang", a.dataset.setLang)));

// OS-aware primary download button; phones get a "open this on a PC" note.
const platform = detectPlatform(navigator.userAgent, navigator.platform, navigator.maxTouchPoints || 0);
const dl = document.getElementById("primary-dl");
if (dl) {
  const r = primaryDownload(platform, { win: dl.dataset.dlWin, mac: dl.dataset.dlMac }, pageLang);
  dl.href = r.href;
  dl.textContent = r.label;
}
if (platform === "mobile") body.classList.add("is-mobile");

const shareBtn = document.getElementById("share-link");
const shareStatus = document.getElementById("share-status");
if (shareBtn) {
  shareBtn.addEventListener("click", async () => {
    const how = shareAction(navigator);
    try {
      if (how === "share") {
        await navigator.share({ title: document.title, url: location.href });
      } else if (how === "copy") {
        await navigator.clipboard.writeText(location.href);
        if (shareStatus) shareStatus.textContent = shareBtn.dataset.copied;
      } else if (shareStatus) {
        shareStatus.textContent = location.href;
      }
    } catch (err) {
      if (err && err.name === "AbortError") return;   // share sheet dismissed
      if (shareStatus) shareStatus.textContent = location.href;
    }
  });
}

// Donate QR: show it only when it actually loads.
const qr = document.getElementById("donate-qr");
const donate = document.getElementById("donate");
if (qr && donate) {
  const ok = () => donate.classList.add("qr-ok");
  const fail = () => {
    const fig = qr.closest(".donate-figure") || qr;
    fig.hidden = true;
    fig.style.display = "none";
    donate.classList.remove("qr-ok");
  };
  if (qr.complete) (qr.naturalWidth > 0 ? ok : fail)();
  else { qr.addEventListener("load", ok); qr.addEventListener("error", fail); }
}

// Mobile menu.
const toggle = document.querySelector(".nav-toggle");
if (toggle) {
  const sync = () => toggle.setAttribute("aria-expanded", String(body.classList.contains("nav-open")));
  sync();
  toggle.addEventListener("click", () => { body.classList.toggle("nav-open"); sync(); });
  document.querySelectorAll("#site-links a").forEach((a) =>
    a.addEventListener("click", () => { body.classList.remove("nav-open"); sync(); }));
}

// Lightbox: click (or Enter/Space on) any screenshot to zoom in.
const lightbox = document.getElementById("lightbox");
const lightImg = document.getElementById("lightbox-img");
if (lightbox && lightImg && typeof lightbox.showModal === "function") {
  const open = (img) => {
    lightImg.src = img.currentSrc || img.src;
    lightImg.alt = img.alt;
    lightbox.showModal();
  };
  document.querySelectorAll("img.zoomable").forEach((img) => {
    img.tabIndex = 0;
    img.setAttribute("role", "button");
    const hint = lightbox.getAttribute("aria-label");
    if (hint) img.setAttribute("aria-label", `${img.alt} – ${hint}`);
    img.addEventListener("click", () => open(img));
    img.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(img); }
    });
  });
  // Demo video plays in the same dialog; without JS the button still jumps to #features.
  const demoBtn = document.getElementById("demo-btn");
  const demoVideo = document.getElementById("demo-video");
  if (demoBtn && demoVideo) {
    demoBtn.addEventListener("click", (e) => {
      e.preventDefault();
      lightImg.hidden = true;
      demoVideo.hidden = false;
      lightbox.showModal();
      demoVideo.currentTime = 0;
      demoVideo.play().catch(() => {});
    });
  }
  // Click the image or the backdrop to close; the × button and Esc work natively.
  lightbox.addEventListener("click", (e) => { if (e.target === lightbox || e.target === lightImg) lightbox.close(); });
  lightbox.addEventListener("close", () => {
    lightImg.removeAttribute("src");
    lightImg.hidden = false;
    if (demoVideo) { demoVideo.pause(); demoVideo.hidden = true; }
  });
}

// Donate QR: hidden until the visitor asks for it.
const qrToggle = document.getElementById("qr-toggle");
const qrPanel = document.getElementById("qr-panel");
if (qrToggle && qrPanel) {
  qrToggle.addEventListener("click", () => {
    const show = qrPanel.hidden;
    qrPanel.hidden = !show;
    qrToggle.setAttribute("aria-expanded", String(show));
    qrToggle.textContent = show ? qrToggle.dataset.hide : qrToggle.dataset.show;
  });
  // "Ủng hộ" in the nav: jump to the donate card and open the QR right away.
  document.querySelectorAll("[data-open-qr]").forEach((a) =>
    a.addEventListener("click", () => { if (qrPanel.hidden) qrToggle.click(); }));
}

// Feedback form: no server, so it composes an email in the visitor's own mail app.
const fb = document.getElementById("fb-form");
const fbStatus = document.getElementById("fb-status");
if (fb && fbStatus) {
  fb.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = fb.elements.name.value.trim();
    const topic = fb.elements.topic.value;
    const to = fb.dataset.email;
    const url = feedbackMailto(to, topic, name, fb.elements.message.value, pageLang);
    fbStatus.classList.remove("err");
    if (!url) {
      fbStatus.classList.add("err");
      fbStatus.textContent = fb.dataset.err;
      fb.elements.message.focus();
      return;
    }
    location.href = url;
    fbStatus.textContent = "";
    const a = document.createElement("a");
    a.href = `mailto:${to}`;
    a.textContent = to;
    fbStatus.append(`${fb.dataset.ok} `, a);
  });
}

// Floating scroll button: ring shows progress; click jumps to the end, or back to the top once there.
const fab = document.getElementById("scroll-fab");
if (fab) {
  fab.hidden = false;
  const update = () => {
    const { pct, atEnd } = scrollState(scrollY, document.documentElement.scrollHeight, innerHeight);
    fab.style.setProperty("--p", String(pct));
    if (atEnd !== fab.classList.contains("at-end")) {
      fab.classList.toggle("at-end", atEnd);
      const label = atEnd ? fab.dataset.top : fab.dataset.end;
      fab.setAttribute("aria-label", label);
      fab.title = label;
    }
  };
  update();
  addEventListener("scroll", update, { passive: true });
  addEventListener("resize", update, { passive: true });
  fab.addEventListener("click", () => {
    const smooth = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    const top = fab.classList.contains("at-end") ? 0 : document.documentElement.scrollHeight;
    scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
  });
}

// Visual effects: decorative only, skipped when the visitor asks for reduced motion.
try {
  const motionOK = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)").matches;

  // Nav gets a neon edge once the page scrolls.
  const onScroll = () => body.classList.toggle("scrolled", scrollY > 8);
  onScroll();
  addEventListener("scroll", onScroll, { passive: true });

  // Cursor spotlight on cards.
  if (finePointer) {
    document.addEventListener("pointermove", (e) => {
      const box = e.target.closest && e.target.closest(".box");
      if (!box) return;
      const r = box.getBoundingClientRect();
      box.style.setProperty("--mx", `${e.clientX - r.left}px`);
      box.style.setProperty("--my", `${e.clientY - r.top}px`);
    }, { passive: true });
  }

  if (motionOK && "IntersectionObserver" in window) {
    // Scroll reveal, staggered within each group.
    const groups = document.querySelectorAll("main > section:not(.hero)");
    const targets = [];
    groups.forEach((sec) => {
      sec.querySelectorAll(":scope > h2, :scope > p, .box, .frow, .mini, .more-title, details, .note").forEach((el, i) => {
        if (el.closest(".mobile-note") && !body.classList.contains("is-mobile")) return;
        el.classList.add("reveal");
        el.style.setProperty("--i", String(Math.min(i, 6)));
        targets.push(el);
      });
    });
    // Cards flip in like augment cards being dealt: card back -> flip -> rim flash + sparkle burst.
    const augCards = new Set();
    document.querySelectorAll(".box.hl, .box.step, .mini, .download .box").forEach((card) => {
      if (!card.classList.contains("reveal")) return;
      augCards.add(card);
      card.classList.add("aug");
      for (const cls of ["aug-back", "aug-shine"]) {
        const s = document.createElement("span");
        s.className = cls;
        s.setAttribute("aria-hidden", "true");
        card.append(s);
        s.addEventListener("animationend", () => s.remove(), { once: true });
      }
    });
    const sparkle = (card) => {
      const n = matchMedia("(max-width: 640px)").matches ? 7 : 11;
      for (let k = 0; k < n; k++) {
        const s = document.createElement("span");
        s.className = "aug-spark";
        s.setAttribute("aria-hidden", "true");
        const ang = (k / n) * Math.PI * 2 + Math.random() * 0.5;
        const dist = 40 + Math.random() * 50;
        s.style.cssText = `left:${10 + Math.random() * 80}%;top:${15 + Math.random() * 70}%;` +
          `--dx:${Math.cos(ang) * dist}px;--dy:${Math.sin(ang) * dist - 20}px;` +
          `--sz:${9 + Math.random() * 9}px;animation-delay:${Math.random() * 120}ms`;
        card.append(s);
        s.addEventListener("animationend", () => s.remove(), { once: true });
      }
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        const el = en.target;
        el.classList.add("in");
        io.unobserve(el);
        if (augCards.has(el)) {
          const i = Number(el.style.getPropertyValue("--i")) || 0;
          setTimeout(() => sparkle(el), 430 + i * 110);       // burst as the card face lands
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    document.documentElement.classList.add("fx");
    targets.forEach((el) => io.observe(el));

    // 3D tilt on the hero screenshot.
    const shot = document.querySelector(".hero-shot");
    if (shot && finePointer) {
      shot.addEventListener("pointermove", (e) => {
        const r = shot.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        shot.style.transform = `perspective(1000px) rotateY(${x * 10}deg) rotateX(${-y * 8}deg)`;
      });
      shot.addEventListener("pointerleave", () => { shot.style.transform = ""; });
    }

    // Rising neon sparks behind the hero; paused off-screen and in background tabs.
    const canvas = document.getElementById("sparks");
    const saveData = navigator.connection && navigator.connection.saveData;
    if (canvas && canvas.getContext && !saveData) {
      const ctx = canvas.getContext("2d");
      const colors = ["#ffb458", "#ff9b55", "#f36a78", "#c9349b", "#ffd29a"];
      let w = 0, h = 0, dpr = 1, raf = 0, visible = true;
      const SPRITE = 32;
      const sprites = Object.fromEntries(colors.map((c) => {
        const sc = document.createElement("canvas");
        sc.width = sc.height = SPRITE;
        const g = sc.getContext("2d");
        const grad = g.createRadialGradient(SPRITE / 2, SPRITE / 2, 0, SPRITE / 2, SPRITE / 2, SPRITE / 2);
        grad.addColorStop(0, "#ffffff");
        grad.addColorStop(0.18, c);
        grad.addColorStop(1, c + "00");
        g.fillStyle = grad;
        g.fillRect(0, 0, SPRITE, SPRITE);
        return [c, sc];
      }));
      const count = innerWidth < 640 ? 22 : 46;
      const make = (fresh) => ({
        x: Math.random() * w,
        y: fresh ? Math.random() * h : h + 10,
        r: 0.6 + Math.random() * 1.8,
        vy: 0.25 + Math.random() * 0.7,
        vx: (Math.random() - 0.5) * 0.3,
        a: 0.3 + Math.random() * 0.7,
        c: colors[(Math.random() * colors.length) | 0],
        t: Math.random() * Math.PI * 2,
      });
      const resize = () => {
        if (w && canvas.clientWidth === w) return;     // mobile URL bar show/hide only changes height
        dpr = Math.min(devicePixelRatio || 1, 2);
        w = canvas.clientWidth; h = canvas.clientHeight;
        canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      };
      resize();
      const sparks = Array.from({ length: count }, () => make(true));
      const tick = () => {
        ctx.clearRect(0, 0, w, h);
        ctx.globalCompositeOperation = "lighter";
        for (const s of sparks) {
          s.t += 0.03; s.y -= s.vy; s.x += s.vx + Math.sin(s.t) * 0.2;
          if (s.y < -10) Object.assign(s, make(false));
          const fade = Math.min(1, s.y / (h * 0.25));
          ctx.globalAlpha = s.a * fade * (0.6 + 0.4 * Math.sin(s.t * 2));
          const size = s.r * 7;
          ctx.drawImage(sprites[s.c], s.x - size / 2, s.y - size / 2, size, size);
        }
        raf = requestAnimationFrame(tick);
      };
      const run = () => { cancelAnimationFrame(raf); if (visible && !document.hidden) raf = requestAnimationFrame(tick); };
      new IntersectionObserver(([en]) => { visible = en.isIntersecting; run(); }).observe(canvas);
      document.addEventListener("visibilitychange", run);
      addEventListener("resize", resize, { passive: true });
      run();
    }
  }
} catch { /* effects are optional */ }

// Live version label: last and best-effort, so a missing fetch/AbortController cannot break anything above.
try {
  const verEls = document.querySelectorAll("[data-version]");
  if (verEls.length) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 5000);
    fetch(RELEASES_API, { signal: ctl.signal, headers: { Accept: "application/vnd.github+json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        const v = parseLatestTag(j);
        if (!v) return;
        verEls.forEach((el) => { el.textContent = "v" + v; el.hidden = false; });
      })
      .catch(() => {})
      .finally(() => clearTimeout(timer));
  }
} catch { /* no fetch / AbortController: version label stays hidden */ }
