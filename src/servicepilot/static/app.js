"use strict";
const $ = (id) => document.getElementById(id);
let current = null;
let busy = false;
const labels = {complete: "Terminé", approval_required: "Approbation requise", rejected: "Proposition refusée", error: "Erreur", running: "En cours"};

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"Content-Type": "application/json", Authorization: `Bearer ${$("token").value}`, ...options.headers}});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Requête invalide.");
  return data;
}
function showError(error) { $("error").textContent = error.message; $("error").hidden = false; }
function setBusy(value) {
  busy = value; $("busy").hidden = !value;
  for (const id of ["submit", "approve", "reject", "identity", "token", "new-run"]) $(id).disabled = value;
}
function node(tag, text, className) {
  const el = document.createElement(tag); el.textContent = text;
  if (className) el.className = className;
  return el;
}
function render(run) {
  current = run; $("result").hidden = false; $("empty").hidden = true;
  $("result-status").textContent = labels[run.status] || run.status;
  $("summary").textContent = run.answer?.summary || run.error || "Aucun résultat disponible.";
  $("actions").replaceChildren(...(run.answer?.recommended_actions || []).map((a) => node("li", a)));
  $("sources").replaceChildren();
  for (const source of run.answer?.sources || []) {
    const item = document.createElement("details"); item.className = "source";
    item.append(node("summary", source.title), node("p", source.excerpt)); $("sources").append(item);
  }
  if (!run.answer?.sources?.length) $("sources").append(node("p", "Aucune source documentaire citée.", "muted"));
  $("trace").replaceChildren();
  for (const event of run.trace) {
    const item = document.createElement("li");
    item.append(node("code", event.tool), node("span", `${event.outcome} · ${event.duration_ms} ms`, event.outcome));
    $("trace").append(item);
  }
  if (!run.trace.length) $("trace").append(node("li", "Aucun appel d'outil."));
  $("run-id").textContent = `RUN ${run.run_id}\nMode : ${run.mode}`;
  $("ticket-result").hidden = !run.ticket_id;
  $("ticket-result").textContent = run.ticket_id ? `Ticket créé : ${run.ticket_id}` : "";
  $("approval").hidden = run.status !== "approval_required";
  if (run.proposal) {
    $("proposal-title").textContent = run.proposal.draft.title;
    $("proposal-description").textContent = run.proposal.draft.description;
    $("proposal-meta").textContent = `${run.proposal.draft.service_id.toUpperCase()} · Priorité ${run.proposal.draft.priority} · Expire le ${new Date(run.proposal.expires_at * 1000).toLocaleString("fr-FR")}`;
    $("digest").textContent = run.proposal.digest;
  }
}
async function loadIdentity() {
  current = null; $("result").hidden = true; $("empty").hidden = false; $("error").hidden = true;
  try {
    const me = await api("/api/me"); $("scope").textContent = me.services.map((s) => s.toUpperCase()).sort().join(" · ");
    await history();
  } catch (e) { $("scope").textContent = "Connexion requise"; $("history").replaceChildren(); showError(e); }
}
async function history() {
  const runs = await api("/api/runs"); $("history").replaceChildren();
  for (const run of runs) {
    const button = node("button", run.answer?.summary?.slice(0, 40) || labels[run.status]);
    button.addEventListener("click", async () => {
      if (busy) return;
      try { render(await api(`/api/runs/${run.run_id}`)); } catch (e) { showError(e); }
    }); $("history").append(button);
  }
  if (!runs.length) $("history").append(node("span", "Aucun diagnostic pour le moment.", "muted"));
}
$("submit").addEventListener("click", async () => {
  if (busy) return;
  const query = $("query").value.trim();
  if (query.length < 3) { showError(new Error("Décrivez votre demande en quelques mots.")); return; }
  $("error").hidden = true; setBusy(true);
  try { render(await api("/api/runs", {method: "POST", body: JSON.stringify({query})})); await history(); }
  catch (e) { showError(e); } finally { setBusy(false); }
});
async function decide(approve) {
  if (!current?.proposal || busy) return;
  setBusy(true); $("error").hidden = true;
  try {
    render(await api(`/api/runs/${current.run_id}/decision`, {method: "POST", body: JSON.stringify({proposal_id: current.proposal.id, digest: current.proposal.digest, approve})}));
    await history();
  } catch (e) { showError(e); } finally { setBusy(false); }
}
$("approve").addEventListener("click", () => decide(true));
$("reject").addEventListener("click", () => decide(false));
$("new-run").addEventListener("click", () => { current = null; $("result").hidden = true; $("empty").hidden = false; $("query").value = ""; $("query").focus(); });
$("identity").addEventListener("change", () => { $("token").value = $("identity").value; loadIdentity(); });
$("token").addEventListener("change", loadIdentity);
document.querySelectorAll("[data-query]").forEach((b) => b.addEventListener("click", () => { $("query").value = b.dataset.query; $("query").focus(); }));
$("query").addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") $("submit").click(); });
(async () => {
  try {
    const config = await api("/api/config");
    $("mode").textContent = config.provider === "offline" ? "SIMULATION LOCALE · SANS LLM" : "AGENT LLM · OPENAI";
    $("embedding-note").textContent = config.embeddings === "hashing" ? "Recherche vectorielle lexicale" : "Embeddings sémantiques";
    for (const identity of config.demo_identities) {
      const option = node("option", `${identity.user_id} · démonstration`); option.value = identity.token; $("identity").append(option);
    }
    if (config.demo_identities.length) {
      $("identity").value = config.demo_identities[0].token; $("token").value = config.demo_identities[0].token; await loadIdentity();
    }
  } catch (e) { showError(e); }
})();
