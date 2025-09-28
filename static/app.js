// static/app.js
const api = "/api/data";
const apiStats = "/api/stats";
const pollInterval = 8000; // ms

let lastJSON = null;
let tsChart = null;

function makeTable(rows) {
  if (!rows || rows.length === 0) {
    return `<div class="alert alert-info">Nenhum registro encontrado.</div>`;
  }
  const cols = Object.keys(rows[0]);
  let html = `<table class="table table-striped table-hover small"><thead><tr>`;
  for (const c of cols) {
    html += `<th>${c}</th>`;
  }
  html += `</tr></thead><tbody>`;
  for (const r of rows) {
    html += `<tr>`;
    for (const c of cols) {
      const v = r[c];
      html += `<td>${v === null || v === undefined ? "" : escapeHtml(String(v))}</td>`;
    }
    html += `</tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function fetchAndRender(force=false) {
  try {
    document.getElementById("status").innerText = "buscando...";
    const search = document.getElementById("search-input").value.trim();
    const column = document.getElementById("column-select").value;
    const url = new URL(api, window.location.origin);
    if (search) url.searchParams.set("search", search);
    if (column) url.searchParams.set("column", column);
    const res = await fetch(url.toString(), {cache: "no-store"});
    const data = await res.json();
    const payload = JSON.stringify(data.rows);
    if (!force && payload === lastJSON) {
      document.getElementById("status").innerText = "sem alterações";
    } else {
      lastJSON = payload;
      document.getElementById("table-container").innerHTML = makeTable(data.rows);
      const d = data.last_updated ? new Date(data.last_updated * 1000).toLocaleString() : "-";
      document.getElementById("last-updated").innerText = `Última atualização: ${d}`;
      document.getElementById("status").innerText = "atualizado";
      if (data.rows && data.rows.length > 0) {
        populateColumnSelect(Object.keys(data.rows[0]));
      }
    }
  } catch (e) {
    document.getElementById("status").innerText = "erro ao buscar dados";
    console.error(e);
  }
}

function populateColumnSelect(cols) {
  const sel = document.getElementById("column-select");
  sel.innerHTML = `<option value="">Todas as colunas</option>`;
  for (const c of cols) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.text = c;
    sel.appendChild(opt);
  }
}

document.getElementById("search-btn").addEventListener("click", ()=> fetchAndRender(true));
document.getElementById("clear-btn").addEventListener("click", ()=> {
  document.getElementById("search-input").value = "";
  document.getElementById("column-select").value = "";
  fetchAndRender(true);
});
document.getElementById("refresh-btn").addEventListener("click", ()=> fetchAndRender(true));

fetchAndRender();
setInterval(fetchAndRender, pollInterval);

async function fetchStats() {
  try {
    const res = await fetch(apiStats, {cache: "no-store"});
    const j = await res.json();
    const s = j.stats;
    if (!s) return;
    renderDashboard(s);
  } catch(e) {
    console.error("erro stats", e);
  }
}

function renderDashboard(s) {
  const cards = document.getElementById("dashboard-cards");
  cards.innerHTML = "";

  const totalCard = cardHtml("Total", s.total_rows);
  cards.insertAdjacentHTML("beforeend", totalCard);

  const numericKeys = Object.keys(s.numeric_stats || {}).slice(0,4);
  for (const c of numericKeys) {
    const st = s.numeric_stats[c];
    let valueText = "";
    if (st.type === "identifier") {
      const ex = (st.examples && st.examples.length > 0) ? st.examples.join(", ") : "-";
      valueText = `tipo: identificador | únicos: ${st.unique} | exemplos: ${ex}`;
    } else {
      valueText = `média: ${fmt(st.mean)} | soma: ${fmt(st.sum)} | aus: ${st.missing}`;
    }
    const html = cardHtml(c, valueText);
    cards.insertAdjacentHTML("beforeend", html);
  }

  const missingCount = Object.values(s.missing_per_column || {}).reduce((a,b)=>a+b,0);
  cards.insertAdjacentHTML("beforeend", cardHtml("Total ausências", missingCount));

  const catDiv = document.getElementById("categorical-list");
  catDiv.innerHTML = "";
  if (s.categorical_summary && s.categorical_summary.length > 0) {
    let html = `<h6>Top valores (colunas categóricas)</h6>`;
    for (const item of s.categorical_summary) {
      html += `<div class="card mb-2"><div class="card-body small"> <strong>${item.column}</strong> (únicos: ${item.unique}) <div>`;
      const top = item.top;
      for (const k in top) {
        html += `<span class="badge bg-secondary me-1">${escapeHtml(k)}: ${top[k]}</span>`;
      }
      html += `</div></div></div>`;
    }
    catDiv.innerHTML = html;
  }

  const ctx = document.getElementById("tsChart").getContext("2d");
  if (s.timeseries_monthly && s.timeseries_monthly.length > 0) {
    const labels = s.timeseries_monthly.map(x => x.period);
    const data = s.timeseries_monthly.map(x => x.count);
    if (tsChart) tsChart.destroy();
    tsChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Registros por mês',
          data
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false
      }
    });
  } else {
    if (tsChart) tsChart.destroy();
    ctx.clearRect(0,0,ctx.canvas.width, ctx.canvas.height);
  }
}

function cardHtml(title, value) {
  return `<div class="card card-small me-2 mb-2">
    <div class="card-body p-2">
      <div class="small text-muted">${escapeHtml(String(title))}</div>
      <div class="h6 mb-0">${escapeHtml(String(value !== null && value !== undefined ? value : '-'))}</div>
    </div>
  </div>`;
}

function fmt(v) {
  return v === null || v === undefined ? "-" : Number(v).toFixed(2);
}

fetchStats();
setInterval(fetchStats, 15000);
