(() => {
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
      (element) => !element.hidden && element.getAttribute("aria-hidden") !== "true"
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
    document.querySelectorAll("[data-drawer-background], .desktop-sidebar").forEach((element) => {
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
    const pauseAt = Number(shell.dataset.pauseSeconds || 0);
    let revealed = false;
    let pollTimer = null;

    function revealQuestion() {
      if (revealed || !question) return;
      revealed = true;
      if (pollTimer) window.clearInterval(pollTimer);
      question.hidden = false;
      revealButton.hidden = true;
      requestAnimationFrame(() => question.querySelector("input")?.focus());
    }

    function sendVideoCommand(func) {
      frame?.contentWindow?.postMessage(
        JSON.stringify({ event: "command", func, args: [] }),
        "*"
      );
    }

    window.addEventListener("message", (event) => {
      if (!frame || event.source !== frame.contentWindow) return;
      let payload;
      try {
        payload = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
      } catch (_error) {
        return;
      }
      const currentTime = payload?.info?.currentTime;
      if (!revealed && typeof currentTime === "number" && currentTime >= pauseAt) {
        sendVideoCommand("pauseVideo");
        revealQuestion();
      }
    });

    frame?.addEventListener("load", () => {
      frame.contentWindow?.postMessage(JSON.stringify({ event: "listening" }), "*");
      pollTimer = window.setInterval(() => {
        if (!revealed) sendVideoCommand("getCurrentTime");
      }, 500);
    });
    revealButton?.addEventListener("click", revealQuestion);
  });
})();
