const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {hold: 'Do not intervene', divert: 'Divert', brake: 'Emergency brake', conditional: 'Conditional'};
let context = null;
let contextId = '';
let readOnly = false;
let catalog = null;
let records = [];
let currentState = null;
let running = false;
let connection = {configured: false};
let loadSequence = 0;

const api = async (url, body) => {
  const response = await fetch(url, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The model request could not be completed.');
  return data;
};
const error = (message) => {$('model-error').textContent = message; $('model-error').hidden = !message;};
const selected = () => [...document.querySelectorAll('#model-options input:checked')].map(input => input.value).filter(id => catalog?.models.some(m => m.id === id && (m.kind === 'decision' || m.verified_free)));
const modelName = (id) => catalog?.models.find(m => m.id === id)?.name || id;

function updateControls() {
  const count = selected().length;
  $('model-run').disabled = running || readOnly || !context || !connection.configured || !count;
  $('model-framework').disabled = running;
  $('model-repeat').disabled = running;
  document.querySelectorAll('#model-options input').forEach(input => {
    const model = catalog?.models.find(m => m.id === input.value);
    input.disabled = running || readOnly || (model?.kind === 'llm' && !model.verified_free);
  });
  $('model-call-count').textContent = running ? 'Running selected models · at most two requests at a time'
    : readOnly ? 'Replay is read-only. Return to the live run to compare models.'
    : `${count} selected model${count === 1 ? '' : 's'} × 1 framework · up to ${count} API requests. Saved attempts are reused unless “New attempt” is selected.`;
  $('model-context').textContent = context
    ? `${context.scenario.title} · ${Object.keys(context.observed).length} disclosed facts · ${context.spent}/2 credits spent${context.finished ? ' · round closed; models still receive only budgeted evidence' : ''}`
    : 'Start an investigation first.';
  $('model-export').disabled = readOnly || !records.length;
}

function renderModels() {
  const previous = new Set(selected());
  const initial = !$('model-options').children.length;
  $('model-options').innerHTML = catalog.models.map((model, index) => `<label class="model-option ${model.kind === 'decision' ? 'paid-option' : ''}"><input type="checkbox" value="${esc(model.id)}" ${initial ? model.recommended && model.verified_free ? 'checked' : '' : previous.has(model.id) ? 'checked' : ''}><span><strong>${esc(model.name)}</strong><span class="model-kind">${model.kind === 'decision' ? 'Include paid Jev · $0.042/M input tokens · $0 output' : model.verified_free ? 'Verified free token pricing · quota applies' : 'Free endpoint unavailable or unverified'}</span><small>${esc(model.note)}</small></span></label>`).join('');
  $('unavailable-models').innerHTML = (catalog.unavailable_families || []).map(item => `<p><strong>${esc(item.name)}:</strong> ${esc(item.message)}</p>`).join('');
  $('model-pricing-note').textContent = catalog.limits_note;
  updateControls();
}

function renderConnection() {
  const quota = connection.quota;
  $('model-connection').textContent = !connection.configured
    ? 'Key missing. Set OPENROUTER_API_KEY in the server’s .env file, then refresh.'
    : connection.error ? connection.error.message
    : quota ? `Connected · ${quota.remaining} of ${quota.limit} free requests remaining today (UTC)`
    : 'Server key configured · refresh to check account quota.';
}

function recordCard(record) {
  const base = `<div class="model-result-top"><h3>${esc(modelName(record.model_id))}</h3><span class="status-pill">${esc(record.status)}</span></div><p class="model-record-meta">${esc(record.framework_id)} · evidence step ${record.step} · ${new Date(record.created_at).toLocaleTimeString()}</p>`;
  if (record.status === 'running') return `<article class="model-result">${base}<p>Request in progress. Refresh saved results if another session started it.</p></article>`;
  if (record.status !== 'ok') return `<article class="model-result model-failed">${base}<p>${esc(record.error?.message || 'Request failed.')}</p><p class="model-record-meta">${esc(record.error?.code)}${record.error?.retry_after ? ' · retry after ' + record.error.retry_after + ' seconds' : ''}. Select “New attempt” to retry explicitly.</p></article>`;
  const result = record.result;
  const answer = result.answer;
  const usage = result.usage || {};
  const cost = typeof usage.cost === 'number' ? '$' + usage.cost.toFixed(6) : 'Cost not reported';
  const tokens = (usage.prompt_tokens ?? usage.input_tokens ?? '?') + ' in / ' + (usage.completion_tokens ?? usage.output_tokens ?? '?') + ' out';
  const next = answer.next_question ? context?.facts.find(f => f.id === answer.next_question)?.title || answer.next_question : 'Stop asking';
  return `<article class="model-result">${base}<p class="model-decision">${esc(labels[answer.decision] || answer.decision)}</p><p class="model-next"><strong>Next question:</strong> ${esc(next)}</p><p class="model-explanation">${esc(answer.explanation || 'Jev returns typed decisions and probabilities; it does not generate an explanation.')}</p><div class="model-metrics"><span>${(result.duration_ms / 1000).toFixed(2)} s total</span><span>${esc(tokens)}</span><span>${esc(cost)}</span></div><div class="reference-check ${record.assessment.decision_matches ? 'matches' : 'mismatch'}">${esc(record.assessment.verdict)}</div>${!record.assessment.question_valid ? '<p class="model-warning">The suggested question is unknown, already revealed, or unaffordable.</p>' : ''}<p class="model-record-meta">Reference next question: ${esc(record.assessment.reference_next_question || 'Stop')} · this is an external check, not input to the model.</p>${answer.probabilities ? `<details class="model-details"><summary>Jev probability distributions</summary><pre>${esc(JSON.stringify(answer.probabilities, null, 2))}</pre><p>Provider probabilities are not validated measures of ethical correctness.</p></details>` : ''}<details class="model-details"><summary>Inspect provenance and supplied evidence</summary><p>Requested: ${esc(result.requested_model)}<br>Returned: ${esc(result.returned_model || 'Not reported')}<br>Provider: ${esc(result.provider || 'Not reported')}<br>Prompt: ${esc(record.prompt_version)}<br>Attempt: ${esc(record.id)}</p><pre>${esc(JSON.stringify(record.input, null, 2))}</pre><p>Request settings and prompt (no credentials):</p><pre>${esc(JSON.stringify(result.request, null, 2))}</pre></details></article>`;
}

function renderResults() {
  if (readOnly) {
    $('model-results').innerHTML = '<p class="model-empty">Return to the live run to view model comparisons. Replay does not show later model outputs.</p>';
    $('model-history').hidden = true;
    updateControls();
    return;
  }
  const framework = $('model-framework').value;
  const current = records.filter(r => r.state_key === currentState && r.framework_id === framework);
  const latest = new Map();
  for (const record of current) latest.set(record.model_id, record);
  $('model-results').innerHTML = [...latest.values()].map(recordCard).join('') || '<p class="model-empty">No model results for this evidence and framework yet. Select models and run a comparison.</p>';
  const older = records.filter(r => ![...latest.values()].some(item => item.id === r.id));
  $('model-history').hidden = !older.length;
  $('model-history-list').innerHTML = older.slice().reverse().map(recordCard).join('');
  $('model-history-count').textContent = older.length;
  updateControls();
}

async function loadHistory() {
  if (!context || readOnly) return;
  const identity = contextId;
  const sequence = ++loadSequence;
  try {
    const data = await api(`/api/runs/${context.id}/comparisons`);
    if (identity !== contextId || sequence !== loadSequence || readOnly) return;
    records = data.records; currentState = data.state_key; renderResults();
  } catch (exc) {if (identity === contextId) error(exc.message);}
}

export function updateModelContext(run, replaying) {
  const identity = run.id + ':' + run.events.length + ':' + run.finished;
  const changed = contextId !== identity || readOnly !== replaying;
  context = run; readOnly = replaying; contextId = identity;
  if (changed) {
    records = []; currentState = null; renderResults();
    if (!readOnly) void loadHistory();
  }
  updateControls();
}

export async function initializeModels() {
  try {
    [catalog, connection] = await Promise.all([api('/api/models'), api('/api/openrouter/status')]);
    renderModels(); renderConnection();
    if (catalog.catalog_error) error(catalog.catalog_error.message);
  } catch (exc) {error(exc.message);}
}

$('model-options').addEventListener('change', updateControls);
$('model-framework').addEventListener('change', renderResults);
$('model-history-refresh').addEventListener('click', () => {error(''); void loadHistory();});
$('model-refresh').addEventListener('click', async () => {
  $('model-refresh').disabled = true; error('');
  try {
    [catalog, connection] = await Promise.all([api('/api/models?refresh=true'), api('/api/openrouter/status?check_quota=true')]);
    renderModels(); renderConnection();
    if (catalog.catalog_error) error(catalog.catalog_error.message);
  } catch (exc) {error(exc.message);}
  finally {$('model-refresh').disabled = false;}
});
$('model-run').addEventListener('click', async () => {
  if (running || readOnly || !context) return;
  running = true; error(''); updateControls();
  const snapshot = {id: context.id, step: context.events.length, identity: contextId};
  const queue = selected();
  const framework = $('model-framework').value;
  const repeat = $('model-repeat').checked;
  let completed = 0;
  const worker = async () => {
    while (queue.length) {
      // A case/evidence change cancels unsent requests, not already submitted provider work.
      if (contextId !== snapshot.identity || readOnly) break;
      const modelId = queue.shift();
      try {
        await api(`/api/runs/${snapshot.id}/comparisons`, {model_id: modelId, framework_id: framework,
          evidence_step: snapshot.step, repeat, allow_paid_jev: modelId === 'typesafe/jev-1.13'});
        completed++;
        if (contextId === snapshot.identity && !readOnly) await loadHistory();
      } catch (exc) {if (contextId === snapshot.identity) error(exc.message);}
    }
  };
  try {await Promise.all([worker(), worker()]);}
  finally {
    running = false; $('model-repeat').checked = false; updateControls();
    $('model-progress').textContent = `${completed} request result${completed === 1 ? '' : 's'} recorded or reused. Failed attempts remain visible.`;
    try {connection = await api('/api/openrouter/status?check_quota=true'); renderConnection();} catch {}
  }
});
$('model-export').addEventListener('click', () => {
  if (context && !readOnly) window.location.href = `/api/runs/${context.id}/comparisons/export`;
});
