const $ = (id) => document.getElementById(id);
let chart;

async function call(path, method = "POST") {
  const btns = document.querySelectorAll("button");
  btns.forEach(b => b.disabled = true);
  $("status").textContent = "Working… (calling Groq)";
  try {
    const res = await fetch(path, { method });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    $("status").textContent = "Done.";
    render(data);
  } catch (e) {
    $("status").textContent = "⚠ " + e.message;
  } finally {
    btns.forEach(b => b.disabled = false);
  }
}

function render(s) {
  $("ctx-inplace").textContent = s.in_place.context || "(empty)";
  $("ctx-guard").textContent = s.dreamguard.context || "(empty)";

  const h = s.history;
  if (chart) chart.destroy();
  chart = new Chart($("chart"), {
    type: "line",
    data: {
      labels: h.map((x, i) => `${i + 1}. ${x.label}`),
      datasets: [
        { label: "In-place dreaming", data: h.map(x => x.in_place.accuracy), borderColor: "#ef4444", tension: .2, borderWidth: 2 },
        { label: "DreamGuard", data: h.map(x => x.dreamguard.accuracy), borderColor: "#10b981", tension: .2, borderWidth: 3 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#f8fafc" } } },
      scales: {
        y: { min: 0, max: 100, title: { display: true, text: "Questions answered correctly (%)", color: "#94a3b8" }, ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
        x: { ticks: { color: "#94a3b8" }, grid: { color: "#334155" } },
      },
    },
  });

  const tbody = document.querySelector("#results tbody");
  tbody.replaceChildren();
  const last = h[h.length - 1];
  $("eval-label").textContent = last ? `· ${last.label}` : "";
  if (!last) return;
  last.in_place.rows.forEach((r, i) => {
    const g = last.dreamguard.rows[i];
    const tr = document.createElement("tr");
    [[r.question, ""], [r.expected, ""], [r.answer, r.correct ? "ok" : "bad"], [g.answer, g.correct ? "ok" : "bad"]]
      .forEach(([t, c]) => { const td = document.createElement("td"); td.textContent = t; td.className = c; tr.append(td); });
    tbody.append(tr);
  });
}

// label each evaluation by what just happened
let lastAction = "baseline";
$("b-start").onclick = () => { lastAction = "baseline"; call("/api/live/start"); };
$("b-dream").onclick = () => { lastAction = "after dream"; call("/api/live/dream"); };
$("b-rollback").onclick = () => { lastAction = "after rollback"; call("/api/live/rollback"); };
$("b-eval").onclick = () => call("/api/live/evaluate?label=" + encodeURIComponent(lastAction));
