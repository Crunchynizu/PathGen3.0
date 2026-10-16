(() => {
  if (typeof window.Chart === "undefined") return;

  const probe = document.createElement("span");
  probe.hidden = true;
  document.body.appendChild(probe);

  function tokenColor(token) {
    probe.style.color = `var(${token})`;
    return window.getComputedStyle(probe).color;
  }

  const palette = [
    tokenColor("--color-primary"),
    tokenColor("--color-warning"),
    tokenColor("--color-success"),
    tokenColor("--color-text-secondary"),
  ];

  document.querySelectorAll("canvas[data-dashboard-chart]").forEach((canvas) => {
    const payload = document.getElementById(canvas.dataset.dashboardChart);
    if (!payload) return;
    const config = JSON.parse(payload.textContent);
    config.data.datasets = config.data.datasets.map((dataset, index) => ({
      ...dataset,
      backgroundColor: palette[index % palette.length],
      borderColor: palette[index % palette.length],
      borderWidth: 1,
      borderRadius: 6,
    }));
    new window.Chart(canvas, config);
  });

  probe.remove();
})();
