(() => {
  // Presentation adapter for the published source_text schema. Never writes learning state.
  const headings = new Set([
    "Objectives:", "What is an integer?", "The number line", "Opposites and absolute value",
    "Zero pairs", "Adding same signs", "Subtracting", "Multiplying and dividing", "Examples:",
    "A story about temperature", "Order of operations", "Words that mean signs",
    "Interpreting the result", "Worked example", "Common mistake", "Ready to practice",
  ]);
  const figures = {
    "lesson1/integer-number-line": "Integers on a number line",
    "lesson1/opposites-example": "Opposites and distance from zero",
    "lesson2/chip-model-zero-pairs": "Positive and negative chips forming zero pairs",
    "lesson2/sign-rules": "Sign rules for multiplying and dividing integers",
    "lesson3/operation-order-steps": "Order of operations: grouping, multiplication and division, addition and subtraction",
    "lesson3/temperature-change": "Temperature change from negative seven degrees by a rise of eight degrees",
  };
  const lessonReadingClasses = [
    "max-w-3xl", "leading-8", "[color:var(--color-text-secondary)]",
    "[&_p]:mb-4", "[max-width:65ch]", "[color:var(--color-text)]",
    "[line-height:var(--leading-normal)]", "[&_>_*_+_*]:[margin-top:1.5rem]",
    "[&_h2]:[padding-top:1rem]", "[&_p]:[margin-bottom:0]",
    "[&_ul]:[list-style:none]", "[&_ol]:[list-style:decimal]",
    "[&_ol]:[padding-left:1.5rem]", "[&_li_+_li]:[margin-top:0.5rem]",
    "[&_ul_li]:[display:flex]", "[&_ul_li]:[align-items:baseline]",
    "[&_ul_li]:[gap:0.5rem]", "[&_figure]:[padding:1rem]",
    "[&_figure]:[border:1px_solid_var(--color-border)]",
    "[&_figure]:[border-radius:var(--radius-lg)]",
    "[&_figure]:[background:var(--color-surface)]",
    "[&_figure_img]:[margin-inline:auto]", "[&_figure_img]:[max-height:24rem]",
    "[&_figure_img]:[object-fit:contain]", "[&_figcaption]:[margin-top:1rem]",
    "[&_figcaption]:[font-size:var(--text-sm)]",
    "[&_figcaption]:[color:var(--color-text-secondary)]",
    "[&_section_h2]:[padding-top:0]", "[&_section_>_*_+_*]:[margin-top:1rem]",
  ];
  const lessonExampleClasses = [
    "[padding:1.5rem]", "[border:1px_solid_var(--color-border)]",
    "[border-radius:var(--radius-lg)]", "[background:var(--color-surface)]",
    "[&_p]:[font-family:ui-monospace,_monospace]", "[&_p]:[overflow-wrap:anywhere]",
  ].join(" ");
  const lessonWarningClasses = [
    "[padding:1.5rem]", "[border:1px_solid_var(--color-border)]",
    "[border-radius:var(--radius-lg)]", "[background:var(--color-warning-subtle)]",
    "[border-color:var(--color-warning)]",
  ].join(" ");
  const mediaNoteClasses = "mt-2 leading-7 [color:var(--color-text-secondary)]";
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function icon(name) {
    const iconElement = element("i", "", "w-5 h-5 inline-block shrink-0 align-middle");
    iconElement.dataset.lucide = name === "triangle-alert" ? "alert-triangle" : name;
    iconElement.setAttribute("aria-hidden", "true");
    return iconElement;
  }
  document.querySelectorAll("[data-lesson-source]").forEach((source) => {
    const root = source.dataset.staticRoot;
    const fragment = document.createDocumentFragment();
    let container = fragment;
    let paragraph = null;
    let list = null;
    let bullet = false;
    let stop = false;
    const reset = () => { paragraph = null; list = null; };
    source.textContent.split(/\r?\n/).map((line) => line.trim()).forEach((line) => {
      if (!line || stop || /^Lesson \d|^Skills:/.test(line)) return;
      if (line === "Ready to practice" && source.closest("[data-lesson-reader]")) { stop = true; return; }
      if (headings.has(line)) {
        reset();
        container = fragment;
        if (line === "Worked example" || line === "Common mistake") {
          container = element("section", "", line === "Worked example" ? lessonExampleClasses : lessonWarningClasses);
          fragment.append(container);
        }
        const heading = element(line === "Examples:" ? "h3" : "h2", line.replace(/:$/, ""));
        if (line === "Common mistake") heading.prepend(icon("triangle-alert", root), " ");
        container.append(heading);
        return;
      }
      const figure = line.match(/^\[insert figure: ([a-z0-9/-]+)\]$/);
      if (figure && figures[figure[1]]) {
        reset();
        const node = element("figure");
        const img = element("img");
        img.src = `${root}lesson/${figure[1]}.png`;
        img.alt = figures[figure[1]];
        img.loading = "lazy";
        img.decoding = "async";
        node.append(img, element("figcaption", figures[figure[1]]));
        container.append(node);
        return;
      }
      const video = line.match(/^\[insert video: (VID-[A-Z-]+)\s*\|/);
      if (video) {
        reset();
        const template = [...document.querySelectorAll("template[data-lesson-video]")].find((node) => node.dataset.lessonVideo === video[1]);
        if (template) container.append(template.content.cloneNode(true));
        else container.append(element("p", "Optional video reference: " + video[1], mediaNoteClasses));
        return;
      }
      if (line === "-") { bullet = true; paragraph = null; return; }
      const numbered = line.match(/^\d+\.\s+(.+)$/);
      if (bullet || numbered) {
        const tag = numbered ? "OL" : "UL";
        if (!list || list.tagName !== tag) { list = element(tag); container.append(list); }
        const item = element("li");
        if (bullet) item.append(icon("check", root));
        item.append(element("span", numbered ? numbered[1] : line));
        list.append(item);
        paragraph = null;
        bullet = false;
        return;
      }
      list = null;
      if (paragraph && !/[.!?:]$/.test(paragraph.textContent)) paragraph.append(" " + line);
      else { paragraph = element("p", line); container.append(paragraph); }
    });
    source.replaceChildren(fragment);
    source.classList.add(...lessonReadingClasses);
    source.dataset.enhanced = "true";
    window.refreshIcons?.();
    window.refreshVideoCues?.(source);
  });

  const reader = document.querySelector("[data-lesson-reader]");
  if (!reader) return;
  const progress = reader.querySelector("progress");
  const label = reader.querySelector("[data-reading-percent]");
  const nav = reader.querySelector("[data-lesson-navigation]");
  const sections = [...reader.querySelectorAll("h1, h2")];
  let current = 0;
  let scheduled = false;
  function update() {
    scheduled = false;
    const rect = reader.getBoundingClientRect();
    const travel = Math.max(1, reader.offsetHeight - window.innerHeight);
    const percent = Math.round(Math.min(100, Math.max(0, -rect.top / travel * 100)));
    progress.value = percent;
    progress.textContent = `${percent}%`;
    label.textContent = `${percent}%`;
    sections.forEach((section, index) => { if (section.getBoundingClientRect().top <= 120) current = index; });
    nav.querySelector("[data-lesson-prev]").disabled = current === 0;
    nav.querySelector("[data-lesson-next]").disabled = current === sections.length - 1;
  }
  function navigate(direction) {
    current = Math.min(sections.length - 1, Math.max(0, current + direction));
    const section = sections[current];
    section.tabIndex = -1;
    section.focus({ preventScroll: true });
    section.scrollIntoView({ behavior: "auto", block: "start" });
    update();
  }
  reader.querySelector("[data-reading-progress]").hidden = false;
  nav.hidden = false;
  nav.querySelector("[data-lesson-prev]").addEventListener("click", () => navigate(-1));
  nav.querySelector("[data-lesson-next]").addEventListener("click", () => navigate(1));
  window.addEventListener("scroll", () => { if (!scheduled) { scheduled = true; requestAnimationFrame(update); } }, { passive: true });
  window.addEventListener("resize", update);
  reader.querySelectorAll("img").forEach((img) => img.addEventListener("load", update));
  update();
})();
