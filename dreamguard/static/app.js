const $ = (id) => document.getElementById(id);
let chart;

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    alert(msg);
    throw new Error(msg);
  }
  return res.json();
}
const post = (path, body) => api(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: body ? JSON.stringify(body) : undefined,
});

function line(cls, text) {
  const d = document.createElement("div");
  d.className = cls;
  d.textContent = text; // textContent: never inject user input as HTML
  return d;
}

async function refreshMemory() {
  const m = await api("/api/memory");
  const box = $("memory-list");
  box.replaceChildren();
  const covered = new Set(m.provenance.filter(p => m.facts.find(f => f.id === p.memory_id && f.active)).map(p => p.episode_id));
  m.facts.forEach(f => box.append(line("fact" + (f.active ? "" : " inactive"), `✦ ${f.fact}`)));
  m.episodes.forEach(e => box.append(line("episode" + (covered.has(e.id) ? " covered" : ""), `[turn ${e.turn}] ${e.content}`)));
  if (!m.facts.length && !m.episodes.length) box.append(line("empty", "No memory yet. Add some episodes."));
  const active = m.facts.filter(f => f.active).length;
  $("stats").textContent = `${m.episodes.length} raw episodes · ${active} active facts · agent context: ${m.context_chars} chars`;
}

async function runBenchmark() {
  const auto = $("auto").checked;
  const at = parseInt($("rollback-at").value, 10) || 40;
  const r = await api(`/api/benchmark?auto_rollback=${auto}&rollback_at=${at}`);
  const labels = r.rows.map(x => x.turn);
  const ds = [
    ["Full raw context (reference)", "raw_acc", "#64748b", [5, 5], 2],
    ["In-place dreaming", "in_place_acc", "#ef4444", [], 2],
    ["DreamGuard (reversible)", "dreamguard_acc", "#10b981", [], 3],
  ].map(([label, k, color, dash, w]) => ({
    label, data: r.rows.map(x => x[k]), borderColor: color, borderDash: dash,
    borderWidth: w, tension: 0.1, pointRadius: 0,
  }));
  if (chart) chart.destroy();
  chart = new Chart($("chart"), {
    type: "line",
    data: { labels, datasets: ds },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { color: "#f8fafc" } } },
      scales: {
        y: { min: 0, max: 100, title: { display: true, text: "Details recalled (%)", color: "#94a3b8" }, ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
        x: { title: { display: true, text: "Turn", color: "#94a3b8" }, ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
      },
    },
  });
}

$("btn-seed").onclick = async () => { await post("/api/demo/seed?n=10"); refreshMemory(); };
$("btn-dream").onclick = async () => { await post("/api/dream"); refreshMemory(); };
$("btn-rollback").onclick = async () => { await post("/api/rollback"); refreshMemory(); };
$("btn-reset").onclick = async () => { await post("/api/reset"); refreshMemory(); };
$("btn-bench").onclick = runBenchmark;
$("record-form").onsubmit = async (e) => {
  e.preventDefault();
  const v = $("record-input").value.trim();
  if (!v) return;
  await post("/api/record", { content: v });
  $("record-input").value = "";
  refreshMemory();
};

refreshMemory();
runBenchmark();
