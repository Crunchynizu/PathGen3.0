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
  let modalInertTargets = [];

  function focusableElements(container) {
    return [...container.querySelectorAll(focusableSelector)].filter(
      (element) => element.tabIndex >= 0 && !element.hidden && element.getAttribute("aria-hidden") !== "true" && element.getClientRects().length > 0
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
    if (!activeLayer.contains(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    } else if (event.shiftKey && document.activeElement === first) {
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

  function inertOutsideDialog(dialog) {
    modalInertTargets = [];
    for (let child = dialog; child.parentElement; child = child.parentElement) {
      for (const sibling of child.parentElement.children) {
        if (sibling === child) continue;
        modalInertTargets.push([sibling, sibling.inert]);
        sibling.inert = true;
      }
    }
  }

  function restoreModalBackground() {
    modalInertTargets.forEach(([element, wasInert]) => { element.inert = wasInert; });
    modalInertTargets = [];
  }

  function activateLayer(layer, source) {
    activeLayer = layer;
    opener = source || (document.activeElement?.closest("dialog") ? null : document.activeElement);
    if (layer instanceof HTMLDialogElement) inertOutsideDialog(layer);
    document.addEventListener("keydown", trapFocus);
    requestAnimationFrame(() => {
      const first = focusableElements(layer)[0];
      (first || layer).focus();
    });
  }

  function deactivateLayer() {
    document.removeEventListener("keydown", trapFocus);
    if (activeLayer instanceof HTMLDialogElement) restoreModalBackground();
    activeLayer = null;
    const returnTarget = opener;
    opener = null;
    if (returnTarget) requestAnimationFrame(() => returnTarget.focus());
    if (drawerOpen && drawerElement) {
      activeLayer = drawerElement;
      opener = drawerOpener;
      document.addEventListener("keydown", trapFocus);
    }
  }

  const drawer = document.querySelector("[data-drawer-open]")?.getAttribute("aria-controls");
  const drawerElement = drawer ? document.getElementById(drawer) : null;
  const drawerOpener = document.querySelector("[data-drawer-open]");
  const drawerPanel = drawerElement?.querySelector("[data-drawer-panel]");
  const drawerScrim = drawerElement?.querySelector("[data-drawer-scrim]");
  const drawerDesktop = window.matchMedia("(min-width: 1024px)");
  const drawerReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const drawerWidth = 240;
  let drawerOpen = false;
  const drawerMotion = { value: -drawerWidth, velocity: 0, target: -drawerWidth, frame: null };

  function paintDrawer() {
    if (!drawerElement || !drawerPanel || !drawerScrim) return;
    const progress = Math.max(0, Math.min(1, 1 + drawerMotion.value / drawerWidth));
    drawerPanel.style.transform = `translateX(${drawerMotion.value}px)`;
    drawerScrim.style.opacity = String(progress * 0.4);
    drawerScrim.style.pointerEvents = progress > 0.02 ? "auto" : "none";
    drawerElement.style.pointerEvents = progress > 0.02 ? "auto" : "none";
    drawerOpener.style.opacity = String(1 - progress);
    drawerOpener.style.pointerEvents = progress > 0.5 ? "none" : "auto";
  }

  function stopDrawerMotion() {
    if (drawerMotion.frame) cancelAnimationFrame(drawerMotion.frame);
    drawerMotion.frame = null;
  }

  function finishDrawerMotion() {
    if (!drawerOpen && drawerElement) {
      drawerElement.hidden = true;
      drawerElement.style.pointerEvents = "none";
    }
  }

  function settleDrawer(target, velocity = 0) {
    stopDrawerMotion();
    drawerMotion.target = target;
    drawerMotion.velocity = velocity;
    if (drawerReducedMotion.matches) {
      drawerMotion.value = target;
      drawerMotion.velocity = 0;
      paintDrawer();
      finishDrawerMotion();
      return;
    }
    let previous = performance.now();
    const tick = (now) => {
      const dt = Math.min((now - previous) / 1000, 0.032);
      previous = now;
      const stiffness = (2 * Math.PI / 0.3) ** 2;
      const damping = 4 * Math.PI * 0.8 / 0.3;
      drawerMotion.velocity += (-stiffness * (drawerMotion.value - target) - damping * drawerMotion.velocity) * dt;
      drawerMotion.value += drawerMotion.velocity * dt;
      paintDrawer();
      if (Math.abs(drawerMotion.velocity) < 0.5 && Math.abs(drawerMotion.value - target) < 0.5) {
        drawerMotion.value = target;
        drawerMotion.velocity = 0;
        drawerMotion.frame = null;
        paintDrawer();
        finishDrawerMotion();
        return;
      }
      drawerMotion.frame = requestAnimationFrame(tick);
    };
    drawerMotion.frame = requestAnimationFrame(tick);
  }

  function openDrawer(velocity = 0) {
    if (!drawerElement || drawerDesktop.matches || drawerOpen) return;
    drawerOpen = true;
    drawerElement.hidden = false;
    drawerElement.inert = false;
    drawerOpener.setAttribute("aria-expanded", "true");
    setBackgroundInert(true);
    activateLayer(drawerElement, drawerOpener);
    drawerOpener.inert = true;
    settleDrawer(0, velocity);
  }

  function closeDrawer(velocity = 0) {
    if (!drawerElement || (!drawerOpen && drawerElement.hidden)) return;
    drawerOpen = false;
    drawerOpener.setAttribute("aria-expanded", "false");
    drawerOpener.inert = false;
    setBackgroundInert(false);
    if (activeLayer === drawerElement) deactivateLayer();
    drawerElement.inert = true;
    settleDrawer(-drawerWidth, velocity);
  }

  drawerOpener?.addEventListener("click", () => openDrawer());
  document.querySelectorAll("[data-drawer-close]").forEach((button) => {
    button.addEventListener("click", () => closeDrawer());
  });

  const projectDrawerMomentum = (velocity) => (velocity / 1000) * 0.998 / (1 - 0.998);
  const rubberbandDrawer = (offset) => (offset * drawerWidth * 0.55) / (drawerWidth + 0.55 * Math.abs(offset));
  function drawerGestureTarget(velocity) {
    if (Math.abs(velocity) > 500) return velocity < 0 ? -drawerWidth : 0;
    return drawerMotion.value + projectDrawerMomentum(velocity) < -drawerWidth / 2 ? -drawerWidth : 0;
  }

  let panelDrag = null;
  drawerPanel?.addEventListener("pointerdown", (event) => {
    if (!drawerOpen || drawerDesktop.matches || drawerReducedMotion.matches || event.target.closest("a, button, input, select, textarea")) return;
    panelDrag = { id: event.pointerId, x: event.clientX, y: event.clientY, start: drawerMotion.value, active: false, history: [{ x: event.clientX, t: performance.now() }] };
  });
  drawerPanel?.addEventListener("pointermove", (event) => {
    if (!panelDrag || panelDrag.id !== event.pointerId) return;
    const dx = event.clientX - panelDrag.x;
    const dy = event.clientY - panelDrag.y;
    if (!panelDrag.active) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      if (Math.abs(dy) > Math.abs(dx)) { panelDrag = null; return; }
      panelDrag.active = true;
      stopDrawerMotion();
      drawerPanel.setPointerCapture(event.pointerId);
    }
    let position = panelDrag.start + dx;
    if (position > 0) position = rubberbandDrawer(position);
    if (position < -drawerWidth) position = -drawerWidth - rubberbandDrawer(-drawerWidth - position);
    drawerMotion.value = position;
    paintDrawer();
    panelDrag.history.push({ x: event.clientX, t: performance.now() });
    if (panelDrag.history.length > 6) panelDrag.history.shift();
  });
  function finishPanelDrag(event) {
    if (!panelDrag || panelDrag.id !== event.pointerId) return;
    if (!panelDrag.active) { panelDrag = null; return; }
    const history = panelDrag.history;
    const elapsed = (history.at(-1).t - history[0].t) / 1000;
    const velocity = elapsed > 0 ? (history.at(-1).x - history[0].x) / elapsed : 0;
    const target = event.type === "pointercancel" ? 0 : drawerGestureTarget(velocity);
    panelDrag = null;
    if (target < 0) closeDrawer(velocity);
    else settleDrawer(0, velocity);
  }
  drawerPanel?.addEventListener("pointerup", finishPanelDrag);
  drawerPanel?.addEventListener("pointercancel", finishPanelDrag);

  document.addEventListener("pointerdown", (event) => {
    if (!drawerElement || drawerOpen || drawerDesktop.matches || drawerReducedMotion.matches || event.clientX > 24) return;
    if (event.target.closest("a, button, input, select, textarea")) return;
    const startX = event.clientX;
    const startY = event.clientY;
    const pointerId = event.pointerId;
    let active = false;
    const history = [{ x: startX, t: performance.now() }];
    const cleanup = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
      document.removeEventListener("pointercancel", end);
    };
    const move = (current) => {
      if (current.pointerId !== pointerId) return;
      const dx = current.clientX - startX;
      const dy = current.clientY - startY;
      if (!active) {
        if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
        if (Math.abs(dy) > Math.abs(dx) || dx < 0) { cleanup(); return; }
        active = true;
        stopDrawerMotion();
        drawerElement.hidden = false;
        drawerElement.inert = false;
      }
      let position = -drawerWidth + dx;
      if (position > 0) position = rubberbandDrawer(position);
      drawerMotion.value = position;
      paintDrawer();
      history.push({ x: current.clientX, t: performance.now() });
      if (history.length > 6) history.shift();
    };
    const end = (current) => {
      if (current.pointerId !== pointerId) return;
      cleanup();
      if (!active) return;
      const elapsed = (history.at(-1).t - history[0].t) / 1000;
      const velocity = elapsed > 0 ? (history.at(-1).x - history[0].x) / elapsed : 0;
      const target = current.type === "pointercancel" ? -drawerWidth : drawerGestureTarget(velocity);
      if (target === 0) openDrawer(velocity);
      else { drawerElement.inert = true; settleDrawer(-drawerWidth, velocity); }
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
    document.addEventListener("pointercancel", end);
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
  document.querySelectorAll("[data-dialog-confirm]").forEach((button) => {
    button.addEventListener("click", () => {
      const dialog = button.closest("dialog");
      if (dialog?.dispatchEvent(new CustomEvent("dialogconfirm", { bubbles: true, cancelable: true }))) {
        dialog.close();
      }
    });
  });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("close", deactivateLayer);
    dialog.addEventListener("cancel", (event) => {
      if (dialog.dataset.escapeClose === "false") event.preventDefault();
    });
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
  drawerDesktop.addEventListener?.("change", (event) => {
    if (!event.matches) return;
    const wasOpen = drawerOpen;
    closeDrawer();
    stopDrawerMotion();
    drawerMotion.value = -drawerWidth;
    paintDrawer();
    if (drawerElement) drawerElement.hidden = true;
    if (wasOpen) requestAnimationFrame(() => document.querySelector("aside[aria-label='Primary navigation'] a")?.focus());
  });

  const crumbsBar = document.querySelector("[data-ui~='crumbs-bar']");
  if (crumbsBar) {
    const syncScrollEdge = () => { crumbsBar.dataset.scrolled = String(window.scrollY > 4); };
    window.addEventListener("scroll", syncScrollEdge, { passive: true });
    syncScrollEdge();
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !(activeLayer instanceof HTMLDialogElement)) {
      if (drawerOpen) { event.preventDefault(); closeDrawer(); return; }
      const backLink = document.querySelector("[data-ui~='back-link']");
      if (backLink) { event.preventDefault(); backLink.click(); }
    }
  });

  document.querySelectorAll("[data-access-form]").forEach((form) => {
    const toggle = form.querySelector("[data-access-switch]");
    const value = form.querySelector("[data-switch-value]");
    const label = form.querySelector("[data-switch-label]");
    if (!toggle || !value || !label) return;
    toggle.addEventListener("click", () => {
      const enabled = toggle.getAttribute("aria-checked") !== "true";
      toggle.setAttribute("aria-checked", String(enabled));
      value.value = String(enabled);
      label.textContent = enabled ? "OPEN" : "CLOSED";
      toggle.classList.toggle("[background:var(--color-primary-subtle)]", enabled);
      toggle.classList.toggle("[color:var(--color-primary-hover)]", enabled);
      toggle.classList.toggle("[background:var(--color-bg-subtle)]", !enabled);
      toggle.classList.toggle("[color:var(--color-text-secondary)]", !enabled);
    });
  });

  document.querySelectorAll("[data-student-search]").forEach((search) => {
    const select = search.parentElement.querySelector('select[name="student"]');
    if (!select) return;
    search.addEventListener("input", () => {
      const term = search.value.trim().toLocaleLowerCase();
      [...select.options].forEach((option) => {
        if (!option.value) return;
        option.hidden = !option.textContent.toLocaleLowerCase().includes(term);
        if (option.hidden && option.selected) select.value = "";
      });
    });
  });

  document.querySelectorAll("[data-assessment-form]").forEach((form) => {
    const submit = form.querySelector("[data-answer-submit]");
    const choices = [...form.querySelectorAll('input[name="choice"]')];
    if (!submit || !choices.length) return;
    const sync = () => { submit.disabled = !choices.some((choice) => choice.checked); };
    choices.forEach((choice) => choice.addEventListener("change", sync));
    sync();
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

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    const input = document.getElementById(button.getAttribute("aria-controls"));
    if (!input) return;
    button.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-pressed", String(show));
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      button.innerHTML = `<i data-lucide="${show ? "eye-off" : "eye"}" aria-hidden="true"></i>`;
      window.refreshIcons?.();
    });
  });

  const feedback = document.querySelector("[data-feedback]");
  if (feedback) {
    // Keep the question and marked choices visible; bring the explanation into view.
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    requestAnimationFrame(() => {
      feedback.focus({ preventScroll: true });
      window.setTimeout(() => feedback.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "nearest" }), calm ? 0 : 350);
    });
  }

  function setupVideoCues(root = document) {
  root.querySelectorAll("[data-video-cue]").forEach((shell) => {
    if (shell.dataset.videoReady === "true") return;
    shell.dataset.videoReady = "true";
    const frame = shell.querySelector("[data-video-frame]");
    const question = shell.closest("form")?.querySelector("[data-video-question]");
    const revealButton = shell.querySelector("[data-reveal-question]");
    const start = Number(shell.dataset.segmentStartSeconds);
    const end = Number(shell.dataset.segmentEndSeconds);
    const requestedPause = Number(shell.dataset.pauseSeconds);
    const hasBounds = Number.isFinite(start) && Number.isFinite(end) && end > start;
    const pauseAt = shell.dataset.pauseSeconds && Number.isFinite(requestedPause)
      ? Math.max(start, Math.min(requestedPause, end)) : end;
    const origin = "https://www.youtube-nocookie.com";
    let revealed = false;
    let pollTimer = null;

    function revealQuestion() {
      if (revealed || !question) return;
      revealed = true;
      if (pollTimer) window.clearInterval(pollTimer);
      question.hidden = false;
      if (revealButton) revealButton.hidden = true;
      requestAnimationFrame(() => question.querySelector("input")?.focus());
    }

    function sendVideoCommand(func, args = []) {
      frame?.contentWindow?.postMessage(
        JSON.stringify({ event: "command", func, args }),
        origin
      );
    }

    if (!frame || !hasBounds) return;
    if (question) {
      question.hidden = true;
      if (revealButton) revealButton.hidden = false;
      window.setTimeout(revealQuestion, 12000);
    }

    window.addEventListener("message", (event) => {
      if (event.origin !== origin || event.source !== frame.contentWindow) return;
      let payload;
      try {
        payload = typeof event.data === "string" ? JSON.parse(event.data) : event.data;
      } catch (_error) {
        return;
      }
      if (payload?.event === "onError") { revealQuestion(); return; }
      if (payload?.event === "onReady") {
        sendVideoCommand("seekTo", [start, true]);
        sendVideoCommand("pauseVideo");
      }
      const currentTime = payload?.info?.currentTime ?? payload?.info?.currentTimeSeconds;
      if (typeof currentTime === "number" && currentTime >= pauseAt) {
        sendVideoCommand("pauseVideo");
        revealQuestion();
      }
      if (payload?.event === "onStateChange" && payload.info === 0) revealQuestion();
    });

    frame.addEventListener("load", () => {
      let attempts = 0;
      const listen = () => frame.contentWindow?.postMessage(JSON.stringify({ event: "listening" }), origin);
      listen();
      pollTimer = window.setInterval(() => {
        listen();
        if (++attempts >= 20 || revealed) window.clearInterval(pollTimer);
      }, 500);
    });
    const playerUrl = new URL(frame.src);
    playerUrl.searchParams.set("origin", window.location.origin);
    frame.src = playerUrl.toString();
    revealButton?.addEventListener("click", () => { sendVideoCommand("pauseVideo"); revealQuestion(); });
    window.addEventListener("pagehide", () => { if (pollTimer) window.clearInterval(pollTimer); }, { once: true });
  });
  }
  window.refreshVideoCues = setupVideoCues;
  setupVideoCues();
})();

window.refreshIcons = function () {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }
};

document.addEventListener("DOMContentLoaded", function () {
  window.refreshIcons();
});
