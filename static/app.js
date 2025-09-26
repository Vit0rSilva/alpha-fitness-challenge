// static/app.js
const api = "/api/data";
const pollInterval = 5000; 

let lastJSON = null;

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
    const res = await fetch(api, {cache: "no-store"});
    const data = await res.json();
    const payload = JSON.stringify(data.rows);
    if (!force && payload === lastJSON) {
      // sem alteração
      document.getElementById("status").innerText = "sem alterações";
    } else {
      lastJSON = payload;
      document.getElementById("table-container").innerHTML = makeTable(data.rows);
      const d = data.last_updated ? new Date(data.last_updated * 1000).toLocaleString() : "-";
      document.getElementById("last-updated").innerText = `Última atualização: ${d}`;
      document.getElementById("status").innerText = "atualizado";
    }
  } catch (e) {
    document.getElementById("status").innerText = "erro ao buscar dados";
    console.error(e);
  }
}

document.getElementById("refresh-btn").addEventListener("click", ()=> fetchAndRender(true));
fetchAndRender();
setInterval(fetchAndRender, pollInterval);
