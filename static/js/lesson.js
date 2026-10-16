(() => {
  // Presentation only: lesson paging, number styling, and practice-free interactives.
  // Nothing here is submitted, stored on the server, or used by scoring/BKT.
  const reader = document.querySelector("[data-lesson-reader]");
  if (!reader) return;
  const content = reader.querySelector("[data-lesson-content]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  // ---------- helpers ----------
  const MINUS = "−";
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(className, text, icon) {
    const node = el("button", className);
    node.type = "button";
    if (icon) {
      const i = el("i");
      i.dataset.lucide = icon;
      i.setAttribute("aria-hidden", "true");
      node.append(i);
    }
    if (text) node.append(document.createTextNode(text));
    return node;
  }
  function num(n) {
    const span = el("span", n < 0 ? "num num-neg" : n > 0 ? "num num-pos" : "num num-zero");
    span.textContent = n < 0 ? `${MINUS}${Math.abs(n)}` : String(n);
    return span;
  }
  function say(target, ...parts) {
    target.replaceChildren(...parts.map((part) => (typeof part === "number" ? num(part) : document.createTextNode(part))));
  }
  const icons = () => window.refreshIcons?.();

  // ---------- 1. Spot the mistake ----------
  reader.querySelectorAll("[data-spot-mistake]").forEach((card) => {
    const textNode = card.querySelector("[data-mistake-text]");
    const match = textNode?.textContent.trim().match(/^(.+?) is wrong\.\s*([\s\S]*)$/);
    if (!match) return;
    const [, claim, why] = match;
    card.classList.add("is-quiz");
    const label = card.querySelector(".ls-mistake-label");
    if (label) label.lastChild.textContent = "Spot the mistake";
    const claimLine = el("p", "lw-claim", `“${claim}”`);
    const ask = el("p", "lw-ask", "Is this right?");
    const choices = el("div", "lw-guess");
    const yes = button("ui-btn ui-btn-secondary", "It's right", "thumbs-up");
    const no = button("ui-btn ui-btn-secondary", "It's wrong", "thumbs-down");
    choices.append(yes, no);
    const verdict = el("p", "lw-verdict");
    verdict.setAttribute("role", "status");
    const explain = el("p", "lw-why", `It's wrong. ${why}`);
    verdict.hidden = true;
    explain.hidden = true;
    textNode.replaceWith(claimLine, ask, choices, verdict, explain);
    const answer = (saidWrong) => {
      yes.disabled = true;
      no.disabled = true;
      (saidWrong ? no : yes).classList.add("is-chosen");
      card.dataset.result = saidWrong ? "good" : "oops";
      verdict.textContent = saidWrong ? "Good eye! You spotted it." : "Careful! This one is a trap.";
      verdict.hidden = false;
      explain.hidden = false;
      styleNumbers(explain);
    };
    yes.addEventListener("click", () => answer(false));
    no.addEventListener("click", () => answer(true));
  });

  // ---------- 2. Step-by-step reveal (worked examples, order of operations) ----------
  reader.querySelectorAll("[data-reveal-group]").forEach((group) => {
    const items = [...group.querySelectorAll("[data-reveal-item]")];
    if (items.length < 2) return;
    const label = group.dataset.revealLabel || "Show step";
    const finalLabel = group.dataset.revealFinal;
    const hint = group.querySelector("[data-reveal-hint]");
    if (hint) hint.hidden = false;
    let shown = 0;
    items.forEach((item) => { item.hidden = true; });
    const bar = el("div", "lw-reveal-bar");
    const nextBtn = button("ui-btn ui-btn-soft", "", "eye");
    const allBtn = button("lw-link-btn", "Show all");
    const nextText = document.createTextNode("");
    nextBtn.append(nextText);
    bar.append(nextBtn, allBtn);
    (group.tagName === "OL" ? group : items.at(-1)).after(bar);
    const sync = () => {
      const upcoming = items[shown];
      const isAnswer = upcoming?.hasAttribute("data-reveal-answer");
      nextText.textContent = isAnswer && finalLabel ? finalLabel : `${label} ${shown + 1}`;
      if (shown >= items.length) bar.remove();
    };
    const revealOne = () => {
      const item = items[shown];
      item.hidden = false;
      item.classList.add("is-revealed");
      shown += 1;
      sync();
      item.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "nearest" });
    };
    nextBtn.addEventListener("click", revealOne);
    allBtn.addEventListener("click", () => { while (shown < items.length) revealOne(); });
    sync();
  });

  // ---------- 3. Interactive figures ----------
  const widgets = {
    numberline(figure, stage) {
      const opposites = figure.dataset.mode === "opposites";
      let value = Number(figure.dataset.start || 0);
      const MIN = -8;
      const MAX = 8;
      const wrap = el("div", "lw-nl");
      const track = el("div", "lw-nl-track");
      const ticks = [];
      for (let n = MIN; n <= MAX; n += 1) {
        const tick = button("lw-tick");
        tick.dataset.n = String(n);
        tick.dataset.sign = n < 0 ? "neg" : n > 0 ? "pos" : "zero";
        tick.setAttribute("aria-label", `Choose ${n < 0 ? "negative " + Math.abs(n) : n}`);
        tick.append(el("span", "lw-tick-dot"), el("span", "lw-tick-label", n < 0 ? `${MINUS}${-n}` : String(n)));
        tick.addEventListener("click", () => set(n));
        ticks.push(tick);
        track.append(tick);
      }
      const arrows = el("div", "lw-nl-arrows");
      arrows.append(el("span", "lw-nl-left", "← smaller"), el("span", "lw-nl-right", "greater →"));
      const controls = el("div", "lw-controls");
      const less = button("ui-icon-btn", "", "minus");
      less.setAttribute("aria-label", "Move left");
      const more = button("ui-icon-btn", "", "plus");
      more.setAttribute("aria-label", "Move right");
      const readout = el("p", "lw-readout");
      readout.setAttribute("aria-live", "polite");
      controls.append(less, readout, more);
      less.addEventListener("click", () => set(value - 1));
      more.addEventListener("click", () => set(value + 1));
      wrap.append(track, arrows);
      stage.replaceChildren(wrap, controls);

      function set(next) {
        value = Math.max(MIN, Math.min(MAX, next));
        ticks.forEach((tick) => {
          const n = Number(tick.dataset.n);
          tick.classList.toggle("is-picked", n === value);
          tick.classList.toggle("is-mirror", opposites && value !== 0 && n === -value);
          tick.classList.toggle("is-span", opposites && value !== 0 && Math.abs(n) <= Math.abs(value) && n !== 0 && !(n === value || n === -value));
          tick.classList.toggle("is-greater", !opposites && n > value);
          tick.setAttribute("aria-pressed", String(n === value));
        });
        less.disabled = value === MIN;
        more.disabled = value === MAX;
        if (opposites) {
          if (value === 0) say(readout, 0, " is its own opposite, and |", 0, "| = ", 0, ".");
          else say(readout, value, " and ", -value, " are opposites. Each is ", Math.abs(value), " steps from 0, so the absolute value is ", Math.abs(value), ".");
        } else if (value < 0) {
          say(readout, value, " is ", -value, " steps left of 0, so it is less than 0. Everything to its right is greater.");
        } else if (value > 0) {
          say(readout, value, " is ", value, " steps right of 0, so it is greater than 0 and every negative number.");
        } else {
          say(readout, "0 is in the middle. It is neither positive nor negative.");
        }
      }
      set(value);
    },

    chips(figure, stage) {
      let negatives = Number(figure.dataset.negatives || 5);
      let positives = Number(figure.dataset.positives || 3);
      const MAX = 8;
      const wrap = el("div", "lw-chips");
      const counters = el("div", "lw-chip-counters");
      const expr = el("p", "lw-expr");
      const board = el("div", "lw-chip-board");
      const pairBtn = button("ui-btn ui-btn-primary ui-btn-block", "Make zero pairs", "link");
      const readout = el("p", "lw-readout");
      readout.setAttribute("aria-live", "polite");

      function counter(label, sign, get, setValue) {
        const box = el("div", "lw-counter");
        box.dataset.sign = sign;
        const minus = button("ui-icon-btn", "", "minus");
        minus.setAttribute("aria-label", `Fewer ${label}`);
        const plus = button("ui-icon-btn", "", "plus");
        plus.setAttribute("aria-label", `More ${label}`);
        const value = el("strong", "lw-counter-value");
        const name = el("span", "lw-counter-name", label);
        minus.addEventListener("click", () => { setValue(Math.max(0, get() - 1)); draw(); });
        plus.addEventListener("click", () => { setValue(Math.min(MAX, get() + 1)); draw(); });
        box.append(name, minus, value, plus);
        return { box, value, minus, plus };
      }
      const neg = counter("negative chips", "neg", () => negatives, (v) => { negatives = v; });
      const pos = counter("positive chips", "pos", () => positives, (v) => { positives = v; });
      counters.append(neg.box, pos.box);
      wrap.append(counters, expr, board, pairBtn, readout);
      stage.replaceChildren(wrap);

      function row(count, sign) {
        const line = el("div", "lw-chip-row");
        line.dataset.sign = sign;
        for (let i = 0; i < MAX; i += 1) {
          const chip = el("span", "lw-chip", sign === "neg" ? MINUS : "+");
          chip.classList.toggle("is-empty", i >= count);
          if (i >= count) chip.setAttribute("aria-hidden", "true");
          chip.style.setProperty("--i", String(i));
          line.append(chip);
        }
        return line;
      }
      function draw() {
        neg.value.textContent = String(negatives);
        pos.value.textContent = String(positives);
        neg.minus.disabled = negatives === 0;
        neg.plus.disabled = negatives === MAX;
        pos.minus.disabled = positives === 0;
        pos.plus.disabled = positives === MAX;
        say(expr, -negatives, " + ", positives, " = ?");
        board.replaceChildren(row(negatives, "neg"), row(positives, "pos"));
        board.classList.remove("is-paired");
        pairBtn.disabled = false;
        say(readout, "Each negative chip and positive chip together make zero. Tap the button to pair them.");
      }
      pairBtn.addEventListener("click", () => {
        const pairs = Math.min(negatives, positives);
        const [negRow, posRow] = board.children;
        for (let i = 0; i < pairs; i += 1) {
          negRow.children[i].classList.add("is-cancelled");
          posRow.children[i].classList.add("is-cancelled");
        }
        board.classList.add("is-paired");
        pairBtn.disabled = true;
        const result = positives - negatives;
        if (pairs === 0) say(readout, "No zero pairs here: all the chips have the same sign. The sum is ", result, ".");
        else if (result === 0) say(readout, `${pairs} pairs make zero and nothing is left, so the sum is `, 0, ".");
        else say(readout, `${pairs} ${pairs === 1 ? "pair makes" : "pairs make"} zero. ${Math.abs(result)} ${result < 0 ? "negative" : "positive"} ${Math.abs(result) === 1 ? "chip is" : "chips are"} left, so `, -negatives, " + ", positives, " = ", result, ".");
        say(expr, -negatives, " + ", positives, " = ", result);
      });
      draw();
    },

    signs(figure, stage) {
      const cells = [...stage.querySelectorAll(".lw-sign-cell")];
      const readout = el("p", "lw-readout", "Tap a box to see the sign of the answer.");
      readout.setAttribute("aria-live", "polite");
      cells.forEach((cell) => {
        const sign = cell.querySelector(".lw-sign");
        const example = cell.querySelector(".lw-sign-ex");
        const reveal = button("lw-sign-btn", "?");
        reveal.setAttribute("aria-label", `Reveal: ${cell.closest("[role=row]").firstElementChild.textContent} times ${["positive", "negative"][[...cell.parentElement.children].indexOf(cell) - 1]}`);
        cell.classList.add("is-hidden");
        cell.prepend(reveal);
        reveal.addEventListener("click", () => {
          cell.classList.remove("is-hidden");
          cell.classList.add("is-revealed");
          reveal.remove();
          readout.textContent = `${sign.textContent}: ${example.textContent}`;
          styleNumbers(readout);
        });
      });
      stage.append(readout);
    },

    order(figure, stage) {
      // Steps are revealed by the shared step-by-step reveal above; nothing else to build.
      if (!stage.querySelector("[data-reveal-item]")) throw new Error("no steps");
    },

    thermometer(figure, stage) {
      const start = Number(figure.dataset.start || 0);
      const change = Number(figure.dataset.change || 0);
      const MIN = -10;
      const MAX = 10;
      let temp = start;
      let timer = null;
      const wrap = el("div", "lw-thermo");
      const tube = el("div", "lw-thermo-tube");
      const fill = el("span", "lw-thermo-fill");
      const scale = el("div", "lw-thermo-scale");
      for (let t = MAX; t >= MIN; t -= 2) {
        const mark = el("span", "lw-thermo-mark", t < 0 ? `${MINUS}${-t}°` : `${t}°`);
        mark.dataset.zero = String(t === 0);
        scale.append(mark);
      }
      tube.append(fill, el("span", "lw-thermo-bulb"));
      const panel = el("div", "lw-thermo-panel");
      const big = el("p", "lw-thermo-now");
      big.setAttribute("aria-live", "polite");
      const go = button("ui-btn ui-btn-primary", `Rise by ${change}°`, "trending-up");
      const again = button("ui-btn ui-btn-secondary", "Start again", "rotate-ccw");
      again.hidden = true;
      const readout = el("p", "lw-readout");
      readout.setAttribute("aria-live", "polite");
      panel.append(big, go, again, readout);
      wrap.append(scale, tube, panel);
      stage.replaceChildren(wrap);

      function paint() {
        fill.style.height = `${((temp - MIN) / (MAX - MIN)) * 100}%`;
        fill.dataset.below = String(temp < 0);
        say(big, temp, " °C");
      }
      function reset() {
        if (timer) window.clearInterval(timer);
        temp = start;
        paint();
        go.hidden = false;
        again.hidden = true;
        say(readout, "At 7:00 AM it is ", start, " °C. What happens when it warms up by ", change, " degrees?");
      }
      go.addEventListener("click", () => {
        go.hidden = true;
        const target = start + change;
        const finish = () => {
          again.hidden = false;
          say(readout, start, " + ", change, " = ", target, ". The temperature went up past zero to ", target, " °C.");
        };
        if (reduceMotion.matches) { temp = target; paint(); finish(); return; }
        timer = window.setInterval(() => {
          temp += 1;
          paint();
          if (temp >= target) { window.clearInterval(timer); finish(); }
        }, 180);
      });
      again.addEventListener("click", reset);
      reset();
    },
  };

  reader.querySelectorAll("[data-widget]").forEach((figure) => {
    const build = widgets[figure.dataset.widget];
    const stage = figure.querySelector("[data-widget-stage]");
    if (!build || !stage) return;
    try {
      build(figure, stage);
      figure.classList.add("is-live");
    } catch (_error) { /* keep the plain-text fallback */ }
  });

  // ---------- 4. Signed-number colouring ----------
  // "-7" -> "−7" in orange, "+8" in teal. Only explicitly signed numbers; the sign stays visible.
  const SIGNED = /(^|[\s([{|=,:;“"])([-−+])(\d+(?:\.\d+)?)/g;
  const MATH_LINE = /^[\d\s()[\]{}|+\-−x×/÷=<>.,]+$/;
  const SKIP = "script, style, iframe, a, button, .ui-figure-missing, .ls-num, .num, .lw-nl, .lw-chip-board, .lw-thermo-scale";

  function prettifyOperators(text) {
    return text
      .replace(/(\d|\))\s+x\s+(?=[\d(−-])/g, "$1 × ")
      .replace(/(\d|\))\s+\/\s+(?=[\d(−-])/g, "$1 ÷ ");
  }

  function styleNumbers(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.nodeValue.trim() || node.parentElement.closest(SKIP)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const text = prettifyOperators(node.nodeValue);
      SIGNED.lastIndex = 0;
      if (!SIGNED.test(text)) {
        if (text !== node.nodeValue) node.nodeValue = text;
        return;
      }
      SIGNED.lastIndex = 0;
      const fragment = document.createDocumentFragment();
      let last = 0;
      for (const match of text.matchAll(SIGNED)) {
        const [whole, lead, sign, digits] = match;
        const start = match.index + lead.length;
        fragment.append(text.slice(last, start));
        const span = document.createElement("span");
        const negative = sign !== "+";
        span.className = negative ? "num num-neg" : "num num-pos";
        span.textContent = (negative ? MINUS : "+") + digits;
        fragment.append(span);
        last = match.index + whole.length;
      }
      fragment.append(text.slice(last));
      node.replaceWith(fragment);
    });
    root.querySelectorAll(".ls-list li > span, .ls-numbered li > span:last-child").forEach((item) => {
      if (MATH_LINE.test(item.textContent.trim())) item.classList.add("ls-math");
    });
  }
  if (content) styleNumbers(content);
  icons();

  // ---------- 5. One part at a time, with Back/Next and progress dots ----------
  const sections = [...reader.querySelectorAll("[data-lesson-section]")];
  const nav = reader.querySelector("[data-lesson-navigation]");
  const dotsList = reader.querySelector("[data-lesson-dots]");
  if (sections.length < 2 || !nav) return;

  const dots = [...reader.querySelectorAll("[data-lesson-dot]")];
  const prev = nav.querySelector("[data-lesson-prev]");
  const next = nav.querySelector("[data-lesson-next]");
  const count = nav.querySelector("[data-lesson-count]");
  const storageKey = `pathgen-lesson-part:${reader.dataset.lessonKey || ""}`;
  let current = 0;
  let furthest = 0;

  try {
    const saved = JSON.parse(window.sessionStorage.getItem(storageKey) || "null");
    if (saved && Number.isInteger(saved.current)) {
      current = Math.min(Math.max(saved.current, 0), sections.length - 1);
      furthest = Math.min(Math.max(saved.furthest || current, current), sections.length - 1);
    }
  } catch (_error) { /* storage unavailable: start at part 1 */ }

  function remember() {
    try { window.sessionStorage.setItem(storageKey, JSON.stringify({ current, furthest })); } catch (_error) { /* ignore */ }
  }

  function show(index, { focus = false, direction = 0 } = {}) {
    current = Math.min(Math.max(index, 0), sections.length - 1);
    furthest = Math.max(furthest, current);
    sections.forEach((section, i) => {
      const active = i === current;
      section.hidden = !active;
      section.classList.toggle("is-entering", active && direction !== 0 && !reduceMotion.matches);
      section.dataset.direction = direction < 0 ? "back" : "forward";
    });
    dots.forEach((dot, i) => {
      dot.dataset.state = i === current ? "current" : i <= furthest ? "seen" : "upcoming";
      if (i === current) dot.setAttribute("aria-current", "step");
      else dot.removeAttribute("aria-current");
    });
    prev.disabled = current === 0;
    next.disabled = current === sections.length - 1;
    count.textContent = String(current + 1);
    nav.dataset.last = String(current === sections.length - 1);
    remember();
    if (focus) {
      const heading = sections[current].querySelector("h2");
      reader.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "start" });
      heading?.focus({ preventScroll: true });
    }
  }

  reader.classList.add("is-paged");
  nav.hidden = false;
  if (dotsList) dotsList.hidden = false;
  prev.addEventListener("click", () => show(current - 1, { focus: true, direction: -1 }));
  next.addEventListener("click", () => show(current + 1, { focus: true, direction: 1 }));
  dots.forEach((dot) => {
    dot.addEventListener("click", () => {
      const target = Number(dot.dataset.lessonDot);
      show(target, { focus: true, direction: target >= current ? 1 : -1 });
    });
  });
  sections.forEach((section) => section.addEventListener("animationend", () => section.classList.remove("is-entering")));
  show(current);
})();
