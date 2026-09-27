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
})();
