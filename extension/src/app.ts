import { isSnapshot, type Command, type Job, type Reply, type Snapshot } from "./contracts.js";
import { language, setLanguage, t, type TextKey } from "./i18n.js";

const $ = <T extends HTMLElement>(selector: string): T => {
  const result = document.querySelector<T>(selector);
  if (!result) throw new Error(`Missing interface element: ${selector}`);
  return result;
};
const isPopup = location.pathname.endsWith("popup.html");
document.body.classList.toggle("popup", isPopup);
let snapshot: Snapshot | null = null;
let filter = "all";
let polling = false;
let connected = false;
let submitting = false;
let pendingRequest: { id: string; url: string; format: "original" | "mp3" } | null = null;
let toastTimer: ReturnType<typeof setTimeout>;

async function rpc<T>(command: Command | { action: string; url?: string }): Promise<T> {
  const reply: Reply<T> = await chrome.runtime.sendMessage(command);
  if (!reply?.ok)
    throw new Error(reply?.error?.message ?? "The companion returned an invalid response.");
  return reply.data;
}

function notice(text: string, error = false): void {
  const element = $("#notice");
  element.textContent = text;
  element.classList.toggle("error", error);
  element.hidden = false;
  clearTimeout(toastTimer);
  if (!error)
    toastTimer = setTimeout(() => {
      element.hidden = true;
    }, 6500);
}

function applyLanguage(): void {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  document.querySelectorAll<HTMLElement>("[data-text]").forEach((node) => {
    node.textContent = t(node.dataset["text"] as TextKey);
  });
  $("#url").setAttribute("placeholder", t("placeholder"));
  $("#jobs").replaceChildren();
  render();
}

function bytes(amount: number | null): string {
  if (amount === null) return "—";
  if (amount < 1e6) return `${(amount / 1e3).toFixed(0)} KB`;
  if (amount < 1e9) return `${(amount / 1e6).toFixed(1)} MB`;
  return `${(amount / 1e9).toFixed(2)} GB`;
}

function duration(seconds: number | null): string {
  if (!seconds) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h ? `${h}:${String(m).padStart(2, "0")} h` : `${m} ${t("minutes")}`;
}

function node<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  element.className = className;
  if (text) element.textContent = text;
  return element;
}

function stateLabel(job: Job): string {
  if (
    !["paused", "cancelled", "failed", "completed"].includes(job.state) &&
    job.desired !== "running"
  ) {
    return t(job.desired === "paused" ? "pausing" : "cancelling");
  }
  return t(job.state);
}

function renderJob(job: Job): HTMLElement {
  const article = node("article", `job ${job.state}`);
  article.dataset["id"] = job.id;
  const top = node("div", "job-top");
  const art = node("div", "track-art", "≋");
  art.setAttribute("aria-hidden", "true");
  const info = node("div", "track-info");
  info.append(
    node("h3", "track-title", job.title),
    node(
      "p",
      "track-meta",
      [job.artist, duration(job.duration), job.format === "mp3" ? "MP3" : job.codec?.toUpperCase()]
        .filter(Boolean)
        .join(" · "),
    ),
  );
  top.append(art, info, node("span", "state", stateLabel(job)));
  article.append(top);
  if (!["completed", "cancelled", "failed"].includes(job.state)) {
    const bar = node("progress", "progress");
    bar.max = 100;
    bar.setAttribute("aria-label", `${job.title}: ${stateLabel(job)}`);
    if (job.progress !== null) bar.value = job.progress;
    article.append(bar);
    const details =
      job.state === "processing"
        ? `${Math.floor(job.progress ?? 0)}%`
        : [
            bytes(job.bytes),
            job.total ? `/ ${bytes(job.total)}` : t("sizeUnknown"),
            job.speed ? `· ${bytes(job.speed)}/s` : "",
            job.eta ? `· ${duration(job.eta)}` : "",
          ].join(" ");
    article.append(node("div", "transfer-meta", details));
  }
  if (job.error) {
    article.append(node("p", "job-error", job.error.message));
    article.append(node("small", "error-code", job.error.code));
  } else if (job.note && job.state !== "completed") article.append(node("p", "job-note", job.note));
  const actions = node("div", "job-actions");
  const options: Array<["pause" | "resume" | "cancel" | "reveal", TextKey]> = [];
  if (["queued", "resolving", "downloading", "processing", "verifying"].includes(job.state))
    options.push(["pause", "pause"], ["cancel", "cancel"]);
  if (["paused", "failed"].includes(job.state))
    options.push(["resume", job.state === "failed" ? "retry" : "resume"], ["cancel", "cancel"]);
  if (job.state === "completed") options.push(["reveal", "reveal"]);
  for (const [command, label] of options) {
    const button = node("button", "text-button", t(label));
    button.type = "button";
    button.dataset["action"] = command;
    button.disabled =
      job.desired !== "running" && !["paused", "failed", "cancelled"].includes(job.state);
    button.addEventListener("click", () => {
      button.disabled = true;
      void rpc({ version: 1, command, id: job.id })
        .then(refresh)
        .catch((error: Error) => {
          button.disabled = false;
          notice(error.message, true);
        });
    });
    actions.append(button);
  }
  article.append(actions);
  return article;
}

function render(): void {
  const ready = connected && snapshot !== null && Object.values(snapshot.tools).every(Boolean);
  $("#connection").classList.toggle("online", ready);
  $("#connection-text").textContent = t(ready ? "connected" : "offline");
  $<HTMLButtonElement>("#submit").disabled = !ready || submitting;
  $("#submit-label").textContent = t(submitting ? "starting" : "download");
  $("#setup-banner").hidden = ready;
  $("#destination").textContent = snapshot?.outputDir ?? t("unknownFolder");
  $("#connection").title = snapshot ? `Companion ${snapshot.version}` : t("offline");
  const jobs = snapshot?.jobs ?? [];
  const active = jobs.filter(
    (job) => !["completed", "failed", "cancelled", "paused"].includes(job.state),
  );
  $("#active-count").textContent = String(active.length);
  $("#total-count").textContent = String(jobs.length);
  const visible = jobs.filter(
    (job) =>
      filter === "all" ||
      (filter === "done"
        ? job.state === "completed"
        : !["completed", "cancelled"].includes(job.state)),
  );
  const container = $("#jobs");
  const focus = document.activeElement as HTMLElement | null;
  const focusId = focus?.closest<HTMLElement>("[data-id]")?.dataset["id"];
  const focusAction = focus?.dataset["action"];
  // Rebuild only when data changes; restore keyboard focus for updated cards.
  const signature = JSON.stringify([visible, language]);
  if (container.dataset["signature"] !== signature) {
    container.replaceChildren(...visible.map(renderJob));
    container.dataset["signature"] = signature;
    if (focusId && focusAction)
      container
        .querySelector<HTMLElement>(
          `[data-id="${CSS.escape(focusId)}"] [data-action="${CSS.escape(focusAction)}"]`,
        )
        ?.focus();
  }
  $("#empty").hidden = visible.length > 0;
  $("#empty-title").textContent = t(jobs.length ? "noResults" : "emptyTitle");
  $("#empty-body").hidden = jobs.length > 0;
}

async function refresh(): Promise<void> {
  if (polling || document.hidden) return;
  polling = true;
  try {
    const data = await rpc<unknown>({ version: 1, command: "snapshot" });
    if (!isSnapshot(data))
      throw new Error("The companion returned an incompatible response. Update both components.");
    snapshot = data;
    connected = true;
    if (!Object.values(data.tools).every(Boolean)) notice(t("toolsMissing"), true);
  } catch {
    connected = false;
  } finally {
    polling = false;
    render();
  }
}

$("#download-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (submitting || !connected) return;
  const url = $<HTMLInputElement>("#url").value.trim();
  const format = $<HTMLInputElement>('input[name="format"]:checked').value as "original" | "mp3";
  if (!pendingRequest || pendingRequest.url !== url || pendingRequest.format !== format)
    pendingRequest = { id: crypto.randomUUID(), url, format };
  submitting = true;
  render();
  void rpc({ version: 1, command: "create", requestId: pendingRequest.id, url, format })
    .then(async () => {
      pendingRequest = null;
      notice(t("added"));
      await refresh();
    })
    .catch((error: Error) => notice(error.message, true))
    .finally(() => {
      submitting = false;
      render();
    });
});

$("#current-tab").addEventListener("click", () => {
  void rpc<string>({ action: "currentTab" }).then((url) => {
    if (/^https:\/\/(?:on\.|www\.|m\.)?soundcloud\.com\//.test(url))
      $<HTMLInputElement>("#url").value = url;
    else notice(t("noTab"), true);
  });
});
$("#open-workspace").addEventListener("click", () => {
  void rpc({ action: "dashboard", url: $<HTMLInputElement>("#url").value.trim() })
    .then(() => window.close())
    .catch((error: Error) => notice(error.message, true));
});
const dialog = $<HTMLDialogElement>("#setup-dialog");
document
  .querySelectorAll("[data-setup]")
  .forEach((button) => button.addEventListener("click", () => dialog.showModal()));
$("#close-setup").addEventListener("click", () => dialog.close());
$("#recheck").addEventListener("click", () => {
  void refresh();
});
$("#language").addEventListener("click", () => {
  setLanguage(language === "en" ? "ar" : "en");
  void chrome.storage.local.set({ language });
  applyLanguage();
});
document.querySelectorAll<HTMLButtonElement>("[data-filter]").forEach((button) =>
  button.addEventListener("click", () => {
    filter = button.dataset["filter"] ?? "all";
    document
      .querySelectorAll("[data-filter]")
      .forEach((tab) => tab.setAttribute("aria-pressed", String(tab === button)));
    render();
  }),
);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void refresh();
});
const preferences = await chrome.storage.local.get("language");
setLanguage(
  preferences["language"] === "ar" ||
    (!preferences["language"] && navigator.language.startsWith("ar"))
    ? "ar"
    : "en",
);
const track = new URLSearchParams(location.search).get("track");
if (track) $<HTMLInputElement>("#url").value = track;
$("#url").addEventListener("paste", (event) => {
  const paste = event as ClipboardEvent;
  const text = paste.clipboardData?.getData("text") ?? "";
  const urls = text.match(/https:\/\/(?:on\.|www\.|m\.)?soundcloud\.com\/[^\s<>"']+/g);
  if (urls?.length === 1 && urls[0]) {
    paste.preventDefault();
    $<HTMLInputElement>("#url").value = urls[0];
  }
});
applyLanguage();
await refresh();
setInterval(() => {
  void refresh();
}, 2000);
