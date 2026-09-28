(() => {
  const responsiveTableClasses = [
    "max-sm:[min-width:0]",
    "max-sm:[&_thead]:[position:absolute]",
    "max-sm:[&_thead]:[width:1px]",
    "max-sm:[&_thead]:[height:1px]",
    "max-sm:[&_thead]:[padding:0]",
    "max-sm:[&_thead]:[margin:-1px]",
    "max-sm:[&_thead]:[overflow:hidden]",
    "max-sm:[&_thead]:[clip:rect(0,_0,_0,_0)]",
    "max-sm:[&_thead]:[white-space:nowrap]",
    "max-sm:[&_thead]:[border:0]",
    "max-sm:[&_tbody]:[display:block]",
    "max-sm:[&_tbody]:[width:100%]",
    "max-sm:[&_tr]:[display:block]",
    "max-sm:[&_tr]:[width:100%]",
    "max-sm:[&_td]:[display:block]",
    "max-sm:[&_td]:[width:100%]",
    "max-sm:[&_tr]:[margin-bottom:0.75rem]",
    "max-sm:[&_tr]:[overflow:hidden]",
    "max-sm:[&_tr]:[border:1px_solid_var(--color-border)]",
    "max-sm:[&_tr]:[border-radius:0.75rem]",
    "max-sm:[&_tr]:[background:var(--color-surface)]",
    "max-sm:[&_td]:[display:grid]",
    "max-sm:[&_td]:[grid-template-columns:minmax(7rem,_40%)_minmax(0,_1fr)]",
    "max-sm:[&_td]:[gap:0.75rem]",
    "max-sm:[&_td]:[padding:0.75rem]",
    "max-sm:[&_td]:[overflow-wrap:anywhere]",
    "max-sm:[&_td::before]:[content:attr(data-label)]",
    "max-sm:[&_td::before]:[font-weight:700]",
    "max-sm:[&_td::before]:[color:var(--color-text-secondary)]",
  ];

  const focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  let activeLayer = null;
  let opener = null;

  function focusableElements(container) {
    return [...container.querySelectorAll(focusableSelector)].filter(
      (element) => !element.hidden && element.getAttribute("aria-hidden") !== "true" && element.getClientRects().length > 0
    );
  }

  function trapFocus(event) {
    if (!activeLayer || event.key !== "Tab") return;
    const elements = focusableElements(activeLayer);
    if (!elements.length) {
      event.preventDefault();
      activeLayer.focus();
      return;
    }
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function setBackgroundInert(inert) {
    document.querySelectorAll("[data-drawer-background], [data-ui~='desktop-sidebar']").forEach((element) => {
      element.inert = inert;
    });
  }

  function activateLayer(layer, source) {
    activeLayer = layer;
    opener = source || document.activeElement;
    document.addEventListener("keydown", trapFocus);
    requestAnimationFrame(() => {
      const first = focusableElements(layer)[0];
      (first || layer).focus();
    });
  }

  function deactivateLayer() {
    document.removeEventListener("keydown", trapFocus);
    activeLayer = null;
    const returnTarget = opener;
    opener = null;
    if (returnTarget) requestAnimationFrame(() => returnTarget.focus());
    if (drawerElement && !drawerElement.hidden) {
      activeLayer = drawerElement;
      opener = drawerOpener;
      document.addEventListener("keydown", trapFocus);
    }
  }

  const drawer = document.querySelector("[data-drawer-open]")?.getAttribute("aria-controls");
  const drawerElement = drawer ? document.getElementById(drawer) : null;
  const drawerOpener = document.querySelector("[data-drawer-open]");

  function closeDrawer() {
    if (!drawerElement || drawerElement.hidden) return;
    drawerElement.hidden = true;
    drawerOpener.setAttribute("aria-expanded", "false");
    setBackgroundInert(false);
    deactivateLayer();
  }

  drawerOpener?.addEventListener("click", () => {
    drawerElement.hidden = false;
    drawerOpener.setAttribute("aria-expanded", "true");
    setBackgroundInert(true);
    activateLayer(drawerElement, drawerOpener);
  });
  document.querySelectorAll("[data-drawer-close]").forEach((button) => {
    button.addEventListener("click", closeDrawer);
  });

  document.querySelectorAll("[data-dialog-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const dialog = document.getElementById(button.dataset.dialogOpen);
      if (!dialog) return;
      dialog.showModal();
      activateLayer(dialog, button);
    });
  });
  document.querySelectorAll("[data-dialog-close]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("close", deactivateLayer);
    dialog.addEventListener("cancel", deactivateLayer);
  });
  document.querySelectorAll("dialog[data-auto-open]").forEach((dialog) => {
    dialog.showModal();
    activateLayer(dialog, null);
  });

  document.querySelectorAll("[data-ui~='table-wrap'] table").forEach((table) => {
    const labels = [...table.querySelectorAll("thead th")].map((heading) =>
      heading.textContent.trim()
    );
    table.querySelectorAll("tbody tr").forEach((row) => {
      [...row.children].forEach((cell, index) => {
        if (!cell.dataset.label) cell.dataset.label = labels[index] || "Value";
      });
    });
    table.classList.add(...responsiveTableClasses);
  });

  const compactFilterQuery = window.matchMedia("(max-width: 639px)");
  function syncFilterDisclosures() {
    document.querySelectorAll("[data-ui~='filter-disclosure']").forEach((details) => {
      details.open = !compactFilterQuery.matches;
    });
  }
  syncFilterDisclosures();
  compactFilterQuery.addEventListener?.("change", syncFilterDisclosures);
  window.matchMedia("(min-width: 1024px)").addEventListener?.("change", (event) => {
    if (event.matches) closeDrawer();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawerElement && !drawerElement.hidden) closeDrawer();
  });

  document.querySelectorAll("[data-hint-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = button.parentElement.querySelector("[data-hint-panel]");
      const input = button.parentElement.querySelector("[data-hint-used]");
      if (!panel || !input) return;
      panel.hidden = false;
      input.value = "on";
      button.setAttribute("aria-expanded", "true");
      button.hidden = true;
      requestAnimationFrame(() => panel.focus?.());
    });
  });

  const feedback = document.querySelector("[data-feedback]");
  if (feedback) requestAnimationFrame(() => feedback.focus());

  document.querySelectorAll("[data-video-cue]").forEach((shell) => {
    const frame = shell.querySelector("[data-video-frame]");
    const question = shell.parentElement.querySelector("[data-video-question]");
    const revealButton = shell.querySelector("[data-reveal-question]");
    const hasCue = shell.dataset.pauseSeconds !== "" && Number.isFinite(Number(shell.dataset.pauseSeconds));
    const pauseAt = Number(shell.dataset.pauseSeconds);
    const origin = "https://www.youtube-nocookie.com";
    const videoId = shell.dataset.videoId || "";
    const validId = /^[A-Za-z0-9_-]{11}$/.test(videoId) && !/placeholder|^0{11}$|^x{11}$/i.test(videoId);
    let revealed = false;
    let pollTimer = null;

    function unavailable() {
      if (pollTimer) window.clearInterval(pollTimer);
      if (frame) frame.parentElement.hidden = true;
      shell.querySelector("[data-video-unavailable]").hidden = false;
    }

    function revealQuestion() {
      if (revealed || !question) return;
      revealed = true;
      if (pollTimer) window.clearInterval(pollTimer);
      question.hidden = false;
      if (revealButton) revealButton.hidden = true;
      requestAnimationFrame(() => question.querySelector("input")?.focus());
    }

    function sendVideoCommand(func) {
      frame?.contentWindow?.postMessage(
        JSON.stringify({ event: "command", func, args: [] }),
        origin
      );
    }

    window.addEventListener("message", (event) => {
      if (!frame || !validId || event.origin !== origin || event.source !== frame.contentWindow) return;
      let payload;
      try {
        payload = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
      } catch (_error) {
        return;
      }
      if (payload?.event === "onError") { unavailable(); return; }
      const currentTime = payload?.info?.currentTime;
      if (typeof currentTime === "number" && pollTimer) { window.clearInterval(pollTimer); pollTimer = null; }
      if (question && hasCue && !revealed && typeof currentTime === "number" && currentTime >= pauseAt) {
        sendVideoCommand("pauseVideo");
        revealQuestion();
      }
    });

    frame?.addEventListener("load", () => {
      if (!validId) return;
      let attempts = 0;
      const listen = () => frame.contentWindow?.postMessage(JSON.stringify({ event: "listening" }), origin);
      listen();
      pollTimer = window.setInterval(() => {
        listen();
        if (++attempts >= 20 || revealed) window.clearInterval(pollTimer);
      }, 500);
    });
    if (frame && validId) {
      frame.src = frame.dataset.src + "&origin=" + encodeURIComponent(window.location.origin);
      frame.parentElement.hidden = false;
      shell.querySelector("[data-video-unavailable]").hidden = true;
      shell.querySelector("[data-video-captions]").hidden = false;
    }
    revealButton?.addEventListener("click", () => { sendVideoCommand("pauseVideo"); revealQuestion(); });
    window.addEventListener("pagehide", () => { if (pollTimer) window.clearInterval(pollTimer); }, { once: true });
  });
})();

window.refreshIcons = function () {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }
};

document.addEventListener("DOMContentLoaded", function () {
  window.refreshIcons();
});
