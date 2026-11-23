const languages = {
  en: {
    title: "Your audio library",
    pair: "Pair this device",
    instructions: "Enter the one-time code shown on your computer.",
    code: "Pairing code",
    connect: "Connect",
    add: "Add a track",
    link: "SoundCloud link or share message",
    format: "Audio format",
    source: "Source audio",
    download: "Download on computer",
    rights:
      "Save audio you own or have permission to keep. Follow the license and SoundCloud terms.",
    speed: "Playback speed",
    queue: "Downloads",
    empty: "Your downloads will appear here.",
    save: "Save to phone",
    play: "Play",
    pause: "Pause",
    resume: "Resume",
    retry: "Retry",
    cancel: "Cancel",
    queued: "Queued",
    resolving: "Finding audio",
    downloading: "Downloading",
    paused: "Paused",
    processing: "Processing",
    verifying: "Verifying",
    completed: "Ready",
    failed: "Failed",
    cancelled: "Cancelled",
    untitled: "SoundCloud track",
    offline: "Cannot reach your computer. Reconnecting…",
    expired: "Pair this device with the code on your computer.",
    incorrect: "Check the code. Restart phone access on your computer for a new one.",
    sent: "Track added to your computer.",
    missing: "Paste a SoundCloud track link.",
    network: "Could not reach your computer. Try again.",
  },
  ar: {
    title: "مكتبتك الصوتية",
    pair: "إقران هذا الجهاز",
    instructions: "أدخل الرمز الذي يظهر على حاسوبك. يُستخدم الرمز مرة واحدة.",
    code: "رمز الاقتران",
    connect: "اتصال",
    add: "إضافة مقطع",
    link: "رابط SoundCloud أو رسالة المشاركة",
    format: "صيغة الصوت",
    source: "صيغة المصدر",
    download: "تنزيل على الحاسوب",
    rights: "احفظ الصوت الذي تملكه أو لديك إذن بحفظه. التزم بالترخيص وشروط SoundCloud.",
    speed: "سرعة التشغيل",
    queue: "التنزيلات",
    empty: "ستظهر تنزيلاتك هنا.",
    save: "حفظ على الهاتف",
    play: "تشغيل",
    pause: "إيقاف مؤقت",
    resume: "استئناف",
    retry: "إعادة المحاولة",
    cancel: "إلغاء",
    queued: "في الانتظار",
    resolving: "جارٍ البحث عن الصوت",
    downloading: "جارٍ التنزيل",
    paused: "متوقف مؤقتًا",
    processing: "جارٍ التحويل",
    verifying: "جارٍ التحقق",
    completed: "جاهز",
    failed: "تعذّر التنزيل",
    cancelled: "ملغى",
    untitled: "مقطع SoundCloud",
    offline: "تعذّر الوصول إلى الحاسوب. جارٍ إعادة الاتصال…",
    expired: "أدخل رمز الاقتران الظاهر على الحاسوب.",
    incorrect: "تحقق من الرمز. للحصول على رمز جديد أعد تشغيل وصول الهاتف على الحاسوب.",
    sent: "أُضيف المقطع إلى تنزيلات الحاسوب.",
    missing: "ألصق رابط مقطع على SoundCloud.",
    network: "تعذّر الوصول إلى الحاسوب. حاول مجددًا.",
  },
};
const el = (id) => document.getElementById(id);
let language =
  localStorage.getItem("language") || (navigator.language.startsWith("ar") ? "ar" : "en");
let lastJobs = [];
let request;
let connectionLost = false;
const t = (key) => languages[language]?.[key] ?? languages.en[key] ?? key;
const message = (value) => {
  el("status").textContent = value;
};
function translate() {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  document.querySelectorAll("[data-copy]").forEach((node) => {
    node.textContent = t(node.dataset.copy);
  });
  el("language").textContent = language === "ar" ? "English" : "العربية";
  render(lastJobs, true);
}
function paired(value) {
  el("pairing").hidden = value;
  el("library").hidden = !value;
  if (!value && !el("player").hidden) {
    el("audio").pause();
    el("audio").removeAttribute("src");
    el("audio").load();
    el("player").hidden = true;
  }
}
async function api(path, body) {
  const response = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const value = await response.json();
  if (!response.ok) {
    if (response.status === 401) paired(false);
    throw new Error(
      response.status === 401
        ? t("expired")
        : path === "/api/pair"
          ? t("incorrect")
          : value.error || t("network"),
    );
  }
  return value;
}
function actionButton(key, run) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = t(key);
  button.onclick = async () => {
    button.disabled = true;
    try {
      await run();
    } catch (err) {
      message(err.message || t("network"));
    } finally {
      button.disabled = false;
    }
  };
  return button;
}
function card(job) {
  const row = document.createElement("li");
  const name = document.createElement("strong");
  name.dir = "auto";
  name.textContent = job.title || t("untitled");
  const detail = document.createElement("div");
  detail.textContent = [job.artist, t(job.state), job.error?.message].filter(Boolean).join(" · ");
  row.append(name, detail);
  if (job.state === "downloading") {
    const bar = document.createElement("progress");
    bar.max = 100;
    if (Number.isFinite(job.progress)) bar.value = job.progress;
    bar.setAttribute("aria-label", t("downloading"));
    row.append(bar);
  }
  const controls = document.createElement("div");
  controls.className = "controls";
  if (job.state === "completed") {
    const save = document.createElement("a");
    save.className = "button";
    save.href = "/audio/" + job.id + "/save";
    save.download = "";
    save.textContent = t("save");
    controls.append(
      save,
      actionButton("play", async () => {
        el("player").hidden = false;
        el("playing").textContent = name.textContent;
        el("audio").src = "/audio/" + job.id + "/listen";
        el("audio").playbackRate = Number(el("rate").value);
        await el("audio").play();
      }),
    );
  } else if (job.state !== "cancelled") {
    const command = job.state === "failed" || job.state === "paused" ? "resume" : "pause";
    for (const key of job.state === "failed" ? [command] : [command, "cancel"]) {
      controls.append(
        actionButton(job.state === "failed" ? "retry" : key, async () => {
          await api("/api/jobs", { command: key, id: job.id });
          await refresh();
        }),
      );
    }
  }
  row.append(controls);
  return row;
}
function render(jobs, force = false) {
  const list = el("jobs");
  // Keep focused controls and the separate audio element intact on unchanged polls.
  if (!force && JSON.stringify(jobs) === JSON.stringify(lastJobs)) return;
  lastJobs = jobs;
  const existing = new Map([...list.children].map((row) => [row.dataset.id, row]));
  for (const [index, job] of jobs.entries()) {
    const stamp = JSON.stringify(job);
    let row = existing.get(job.id);
    if (force || !row || row.dataset.stamp !== stamp) {
      const next = card(job);
      next.dataset.id = job.id;
      next.dataset.stamp = stamp;
      if (row) row.replaceWith(next);
      row = next;
    }
    if (list.children[index] !== row) list.insertBefore(row, list.children[index] || null);
    existing.delete(job.id);
  }
  existing.forEach((row) => row.remove());
  el("empty").hidden = jobs.length > 0;
}
async function refresh() {
  try {
    const { jobs } = await api("/api/jobs");
    paired(true);
    render(jobs);
    if (connectionLost) {
      message("");
      connectionLost = false;
    }
  } catch (error) {
    if (!el("pairing").hidden) return;
    message(t("offline"));
    connectionLost = true;
  }
}
for (const [id, submit] of [
  [
    "pair-form",
    async () => {
      await api("/api/pair", { code: el("code").value.trim() });
      el("code").value = "";
      message("");
      await refresh();
    },
  ],
  [
    "track-form",
    async () => {
      const url = el("link").value.match(
        /https:\/\/(?:on\.|m\.|www\.)?soundcloud\.com\/[^\s<>"']+/i,
      )?.[0];
      if (!url) throw new Error(t("missing"));
      const format = el("format").value;
      if (!request || request.url !== url || request.format !== format)
        request = { command: "create", requestId: crypto.randomUUID(), url, format };
      await api("/api/jobs", request);
      request = undefined;
      el("link").value = "";
      message(t("sent"));
      await refresh();
    },
  ],
]) {
  el(id).onsubmit = async (event) => {
    event.preventDefault();
    const button = el(id).querySelector("button");
    if (button.disabled) return;
    button.disabled = true;
    try {
      await submit();
    } catch (err) {
      message(err.message || t("network"));
    } finally {
      button.disabled = false;
    }
  };
}
el("language").onclick = () => {
  language = language === "en" ? "ar" : "en";
  localStorage.setItem("language", language);
  message("");
  translate();
};
el("rate").onchange = () => {
  el("audio").defaultPlaybackRate = el("audio").playbackRate = Number(el("rate").value);
};
translate();
await refresh();
async function poll() {
  if (!document.hidden && el("pairing").hidden) await refresh();
  setTimeout(poll, 3500);
}
setTimeout(poll, 3500);
