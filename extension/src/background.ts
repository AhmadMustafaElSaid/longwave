import type { Command, Reply } from "./contracts.js";

const HOST = "app.longwave.companion";
const COMMANDS = new Set(["snapshot", "create", "pause", "resume", "cancel", "reveal"]);

chrome.runtime.onMessage.addListener((request: unknown, sender, respond) => {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL("")))
    return false;
  if (!request || typeof request !== "object") return false;
  const message = request as Record<string, unknown>;
  if (message["action"] === "currentTab") {
    void chrome.tabs
      .query({ active: true, lastFocusedWindow: true })
      .then((tabs) => {
        respond({ ok: true, data: tabs[0]?.url ?? "" });
      })
      .catch(() => respond({ ok: true, data: "" }));
    return true;
  }
  if (message["action"] === "dashboard") {
    const url = new URL(chrome.runtime.getURL("index.html"));
    if (
      typeof message["url"] === "string" &&
      /^https:\/\/(?:on\.|www\.|m\.)?soundcloud\.com\//.test(message["url"])
    ) {
      url.searchParams.set("track", message["url"]);
    }
    void chrome.tabs
      .create({ url: url.href })
      .then(() => respond({ ok: true, data: null }))
      .catch(() =>
        respond({
          ok: false,
          error: { code: "tab_failed", message: "The downloads workspace could not be opened." },
        }),
      );
    return true;
  }
  if (message["version"] !== 1 || !COMMANDS.has(String(message["command"]))) {
    respond({
      ok: false,
      error: { code: "invalid_request", message: "Unsupported extension request." },
    });
    return false;
  }
  void chrome.runtime
    .sendNativeMessage(HOST, message as unknown as Command)
    .then((reply: Reply<unknown>) => respond(reply))
    .catch(() =>
      respond({
        ok: false,
        error: {
          code: "companion_unavailable",
          message:
            "Connect the local companion to start downloading. Your queue stays on this computer.",
        },
      }),
    );
  return true;
});
