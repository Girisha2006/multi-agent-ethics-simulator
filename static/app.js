import {initializeModels, updateModelContext} from './models.js';
const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const actionNames = {hold: 'Do not intervene', divert: 'Divert', brake: 'Emergency brake'};
let catalog;
let run;
let busy = false;
let strategy = "optimal";
let replay = null;
let replayTimer = null;
let liveRun = null;

const announce = (message) => { $('live-status').textContent = message; };
const showError = (message) => {
  $('error').textContent = message;
  $('error').hidden = false;
};
const api = async (path, method = 'GET', body) => {
  const response = await fetch(path, {method, headers: {'Content-Type': 'application/json'}, ...(body ? {body: JSON.stringify(body)} : {})});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be completed. Try again.');
  }
  return response.json();
};
const withBusy = async (operation) => {
  if (busy) return;
  busy = true;
  $('main').setAttribute('aria-busy', 'true');
  document.body.classList.add('busy');
  $('error').hidden = true;
  document.querySelectorAll('button[data-fact], #reset-button, #finish-button, .scenario-link').forEach((button) => { button.disabled = true; });
  let succeeded = false;
  try { await operation(); succeeded = true; } catch (error) { showError(error.message); }
  finally {
    busy = false;
    $('main').setAttribute('aria-busy', 'false');
    document.body.classList.remove('busy');
    if (run && !succeeded) render();
    else if (!run) document.querySelectorAll('.scenario-link').forEach((button) => {button.disabled = false;});
  }
};
const saveRunId = () => { try {localStorage.setItem('byd-run', run.id);} catch {} };
const chips = (actions) => actions.map((action) => `<span class="action-chip ${action}">${actionNames[action]}</span>`).join(' ');

const renderNavigation = () => {
  $('scenario-list').innerHTML = catalog.scenarios.map((scenario) => `<button class="scenario-link ${run?.scenario.id === scenario.id ? 'active' : ''}" data-scenario="${scenario.id}" ${run?.scenario.id === scenario.id ? 'aria-current="true"' : ''}><span class="nav-number">${scenario.number}</span><span>${escapeHtml(scenario.title)}<span class="nav-subtitle">${scenario.main} on course · ${scenario.side} on side track</span></span></button>`).join('');
};

const renderDiagram = () => {
  const s = run.scenario;
  const reliability = run.facts.find((f) => f.id === 'reliability');
  const p = s.mechanism === 'matching_relays' ? (['relay_a', 'relay_b'].every((key) => key in run.observed) ? `${Math.round((run.observed.relay_a === run.observed.relay_b ? s.high : s.low) * 100)}% rescue` : 'Relay pair unknown') : reliability?.revealed ? `${Math.round((run.observed.reliability ? s.high : s.low) * 100)}% rescue` : 'Reliability unknown';
  $('diagram').innerHTML = `<svg viewBox="0 0 460 220" role="img" aria-label="A trolley approaches ${s.main} people. Diversion exposes ${s.side} people on a side track."><defs><marker id="arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10" fill="none" stroke="#98b085" stroke-width="2"/></marker></defs><g fill="none" stroke="#5f735e" stroke-width="2"><path d="M35 82H366"/><path d="M35 92H366"/><path d="M161 87L237 160H366"/><path d="M156 95L232 170H366"/></g><path d="M128 87H166" stroke="#c0e985" stroke-width="2" marker-end="url(#arrow)"/><path d="M215 87H280" stroke="#839f77" stroke-width="2" stroke-dasharray="4 5" marker-end="url(#arrow)"/><rect x="58" y="66" width="53" height="33" rx="5" fill="#c0e985"/><rect x="66" y="72" width="14" height="10" rx="2" fill="#344528"/><rect x="87" y="72" width="14" height="10" rx="2" fill="#344528"/><circle cx="71" cy="99" r="5" fill="#131b15" stroke="#c0e985" stroke-width="2"/><circle cx="99" cy="99" r="5" fill="#131b15" stroke="#c0e985" stroke-width="2"/><circle cx="164" cy="90" r="6" fill="#101411" stroke="#c0e985" stroke-width="2"/><g class="diagram-text"><text x="57" y="48" fill="#aabca6" font-size="11">RUNAWAY TROLLEY</text><text x="210" y="64" fill="#b2bfb1" font-size="11">Current course</text><text x="207" y="198" fill="#b2bfb1" font-size="11">${escapeHtml(p)}</text><circle cx="379" cy="86" r="24" fill="#2a362b" stroke="#b8c9ac"/><text x="379" y="92" fill="#edf0e9" text-anchor="middle" font-size="22">${s.main}</text><text x="379" y="128" fill="#b2bfb1" text-anchor="middle" font-size="10">MAIN GROUP</text><circle cx="379" cy="165" r="20" fill="#3a3426" stroke="#c8b58a"/><text x="379" y="172" fill="#e4be84" text-anchor="middle" font-size="20">${s.side}</text><text x="379" y="204" fill="#b2bfb1" text-anchor="middle" font-size="10">SIDE GROUP</text></g></svg>`;
};

const renderFacts = () => {
  $('fact-cards').innerHTML = run.facts.map((fact, index) => {
    const locked = !fact.revealed && (fact.cost > run.remaining || run.finished || replay);
    return `<button class="fact-card ${fact.revealed ? 'revealed' : ''} ${locked ? 'locked' : ''}" data-fact="${fact.id}" ${fact.revealed || locked ? 'disabled' : ''} aria-label="${fact.revealed ? 'Revealed: ' + escapeHtml(fact.value) : 'Reveal: ' + escapeHtml(fact.question)}"><span class="fact-top"><span class="fact-number">F0${index + 1}</span><span class="fact-icon" aria-hidden="true">${fact.revealed ? '✓' : '+'}</span></span><span class="fact-title">${fact.title}</span><span class="fact-question">${escapeHtml(fact.revealed ? fact.value : fact.question)}</span><span class="fact-footer"><span>${fact.revealed ? 'Shared with all three agents' : locked ? 'Unavailable at this step' : 'Reveal fact'}</span><span aria-hidden="true">${fact.revealed ? '✓' : locked ? '—' : `${fact.cost} credit${fact.cost === 1 ? '' : 's'} →`}</span></span></button>`;
  }).join('');
};

const renderAgents = () => {
  $('strategy-description').textContent = strategy === 'optimal'
    ? 'Look ahead: maximize resolution within the remaining credits, then minimize expected cost.'
    : 'Choose the largest immediate information gain per credit. Stop at zero gain.';
  $('agent-cards').innerHTML = run.agents.map((agent, index) => {
    const plan = agent.optimal_plan;
    const question = strategy === 'optimal' ? (plan.fact_id ? plan : null) : agent.next_question;
    const scores = agent.question_scores.map((score) => `<li><span>${escapeHtml(score.title)} · ${score.cost} cr</span><span>${score.gain_per_credit.toFixed(3)} bits/cr</span></li>`).join('');
    const stopReason = agent.robust_actions.length ? 'A supported action remains the same across all possible answers.'
      : !run.remaining ? 'The agent keeps a conditional answer instead of guessing a missing fact.'
      : strategy === 'optimal' ? 'No affordable sequence can resolve the decision. Stop and keep the uncertainty visible.'
      : 'No affordable question has immediate information gain. A sequence may still help; compare the budget planner.';
    const branches = strategy === 'optimal' && question ? `<details class="plan-branches"><summary>Inspect the next step</summary><ul>${plan.branches.map((branch) => `<li><strong>If ${escapeHtml(branch.label)}:</strong> ${branch.plan.fact_id ? 'ask ' + escapeHtml(branch.plan.title) : branch.plan.resolved_probability === 1 ? 'stop — resolved' : 'stop — conditional'}.</li>`).join('')}</ul></details>` : '';
    return `<article class="agent-card ${agent.id}"><div class="agent-top"><span class="agent-number">AGENT 0${index + 1} / ${agent.short.toUpperCase()}</span><span class="status-pill ${agent.robust_actions.length ? 'resolved' : ''}">${agent.status}</span></div><div class="agent-main"><h3>${agent.name}</h3><p class="agent-principle">${escapeHtml(agent.principle)}</p><p class="decision-line">${agent.robust_actions.length ? agent.robust_actions.map((a) => actionNames[a]).join(' or ') : 'The answer is still conditional'}</p><div class="support-list">${Object.entries(agent.support).filter(([, count]) => count > 0).map(([action, count]) => `<span class="support-chip">${actionNames[action]}<strong>${count}/${agent.world_count}</strong></span>`).join('')}</div><p class="agent-explanation">${escapeHtml(agent.reason)}</p><details class="rule-details"><summary>Inspect rule and question scores</summary><p>${escapeHtml(agent.rule)}</p><ul class="score-list">${scores || '<li>All facts are known.</li>'}</ul></details></div><div class="agent-question"><span class="eyebrow">${question ? 'Would ask next' : agent.robust_actions.length ? 'No further question needed' : !run.remaining ? 'Credit budget closed' : 'Strategy stops here'}</span><p>${question ? escapeHtml(question.question) : stopReason}</p>${strategy === 'optimal' ? `<span class="gain">${Math.round(plan.resolved_probability * 100)}% resolution chance · ${plan.expected_cost.toFixed(2)} expected credits</span>` : question ? `<span class="gain">Immediate gain: ${question.gain.toFixed(3)} bits · ${question.cost} credit${question.cost === 1 ? '' : 's'}</span>` : ''}${branches}${question ? `<button class="button subtle" data-fact="${question.fact_id}" ${replay ? 'disabled' : ''}>Ask this question · ${question.cost} cr →</button>` : ''}</div></article>`;
  }).join('');
};

const renderAnalysis = () => {
  const analysis = run.analysis;
  $('analysis-summary').innerHTML = `<div class="analysis-body"><div><h3>${escapeHtml(analysis.title)}</h3><p>${escapeHtml(analysis.description)}</p></div><div class="world-meter"><div class="big">${analysis.agreement_worlds}<span> / ${analysis.total_worlds}</span></div><p>worlds with a shared action</p><div class="meter-track"><div class="meter-fill" style="width:${100 * analysis.agreement_worlds / analysis.total_worlds}%"></div></div></div></div>`;
  $('world-summary').textContent = `Inspect all ${analysis.total_worlds} remaining possible worlds`;
  $('world-table').innerHTML = `<table><caption class="sr-only">Every world consistent with disclosed facts, and each framework’s supported actions</caption><thead><tr><th>World</th>${run.facts.map((fact) => `<th>${escapeHtml(fact.title)}</th>`).join('')}<th>Utilitarian</th><th>Duty-based</th><th>Minimax risk</th><th>Shared action</th></tr></thead><tbody>${analysis.rows.map((row) => `<tr><td>W${row.id}</td>${run.facts.map((fact) => `<td>${escapeHtml(row.labels[fact.id])}</td>`).join('')}<td>${chips(row.actions.utility)}</td><td>${chips(row.actions.duty)}</td><td>${chips(row.actions.fairness)}</td><td>${row.shared_actions.length ? chips(row.shared_actions) : '<span class="agreement-text">None</span>'}</td></tr>`).join('')}</tbody></table>`;
};

const renderDebrief = () => {
  $('debrief').hidden = !run.finished;
  if (!run.finished) return;
  const d = run.debrief;
  $('debrief').innerHTML = `<span class="eyebrow accent">Full information · outside the budget</span><h2>The complete picture.</h2><p>The results above are frozen at the disclosure budget. These are the actual facts that were held on the server during this run.</p><div class="debrief-facts">${d.facts.map((f) => `<div><span class="eyebrow">${f.title}</span><p>${escapeHtml(f.value)}</p></div>`).join('')}</div><div class="debrief-results">${d.agents.map((agent) => `<div class="debrief-row"><span>${agent.name}</span><span>${chips(agent.robust_actions)}</span></div>`).join('')}</div><p>${escapeHtml(d.analysis.description)}</p><details class="world-details"><summary>Inspect full-information outcome calculations</summary><div class="table-scroll"><table><thead><tr><th>Available action</th><th>Main-group risk</th><th>Side-group risk</th><th>Expected deaths</th><th>Largest individual risk</th></tr></thead><tbody>${Object.entries(d.analysis.rows[0].outcomes).map(([action, o]) => `<tr><td>${actionNames[action]}</td><td>${Math.round(o.main_risk * 100)}%</td><td>${Math.round(o.side_risk * 100)}%</td><td>${o.expected_deaths.toFixed(2)}</td><td>${Math.round(o.max_risk * 100)}%</td></tr>`).join('')}</tbody></table></div></details>`;
};

const render = () => {
  if (!run) return;
  $('loading').hidden = true;
  $('investigation').hidden = false;
  $('export-button').disabled = false;
  $('reset-button').disabled = Boolean(replay);
  $('case-breadcrumb').textContent = `Case ${run.scenario.number}`;
  $('case-number').textContent = `CASE ${run.scenario.number}`;
  $('case-setting').textContent = run.scenario.setting;
  $('scenario-title').textContent = run.scenario.title;
  $('scenario-description').textContent = run.scenario.description;
  $('run-id').textContent = `RUN ${run.id.slice(0, 8).toUpperCase()}`;
  $('budget-used').textContent = run.spent;
  $('budget-status').textContent = run.finished ? 'Round closed · debrief available' : run.remaining ? 'Every reveal is shared with all agents' : 'Budget reached · inspect the debrief';
  $('reveal-hint').textContent = run.finished ? 'Investigation frozen at disclosure budget' : run.remaining ? `${run.remaining} credit${run.remaining === 1 ? '' : 's'} remaining` : 'No credits remaining';
  const s = run.scenario;
  $('outcome-model').innerHTML = `<p><strong>Do not intervene:</strong> every person in the main group dies; the side group is safe. <strong>Divert:</strong> the main group survives with the hidden rescue probability (${Math.round(s.low * 100)}% or ${Math.round(s.high * 100)}%); each person in the side group faces a ${Math.round(s.side_risk * 100)}% probability of death, whether rescue succeeds or fails.</p><p><strong>Emergency brake:</strong> ${s.fixed_alternative === true ? 'known to be available.' : s.fixed_alternative === false ? 'known to be unavailable.' : 'only available if its hidden fact is true.'} Each person in both groups then faces a ${Math.round(s.brake_risk * 100)}% probability of death. Braking never uses a person as a means. ${s.model_note ? escapeHtml(s.model_note) : 'The causal-role fact changes the duty constraint, not the numerical risks.'}</p><p>These are stipulated marginal risks. Expected-death calculations do not require independence between individuals. The three hidden facts are modeled as independent, equally likely binary values.</p>`;
  renderNavigation(); renderDiagram(); renderFacts(); renderAgents(); renderAnalysis(); renderDebrief(); renderReplay(); updateModelContext(run, Boolean(replay));
  $('finish-button').disabled = run.finished || Boolean(replay);
  $('finish-button').textContent = run.finished ? 'Round closed ✓' : 'Close round & open debrief →';
  $('finish-title').textContent = run.finished ? 'The investigation is recorded.' : 'See what the missing facts reveal.';
  $('finish-description').textContent = run.finished ? 'Export the record, or start a new run to try another question order.' : 'Close the round to compare your budgeted result with full information.';
  $('log-count').textContent = run.events.length;
  $('timeline-list').innerHTML = run.events.map((event) => `<li>${event.type === 'finish' ? 'Round closed. Full information opened outside the budget.' : `<strong>${run.facts.find((f) => f.id === event.fact_id).title}</strong> revealed to all agents. ${escapeHtml(run.facts.find((f) => f.id === event.fact_id).value)}`}<br><small>${new Date(event.at).toLocaleTimeString()}</small></li>`).join('') || '<li>No facts have been revealed yet.</li>';
};

const startRun = async (scenarioId) => {
  const nextRun = await api('/api/runs', 'POST', {scenario_id: scenarioId});
  stopReplayTimer(); replay = null; liveRun = null; run = nextRun;
  saveRunId(); render(); showTab('investigation'); announce(`Started ${run.scenario.title}. Two credits available.`);
};
const showTab = (name) => {
  for (const tab of ['investigation', 'benchmark', 'models']) {
    $(tab + '-panel').hidden = tab !== name;
    $(tab + '-tab').classList.toggle('active', tab === name);
    $(tab + '-tab').setAttribute('aria-selected', String(tab === name));
    $(tab + '-tab').tabIndex = tab === name ? 0 : -1;
  }
};

$('scenario-list').addEventListener('click', (event) => {
  const target = event.target.closest('[data-scenario]');
  if (target) withBusy(() => startRun(target.dataset.scenario));
});
$('investigation').addEventListener('click', (event) => {
  const target = event.target.closest('[data-fact]');
  if (!target || target.disabled || replay) return;
  const factId = target.dataset.fact;
  withBusy(async () => {
    const before = run;
    run = await api(`/api/runs/${run.id}/reveal`, 'POST', {fact_id: factId});
    render(); animateEvidence(before, run, factId);
    announce(`${run.facts.find((f) => f.id === factId).value}. ${run.remaining} credits remaining. All agents updated.`);
    // The revealed card is disabled. Move focus to the next available card or the debrief action.
    const next = document.querySelector('#fact-cards button:not(:disabled)') || $('finish-button');
    next.focus();
  });
});
$('reset-button').addEventListener('click', () => withBusy(() => startRun(run.scenario.id)));
$('finish-button').addEventListener('click', () => withBusy(async () => {
  if (replay) return;
  run = await api(`/api/runs/${run.id}/finish`, 'POST'); render(); announce('Round closed. Full-information debrief is available.');
  $('debrief').tabIndex = -1;
  $('debrief').focus({preventScroll: true});
  $('debrief').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center'});
}));
$('export-button').addEventListener('click', () => {if (run) window.location.href = `/api/runs/${run.id}/export`;});
$('method-button').addEventListener('click', () => $('method-dialog').showModal());
$('method-footer').addEventListener('click', () => $('method-dialog').showModal());
$('method-close').addEventListener('click', () => $('method-dialog').close());
$('method-dialog').addEventListener('click', (event) => {if (event.target === $('method-dialog')) {const rect = event.target.getBoundingClientRect();if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();}});
for (const tab of ['investigation', 'benchmark', 'models']) {
  $(tab + '-tab').addEventListener('click', () => showTab(tab));
  $(tab + '-tab').addEventListener('keydown', (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const tabs = ['investigation', 'benchmark', 'models'];
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[2] : tabs[(tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : 2)) % 3];
      showTab(next); $(next + '-tab').focus();
    }
  });
}
$('benchmark-run').addEventListener('click', async () => {
  const button = $('benchmark-run'); button.disabled = true; button.textContent = 'Enumerating worlds…'; $('error').hidden = true;
  try {
    const result = await api('/api/benchmark');
    const policies = [['optimal', 'Budget planner'], ['adaptive', 'Greedy gain'], ['random', 'Random affordable']];
    $('benchmark-results').innerHTML = `<div class="benchmark-grid">${result.results.map((row) => `<article class="benchmark-card"><h3>${row.framework}</h3>${policies.map(([key, label]) => `<div class="policy-result"><span class="eyebrow ${key === 'optimal' ? 'accent' : 'muted'}">${label}</span><div class="benchmark-stat">${(row[key].resolved_rate * 100).toFixed(1)}% <small>resolved</small></div><div class="benchmark-bar"><div class="benchmark-fill ${key === 'random' ? 'random' : ''}" style="width:${row[key].resolved_rate * 100}%"></div></div><p>${row[key].mean_credits.toFixed(2)} credits · ${row[key].mean_questions.toFixed(2)} questions on average</p></div>`).join('')}</article>`).join('')}</div><h3 class="case-results-heading">Where the strategies differ</h3><div class="table-scroll"><table id="case-results"><caption>Resolution rate by case and framework; mean credits in parentheses</caption><thead><tr><th>Case</th><th>Framework</th>${policies.map(([,label]) => `<th>${label}</th>`).join('')}</tr></thead><tbody>${result.per_case.map((entry) => entry.results.map((row) => `<tr data-case="${entry.scenario_id}"><td>${escapeHtml(entry.title)}</td><td>${row.framework}</td>${policies.map(([key]) => `<td>${(row[key].resolved_rate * 100).toFixed(1)}% <span class="muted">(${row[key].mean_credits.toFixed(2)} cr)</span></td>`).join('')}</tr>`).join('')).join('')}</tbody></table></div><p class="benchmark-method">${escapeHtml(result.method)}</p><p class="benchmark-method">“Resolved” means an action remains supported for every undisclosed factual completion. This pilot contains authored cases and is not a held-out validation study.</p>`;
    announce('Policy comparison complete. Results are displayed for all three frameworks.');
    button.textContent = 'Run again ↻';
  } catch (error) {showError(error.message);button.textContent = 'Retry comparison';}
  finally {button.disabled = false;}
});

const stopReplayTimer = () => {
  if (replayTimer !== null) clearInterval(replayTimer);
  replayTimer = null;
  $('replay-play').textContent = 'Play';
};

const renderReplay = () => {
  const possible = new Set(run.analysis.rows.map((row) => row.id));
  $('world-map').innerHTML = Array.from({length: run.analysis.universe_count}, (_, index) => {
    const id = index + 1;
    return `<div class="world-tile ${possible.has(id) ? 'possible' : 'excluded'}" data-world="${id}" aria-label="World ${id}: ${possible.has(id) ? 'possible' : 'ruled out'}"><span>W0${id}</span><strong aria-hidden="true">${possible.has(id) ? '○' : '×'}</strong></div>`;
  }).join('');
  $('replay-start').disabled = Boolean(replay) || !run.events.length;
  $('replay-controls').hidden = !replay;
  $('replay-status').textContent = replay
    ? `Replay · step ${replay.index} of ${replay.frames.length - 1}: ${replay.frames[replay.index].label}`
    : `Live run · ${possible.size} of ${run.analysis.universe_count} worlds remain possible`;
  $('evidence-flow').textContent = replay ? 'Read-only replay. Return to the live run to reveal another fact.' : 'Each disclosure reaches all three agents. Watch which possibilities remain.';
  document.querySelector('.replay-panel').classList.toggle('is-replaying', Boolean(replay));
  if (replay) {
    $('replay-prev').disabled = replay.index === 0;
    $('replay-next').disabled = replay.index === replay.frames.length - 1;
    $('replay-position').max = replay.frames.length - 1;
    $('replay-position').value = replay.index;
    $('replay-position').setAttribute('aria-valuetext', `Step ${replay.index}: ${replay.frames[replay.index].label}`);
  }
};

const animateEvidence = (before, after, factId) => {
  const previousIds = new Set(before.analysis.rows.map((row) => row.id));
  const currentIds = new Set(after.analysis.rows.map((row) => row.id));
  document.querySelectorAll('.world-tile').forEach((tile) => {
    if (previousIds.has(Number(tile.dataset.world)) && !currentIds.has(Number(tile.dataset.world))) tile.classList.add('just-eliminated');
  });
  if (!factId) return;
  const fact = after.facts.find((item) => item.id === factId);
  $('evidence-flow').innerHTML = `<span class="evidence-source">${escapeHtml(fact.title)}</span><span class="flow-arrow" aria-hidden="true">→</span><div class="flow-recipients">${after.agents.map((agent, i) => {
    const oldAgent = before.agents.find((item) => item.id === agent.id);
    const changed = JSON.stringify(oldAgent.robust_actions) !== JSON.stringify(agent.robust_actions);
    if (changed) document.querySelector('.agent-card.' + agent.id)?.classList.add('decision-changed');
    return `<span class="flow-recipient" style="--flow-delay:${i * 100}ms">${agent.short}: ${changed ? 'decision updated' : agent.status.toLowerCase()}</span>`;
  }).join('')}</div><span class="evidence-count">${before.analysis.total_worlds} → ${after.analysis.total_worlds} worlds</span>`;
};

const showReplayFrame = (index) => {
  if (!replay) return;
  const before = run;
  replay.index = Math.max(0, Math.min(index, replay.frames.length - 1));
  const frame = replay.frames[replay.index];
  run = frame.state;
  render();
  animateEvidence(before, run, frame.kind === 'reveal' ? frame.fact_id : null);
  announce($('replay-status').textContent);
  if (replay.index === replay.frames.length - 1) stopReplayTimer();
};

$('replay-start').addEventListener('click', () => withBusy(async () => {
  const data = await api(`/api/runs/${run.id}/replay`);
  liveRun = run;
  replay = {frames: data.frames, index: 0};
  showReplayFrame(0);
  $('replay-play').focus();
}));
$('replay-prev').addEventListener('click', () => {stopReplayTimer(); showReplayFrame(replay.index - 1);});
$('replay-next').addEventListener('click', () => {stopReplayTimer(); showReplayFrame(replay.index + 1);});
$('replay-position').addEventListener('input', (event) => {stopReplayTimer(); showReplayFrame(Number(event.target.value));});
$('replay-play').addEventListener('click', () => {
  if (!replay) return;
  if (replayTimer !== null) {stopReplayTimer(); return;}
  if (replay.index === replay.frames.length - 1) showReplayFrame(0);
  $('replay-play').textContent = 'Pause';
  replayTimer = setInterval(() => showReplayFrame(replay.index + 1), 1800);
});
$('replay-exit').addEventListener('click', () => {
  stopReplayTimer(); run = liveRun; liveRun = null; replay = null; render();
  announce('Returned to the live run.'); $('replay-start').focus();
});
for (const choice of ['optimal', 'greedy']) {
  $('strategy-' + choice).addEventListener('click', () => {
    strategy = choice;
    for (const key of ['optimal', 'greedy']) $('strategy-' + key).setAttribute('aria-pressed', String(key === strategy));
    renderAgents();
  });
}

const initialize = async () => {
  try {
    catalog = await api('/api/catalog');
    renderNavigation();
    $('method-frameworks').innerHTML = catalog.frameworks.map((f) => `<h3>${f.name}</h3><p>${escapeHtml(f.rule)}</p>`).join('');
    let previous;
    try {previous = localStorage.getItem('byd-run');} catch {}
    if (previous) {try {run = await api(`/api/runs/${encodeURIComponent(previous)}`);} catch { /* An old or deleted journal starts a fresh run. */ }}
    if (run) render(); else await startRun('junction');
  } catch (error) {
    $('loading').hidden = true;
    showError(`${error.message} Refresh the page to retry.`);
  }
};
document.querySelector('.contribution-panel').addEventListener('click', (event) => {
  const target = event.target.closest('[data-demo]');
  if (target) withBusy(async () => {
    await startRun(target.dataset.demo);
    $('scenario-title').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
  });
});
initialize();
void initializeModels();
