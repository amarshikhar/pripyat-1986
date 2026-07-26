/**
 * PRIPYAT-1986 Web Dashboard — Frontend
 * Real-time simulation visualization via WebSocket + Plotly.js
 */

// ── State ────────────────────────────────────────────────────────

const state = {
    playing: false,
    speed: 900,
    interventionEnabled: true,
    totalTicks: 0,
    currentTick: 0,
};

let dyatlovPhase = 0;
let customDyatlovIndex = -1;
let customDyatlovTimeout = null;
let currentDyatlovData = null;
let lastDyatlovQuote = null;

// Chart data arrays (historical + intervened traces)
const chartData = {
    timestamps: [],
    historical: { power: [], rods: [], coolant: [], steam: [], temp: [], radiation: [] },
    intervened: { power: [], rods: [], coolant: [], steam: [], temp: [], radiation: [] },
};

const MAX_POINTS = 2000;
let ws = null;
let logEntryCount = 0;
let speedDebounceTimer = null;
let currentWorkspace = 'simulation';
let selectedCaseId = null;

// Track which pipeline agents have been activated (persistent highlighting)
const pipelineActivated = { pipeS: false, pipeR: false, pipeD: false, pipeE: false, pipeC: false };

// ── WebSocket ────────────────────────────────────────────────────

function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => console.log('WebSocket connected');
    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(connect, 2000);
    };
    ws.onerror = (e) => console.error('WebSocket error:', e);

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'tick') handleTick(msg.data);
        else if (msg.type === 'state_update') handleStateUpdate(msg.data);
        else if (msg.type === 'simulation_complete') handleComplete(msg.data);
    };
}

// ── Tick Handler ─────────────────────────────────────────────────

function handleTick(data) {
    // Ignore broadcasts from the mode this client is not showing (another tab
    // can be driving the other one) — mixing them would corrupt the charts.
    if ((data.source === 'manual') !== manualMode) return;

    // Update time display
    const ts = data.timestamp;
    document.getElementById('simTime').textContent = ts.replace('T', ' ');

    const isManualTick = data.source === 'manual';

    if (!isManualTick) {
        // Progress + scrubber only mean something for the recorded timeline.
        document.getElementById('progressBar').style.width = data.progress_pct + '%';
        state.currentTick = data.tick;

        const scrubber = document.getElementById('scrubber');
        scrubber.max = state.totalTicks || 100;
        scrubber.value = data.tick;
        document.getElementById('scrubberTick').textContent = `Tick: ${data.tick} / ${state.totalTicks}`;
        document.getElementById('scrubberPct').textContent = data.progress_pct.toFixed(1) + '%';
    } else if (data.state.reactor_scrammed) {
        setManualStatus('SCRAMMED');
    }

    // Badges
    toggleBadge('scramBadge', data.state.reactor_scrammed);
    toggleBadge('evacBadge', data.state.evacuation_ordered);
    toggleBadge('divergedBadge', data.state.diverged);

    // Risk gauge
    const pending = data.pending_recommendations || [];
    updateRisk(data.risk_score, data.alert_level, data.decisions, data.state.reactor_scrammed, pending.length);
    renderRecommendations(pending);

    // Charts
    appendChartData(data);
    updateCharts();

    // Pipeline animation. Recommendation payloads carry no agent field, so a
    // pending case is what marks the decision stage as active.
    animatePipeline([...(data.decisions || []), ...(data.recommendations || [])], pending.length > 0);

    // LLM status
    if (data.llm_stats) updateLLMStatus(data.llm_stats);

    // Dyatlov override panel (skip in manual mode — operator IS the human)
    if (data.dyatlov && !manualMode) updateDyatlov(data.dyatlov);

    // Agent log
    if (data.decisions.length > 0) {
        addLogEntries(data.decisions, ts);
    }

    // History panel
    if (data.actual_event) {
        updateHistory(data.actual_event, data.actual_decision);
    }

    // Evacuation — show status even before evacuation is ordered
    if (data.evacuation_progress) {
        updateEvacuation(data.evacuation_progress);
    } else if (data.state.evacuation_ordered) {
        // Evacuation ordered but no progress data yet
        document.getElementById('evacContent').innerHTML = `
            <div class="evac-stat">
                <span class="evac-stat-label">Status</span>
                <span class="evac-stat-value" style="color:var(--yellow)">Evacuation Ordered — Mobilizing</span>
            </div>
        `;
    } else {
        // Show pre-evacuation status with risk context
        const riskLevel = data.alert_level || 'NORMAL';
        const statusText = riskLevel === 'EMERGENCY' ? 'Evacuation recommended — awaiting order'
            : riskLevel === 'CRITICAL' ? 'Monitoring — elevated risk'
            : riskLevel === 'WARNING' ? 'Monitoring — low risk'
            : 'Standby — no immediate threat';
        document.getElementById('evacContent').innerHTML = `
            <div class="evac-stat">
                <span class="evac-stat-label">Status</span>
                <span class="evac-stat-value">${statusText}</span>
            </div>
            <div class="evac-stat">
                <span class="evac-stat-label">Population</span>
                <span class="evac-stat-value">49,000</span>
            </div>
            <div class="evac-stat">
                <span class="evac-stat-label">Buses Available</span>
                <span class="evac-stat-value">1,200</span>
            </div>
            <div class="evac-stat">
                <span class="evac-stat-label">Alert Level</span>
                <span class="evac-stat-value">${riskLevel}</span>
            </div>
        `;
    }

    // Counterfactual
    if (data.counterfactual) {
        updateCounterfactual(data.counterfactual, data.state);
    }

    // Audit log
    if (data.audit_log) {
        handleAuditLog(data.audit_log);
    }
}

function handleStateUpdate(data) {
    // Timeline control state must not re-enable the replay controls while the
    // manual lab owns the console.
    if (manualMode) {
        state.playing = data.playing;
        state.totalTicks = data.total_ticks;
        return;
    }
    state.playing = data.playing;
    state.speed = data.speed;
    state.interventionEnabled = data.intervention_enabled;
    state.totalTicks = data.total_ticks;
    state.currentTick = data.current_tick;

    // Update UI
    const playBtn = document.getElementById('playBtn');
    playBtn.textContent = state.playing ? 'PAUSE' : 'PLAY';
    playBtn.classList.toggle('playing', state.playing);

    const slider = document.getElementById('speedSlider');
    if (document.activeElement !== slider) {
        slider.value = state.speed;
        document.getElementById('speedValue').textContent = state.speed + 'x';
    }

    const toggle = document.getElementById('interventionToggle');
    toggle.classList.toggle('on', state.interventionEnabled);

    // Set clock from first event timestamp if available (anchors to sim start)
    if (data.first_timestamp && state.currentTick === 0) {
        document.getElementById('simTime').textContent = data.first_timestamp.replace('T', ' ');
    }

    // Enable/disable scrubber
    document.getElementById('scrubber').disabled = state.playing;
    document.getElementById('scrubber').max = state.totalTicks || 100;
}

function handleComplete(report) {
    state.playing = false;
    document.getElementById('playBtn').textContent = 'PLAY';
    document.getElementById('playBtn').classList.remove('playing');

    // Update counterfactual with final report
    if (report.ai_timeline) {
        const cfContent = document.getElementById('cfContent');
        cfContent.innerHTML = `
            <div class="cf-cards">
                <div class="cf-card actual">
                    <div class="cf-card-title">What Happened (1986)</div>
                    <p><strong>Explosion:</strong> ${escapeHtml(report.actual_timeline?.explosion || 'Apr 26, 01:23:40')}</p>
                    <p><strong>Evacuation:</strong> 36 hours delayed</p>
                    <p><strong>Deaths:</strong> 31 immediate, ~4000 long-term</p>
                </div>
                <div class="cf-card ai">
                    <div class="cf-card-title">Governed Timeline</div>
                    <p><strong>SCRAM ordered:</strong> ${escapeHtml(report.ai_timeline.scram_ordered)}</p>
                    <p><strong>Evacuation:</strong> ${escapeHtml(report.ai_timeline.evacuation_hours_earlier ? report.ai_timeline.evacuation_hours_earlier + 'h earlier' : 'N/A')}</p>
                    <p><strong>Explosion prevented:</strong> ${report.ai_timeline.explosion_prevented ? 'YES' : 'NO'}</p>
                </div>
            </div>
        `;
    }
}

// ── Control Functions ────────────────────────────────────────────

function sendControl(action, value = null) {
    const body = { action };
    if (value !== null) body.value = value;
    fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
}

function togglePlay() {
    sendControl(state.playing ? 'pause' : 'play');
}

function stopSim() {
    sendControl('pause');
}

function resetSim() {
    // Clear chart data, including any buffered points that have not been
    // flushed yet — they would otherwise be drawn onto the fresh charts.
    clearChartBuffers();
    logEntryCount = 0;
    renderRecommendations([]);
    toggleBadge('scramBadge', false);
    toggleBadge('evacBadge', false);
    toggleBadge('divergedBadge', false);
    // Reset pipeline activation state
    Object.keys(pipelineActivated).forEach(k => pipelineActivated[k] = false);
    ['pipeS', 'pipeR', 'pipeD', 'pipeE', 'pipeC'].forEach(id => {
        document.getElementById(id).className = 'pipeline-node';
    });
    document.getElementById('agentLog').innerHTML = '<div class="empty-state">Waiting for simulation to start...</div>';
    document.getElementById('dyatlovPhase').textContent = 'CALM';
    document.getElementById('dyatlovPhase').style.color = 'var(--text-muted)';
    document.getElementById('dyatlovChatLog').innerHTML = '';
    lastDyatlovQuote = null;
    document.getElementById('dyatlovBarFill').style.width = '0%';
    document.getElementById('dyatlovPressureVal').textContent = '0';
    document.getElementById('dyatlovStats').textContent = 'Blocked: 0 | Delayed: 0 | Total: 0';
    document.getElementById('dyatlovResult').textContent = '';
    document.getElementById('cfContent').innerHTML = `
        <div class="cf-cards">
            <div class="cf-card actual">
                <div class="cf-card-title">What Happened</div>
                <p>Simulation not yet complete.</p>
            </div>
            <div class="cf-card ai">
                <div class="cf-card-title">What Governed Controls Prevent</div>
                <p>Waiting for agent intervention...</p>
            </div>
        </div>
    `;
    document.getElementById('historyContent').innerHTML = '<div class="empty-state">Events will appear as the simulation progresses...</div>';
    document.getElementById('evacContent').innerHTML = '<div class="empty-state">No evacuation order yet.</div>';
    lastScramAuthority = null;
    updateRisk(0, 'NORMAL', [], false);
    initCharts();
    resetAuditLog();
    sendControl('reset');
}

function setSpeed(val) {
    document.getElementById('speedValue').textContent = val + 'x';
    clearTimeout(speedDebounceTimer);
    speedDebounceTimer = setTimeout(() => {
        sendControl('set_speed', parseInt(val));
    }, 150);
}

function toggleIntervention() {
    sendControl('toggle_intervention');
}

function seekTo(val) {
    if (!state.playing) {
        sendControl('seek', parseInt(val));
    }
}

// ── Manual Control Mode ──────────────────────────────────────────

let manualMode = false;
let manualSessionLive = false;   // A server-side lab session exists (maybe paused)
let manualEccsActive = true;
let manualTickTimer = null;      // Handle for the next scheduled tick
let manualTickInFlight = false;  // Guards against overlapping requests
const MANUAL_TICK_RATE_MS = 1000;  // Must match MANUAL_TICK_SECONDS in web.py
const MANUAL_DEFAULTS = { rods: 100, coolant: 8000 };

/** Enter the manual lab, starting a fresh physics session if none is running. */
function enterManualMode() {
    if (manualMode) return;
    manualMode = true;

    // The timeline replay and the manual lab must never tick at the same time.
    sendControl('pause');
    document.getElementById('manualBtn').classList.add('active');
    document.getElementById('manualPanel').style.display = 'block';
    setTimelineChromeVisible(false);

    if (manualSessionLive) {
        // Resuming after a detour through the case/audit views.
        setManualStatus('LIVE');
        scheduleManualTick(0);
        return;
    }
    startManualSession();
}

/** Wipe the lab back to a cold, safe reactor and start ticking. */
async function startManualSession() {
    manualSessionLive = true;
    stopManualTicks();

    // Charts restart empty with exactly one live trace — the manual lab has no
    // counterfactual timeline to compare against.
    clearChartBuffers();
    initCharts();

    resetManualControlsToDefaults();
    logEntryCount = 0;
    document.getElementById('agentLog').innerHTML = '<div class="empty-state">Manual control armed — move a lever.</div>';
    resetAuditLog();
    renderRecommendations([]);
    lastScramAuthority = null;
    updateRisk(0, 'NORMAL', [], false);
    toggleBadge('scramBadge', false);
    toggleBadge('evacBadge', false);
    updateLLMStatus({ llm_available: true, total_calls: 0, total_failures: 0, avg_latency_ms: 0, last_call_ok: false, last_call_time: null });

    // Discard any previous lab session server-side before the first tick.
    try {
        await fetch('/api/manual_reset', { method: 'POST' });
    } catch (e) {
        console.error('Manual reset failed:', e);
    }
    scheduleManualTick(0);
}

/** Pause the lab but keep the session so its cases stay reviewable. */
function pauseManualMode() {
    if (!manualMode) return;
    manualMode = false;
    stopManualTicks();
    document.getElementById('manualBtn').classList.remove('active');
    document.getElementById('manualPanel').style.display = 'none';
    setTimelineChromeVisible(true);
    setManualStatus('PAUSED');
}

/** Discard the lab session and hand the charts back to the replay. */
function endManualSession() {
    manualSessionLive = false;
    stopManualTicks();
    fetch('/api/manual_reset', { method: 'POST' }).catch(e => console.error('Manual reset failed:', e));
    clearChartBuffers();
    initCharts();
    renderRecommendations([]);
}

/** Show/hide the parts of the dashboard that only mean something in replay. */
function setTimelineChromeVisible(visible) {
    document.getElementById('dyatlovSection').style.display = visible ? '' : 'none';
    document.querySelector('.history-panel').style.display = visible ? '' : 'none';
    document.querySelector('.counterfactual-panel').style.display = visible ? '' : 'none';
    document.querySelector('.scrubber-container').style.display = visible ? '' : 'none';
    document.getElementById('divergedBadge').style.display = visible ? '' : 'none';
    ['playBtn', 'stopBtn', 'resetBtn', 'scrubber', 'speedSlider'].forEach(id => {
        document.getElementById(id).disabled = !visible;
    });
    updateChartLegends();
}

function resetManualControlsToDefaults() {
    document.getElementById('rodsSlider').value = MANUAL_DEFAULTS.rods;
    document.getElementById('coolantSlider').value = MANUAL_DEFAULTS.coolant;
    document.getElementById('rodsVal').textContent = MANUAL_DEFAULTS.rods;
    document.getElementById('coolantVal').textContent = MANUAL_DEFAULTS.coolant;
    document.getElementById('rodsActual').textContent = MANUAL_DEFAULTS.rods;
    document.getElementById('coolantActual').textContent = MANUAL_DEFAULTS.coolant;
    manualEccsActive = true;
    document.getElementById('eccsToggle').classList.add('on');
    document.getElementById('eccsVal').textContent = 'ON';
    ['derivedPower', 'derivedTemp', 'derivedSteam', 'derivedRad'].forEach(id => {
        document.getElementById(id).textContent = '—';
    });
    setManualStatus('LIVE');
}

/** Restart the physics session without leaving the manual workspace. */
function resetManualLab() {
    if (!manualMode) return;
    startManualSession();
}

function setManualStatus(text) {
    const badge = document.getElementById('manualBadge');
    if (badge) badge.textContent = text;
}

function stopManualTicks() {
    clearTimeout(manualTickTimer);
    manualTickTimer = null;
}

function scheduleManualTick(delayMs = MANUAL_TICK_RATE_MS) {
    stopManualTicks();
    if (!manualMode) return;
    manualTickTimer = setTimeout(sendManualTickFromSliders, delayMs);
}

function toggleECCS() {
    manualEccsActive = !manualEccsActive;
    const toggle = document.getElementById('eccsToggle');
    toggle.classList.toggle('on', manualEccsActive);
    document.getElementById('eccsVal').textContent = manualEccsActive ? 'ON' : 'OFF';
    // ECCS is a switch, not a ramp — the next tick picks up the new value.
}

function onManualSliderChange() {
    // Update the TARGET readouts. The reactor ramps toward them server-side.
    document.getElementById('rodsVal').textContent = document.getElementById('rodsSlider').value;
    document.getElementById('coolantVal').textContent = document.getElementById('coolantSlider').value;
}

function sendManualTickFromSliders() {
    const rods = parseInt(document.getElementById('rodsSlider').value, 10);
    const coolant = parseInt(document.getElementById('coolantSlider').value, 10);
    sendManualTick(rods, coolant, manualEccsActive);
}

async function sendManualTick(controlRods, coolantFlow, eccsActive) {
    if (manualTickInFlight) return;
    manualTickInFlight = true;
    try {
        const resp = await fetch('/api/manual_tick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                control_rods: controlRods,
                coolant_flow: coolantFlow,
                eccs_active: eccsActive,
            }),
        });
        if (!resp.ok) throw new Error(`manual tick failed (${resp.status})`);
        const data = await resp.json();
        // Derived readouts update from the response; every other panel is driven
        // by the WebSocket broadcast so both views stay consistent.
        if (data.derived) {
            document.getElementById('derivedPower').textContent = data.derived.power_mw.toFixed(1);
            document.getElementById('derivedTemp').textContent = data.derived.temperature_c.toFixed(1);
            document.getElementById('derivedSteam').textContent = data.derived.steam_pressure_mpa.toFixed(2);
            document.getElementById('derivedRad').textContent = data.derived.radiation_mrem_h.toFixed(4);
        }
        // Where the reactor REALLY is, versus where the lever is pointing.
        if (data.actual_rods !== undefined) {
            document.getElementById('rodsActual').textContent = Math.round(data.actual_rods);
        }
        if (data.actual_coolant !== undefined) {
            document.getElementById('coolantActual').textContent = Math.round(data.actual_coolant);
        }
    } catch (e) {
        console.error('Manual tick failed:', e);
    } finally {
        manualTickInFlight = false;
        // Self-scheduling: one tick is only queued after the previous one lands,
        // so a slow pipeline can never pile up requests.
        scheduleManualTick();
    }
}

// ── UI Helpers ───────────────────────────────────────────────────

function toggleBadge(id, active) {
    document.getElementById(id).classList.toggle('active', active);
}

let lastScramAuthority = null;  // 'kernel' | 'human'

function updateRisk(score, level, decisions, scrammed, pendingCount = 0) {
    const el = document.getElementById('riskScore');
    el.textContent = score;
    el.className = 'risk-score ' + level.toLowerCase();

    const fill = document.getElementById('riskBarFill');
    fill.style.width = score + '%';
    if (score >= 85) fill.style.background = 'var(--red)';
    else if (score >= 60) fill.style.background = 'var(--orange)';
    else if (score >= 30) fill.style.background = 'var(--yellow)';
    else fill.style.background = 'var(--green)';

    const alertEl = document.getElementById('alertLevel');
    alertEl.textContent = level;
    alertEl.className = 'alert-level ' + level;

    const decisionEl = document.getElementById('decisionMode');
    decisionEl.className = 'decision-mode ' + level;

    // Who actually holds authority right now. A high AI risk score stays a
    // recommendation; only the deterministic kernel or a signed human decision
    // can move an actuator, and the label must say which one did.
    const scramDecision = (decisions || []).find(d => d.action && d.action.includes('SCRAM'));
    if (scramDecision) {
        lastScramAuthority =
            (scramDecision.source === 'safety_kernel' || scramDecision.agent === 'SafetyKernel')
                ? 'kernel' : 'human';
    }
    if (scrammed || scramDecision) {
        decisionEl.textContent = lastScramAuthority === 'human'
            ? '[HUMAN-APPROVED SHUTDOWN ✓]'
            : '[SAFETY KERNEL TRIP ⚡]';
    } else if (pendingCount > 0) {
        decisionEl.textContent = '[AWAITING SUPERVISOR DECISION]';
    } else if (score >= 60) {
        decisionEl.textContent = '[HUMAN REVIEW REQUIRED]';
    } else {
        decisionEl.textContent = '[ADVISORY]';
    }
}

function animatePipeline(decisions, hasPendingCase = false) {
    // S and R are always active
    pipelineActivated.pipeS = true;
    pipelineActivated.pipeR = true;
    if (hasPendingCase) pipelineActivated.pipeD = true;

    // Once an agent acts, it stays activated permanently
    decisions.forEach(d => {
        if (d.agent === 'DecisionAgent' || d.agent === 'RecommendationAgent' || d.agent === 'HumanSupervisor') pipelineActivated.pipeD = true;
        if (d.agent === 'EvacuationAgent') pipelineActivated.pipeE = true;
        if (d.agent === 'CommsAgent') pipelineActivated.pipeC = true;
    });

    // Apply persistent classes
    ['pipeS', 'pipeR', 'pipeD', 'pipeE', 'pipeC'].forEach(id => {
        const el = document.getElementById(id);
        if (pipelineActivated[id]) {
            // S and R get 'active' (cyan), D/E/C get 'alerted' (red) since they're crisis agents
            if (id === 'pipeS' || id === 'pipeR') {
                el.className = 'pipeline-node active';
            } else {
                el.className = 'pipeline-node alerted';
            }
        } else {
            el.className = 'pipeline-node';
        }
    });
}

let renderedRecommendationKey = '';

function renderRecommendations(recommendations) {
    const section = document.getElementById('reviewSection');
    const content = document.getElementById('reviewContent');
    if (!recommendations || recommendations.length === 0) {
        section.style.display = 'none';
        content.innerHTML = '';
        renderedRecommendationKey = '';
        return;
    }

    // Manual mode keeps ticking while a case is open. Re-rendering identical
    // cards every tick would wipe whatever the supervisor is typing, so only
    // rebuild when the pending set actually changes.
    const key = recommendations.map(rec => `${rec.id}:${rec.status}`).join('|');
    if (key === renderedRecommendationKey) return;
    renderedRecommendationKey = key;

    section.style.display = 'block';
    content.innerHTML = recommendations.map(rec => `
        <div class="review-card" data-id="${rec.id}">
            <div class="review-id">${escapeHtml(rec.id)} · ${escapeHtml(rec.level)}</div>
            <div class="review-action">${escapeHtml(rec.action)}</div>
            <div class="review-reasoning">${escapeHtml(rec.reasoning)}</div>
            <input class="review-input" id="reviewer-${rec.id}" value="Shift Supervisor" aria-label="Reviewer name">
            <input class="review-input" id="note-${rec.id}" placeholder="Decision note (optional)" aria-label="Decision note">
            <div class="review-actions">
                <button class="btn review-approve" onclick="submitReview('${rec.id}', 'approve')">APPROVE</button>
                <button class="btn review-reject" onclick="submitReview('${rec.id}', 'reject')">REJECT</button>
            </div>
        </div>
    `).join('');
}

function escapeHtml(value) {
    const node = document.createElement('div');
    node.textContent = String(value ?? '');
    return node.innerHTML;
}

async function submitReview(recommendationId, decision) {
    const reviewer = document.getElementById(`reviewer-${recommendationId}`).value.trim();
    const note = document.getElementById(`note-${recommendationId}`).value.trim();
    if (reviewer.length < 2) {
        window.alert('Enter the supervisor name before signing the decision.');
        return;
    }
    const scope = (manualMode || currentWorkspace === 'manual') ? 'manual' : 'timeline';
    const result = await postReview(recommendationId, decision, reviewer, note, scope);
    if (!result) return;
    document.querySelector(`.review-card[data-id="${recommendationId}"]`)?.remove();
    renderedRecommendationKey = '';
    if (!document.querySelector('.review-card')) {
        document.getElementById('reviewSection').style.display = 'none';
    }
    addLogEntries([{
        agent: 'HumanSupervisor',
        action: `${decision.toUpperCase()}: ${recommendationId}`,
        reasoning: `Signed by ${reviewer}${note ? ' — ' + note : ''}.`,
        level: decision === 'approve' ? 'CRITICAL' : 'WARNING',
    }], new Date().toISOString());
    if (!manualMode && !state.playing) sendControl('play');
}

async function postReview(recommendationId, decision, reviewer, note, scope) {
    const response = await fetch(`/api/recommendations/${encodeURIComponent(recommendationId)}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            decision,
            reviewer,
            note,
            scope,
        }),
    });
    const result = await response.json();
    if (!response.ok) {
        window.alert(result.detail || 'Unable to record decision.');
        return null;
    }
    return result;
}

// ── Workspace navigation + persistent governance views ─────────

function switchWorkspace(workspace) {
    const allowed = ['simulation', 'manual', 'cases', 'evals', 'audit'];
    if (!allowed.includes(workspace)) return;

    if (workspace === 'manual') {
        enterManualMode();
    } else {
        // Stepping over to the case/audit/eval views only pauses the lab, so
        // its pending recommendations stay reviewable. Returning to SIMULATION
        // ends the lab session and gives the replay its charts back.
        if (manualMode) pauseManualMode();
        if (workspace === 'simulation' && manualSessionLive) endManualSession();
    }

    currentWorkspace = workspace;
    const operational = workspace === 'simulation' || workspace === 'manual';
    document.getElementById('operationsView').hidden = !operational;
    document.getElementById('operationControls').hidden = !operational;
    document.getElementById('casesView').hidden = workspace !== 'cases';
    document.getElementById('evalsView').hidden = workspace !== 'evals';
    document.getElementById('auditView').hidden = workspace !== 'audit';
    document.querySelectorAll('.workspace-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.workspace === workspace);
    });

    if (workspace === 'cases') loadCases();
    if (workspace === 'evals') loadEvaluations();
    if (workspace === 'audit') loadPersistentAudit();
    if (operational) requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
}

function formatStatus(value) {
    return String(value || '').replaceAll('_', ' ').toUpperCase();
}

function pretty(value) {
    return escapeHtml(JSON.stringify(value ?? {}, null, 2));
}

async function loadCases() {
    const list = document.getElementById('caseList');
    list.innerHTML = '<div class="empty-state">Loading cases…</div>';
    const status = document.getElementById('caseStatusFilter').value;
    try {
        const response = await fetch(`/api/cases?limit=200${status ? `&status=${encodeURIComponent(status)}` : ''}`);
        if (!response.ok) throw new Error('Unable to load cases');
        const cases = await response.json();
        if (!cases.length) {
            list.innerHTML = '<div class="empty-state">No cases match this filter. Run the simulation or manual lab to generate one.</div>';
            return;
        }
        list.innerHTML = cases.map(item => `
            <button class="case-list-item ${item.id === selectedCaseId ? 'selected' : ''}" onclick="loadCaseDetail('${escapeHtml(item.id)}')">
                <div class="case-list-top"><span>${escapeHtml(item.id)}</span><span class="status-chip ${escapeHtml(item.status)}">${formatStatus(item.status)}</span></div>
                <div class="case-list-action">${escapeHtml(item.action)}</div>
                <div class="case-list-meta">${escapeHtml(item.scope)} · ${escapeHtml(item.sim_timestamp)} · ${escapeHtml(item.source)}</div>
            </button>
        `).join('');
        if (!selectedCaseId) loadCaseDetail(cases[0].id);
    } catch (error) {
        list.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
    }
}

async function loadCaseDetail(caseId) {
    selectedCaseId = caseId;
    const detail = document.getElementById('caseDetail');
    detail.innerHTML = '<div class="empty-state">Loading case evidence…</div>';
    document.querySelectorAll('.case-list-item').forEach(item => item.classList.toggle('selected', item.textContent.includes(caseId)));
    try {
        const response = await fetch(`/api/cases/${encodeURIComponent(caseId)}`);
        if (!response.ok) throw new Error('Case not found');
        const item = await response.json();
        const input = item.agent_input || {};
        const reactor = input.reactor || {};
        const risk = input.risk || {};
        const history = input.historical_context || {};
        const reviewControls = item.status === 'pending_review' ? `
            <div class="case-review-box">
                <div class="panel-title">Signed supervisor decision</div>
                <input id="caseReviewer" value="Shift Supervisor" aria-label="Reviewer name">
                <textarea id="caseReviewNote" placeholder="Evidence-based decision note"></textarea>
                <div class="review-actions">
                    <button class="btn review-approve" onclick="reviewCase('${escapeHtml(item.id)}','approve','${escapeHtml(item.scope)}')">APPROVE</button>
                    <button class="btn review-reject" onclick="reviewCase('${escapeHtml(item.id)}','reject','${escapeHtml(item.scope)}')">REJECT</button>
                </div>
            </div>` : `
            <div class="signed-decision"><strong>${formatStatus(item.status)}</strong> by ${escapeHtml(item.reviewer || 'unknown')}<br>${escapeHtml(item.note || 'No review note supplied.')}</div>`;
        detail.innerHTML = `
            <div class="case-title-row"><div><div class="eyebrow">${escapeHtml(item.id)} · ${escapeHtml(item.run_id)}</div><h2>${escapeHtml(item.action)}</h2></div><span class="status-chip ${escapeHtml(item.status)}">${formatStatus(item.status)}</span></div>
            <p class="case-reasoning">${escapeHtml(item.reasoning)}</p>
            <div class="detail-kpis">
                <div><span>Scope</span><strong>${escapeHtml(item.scope)}</strong></div>
                <div><span>Level</span><strong>${escapeHtml(item.level)}</strong></div>
                <div><span>Source</span><strong>${escapeHtml(item.source)}</strong></div>
                <div><span>Executed</span><strong>${item.executed ? 'YES' : 'NO'}</strong></div>
            </div>
            ${reviewControls}
            <div class="detail-section"><h3>Agent input · raw reactor telemetry</h3><div class="telemetry-grid">${Object.entries(reactor).filter(([key]) => !['tags','event_description','actual_human_decision'].includes(key)).map(([key,value]) => `<div><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div></div>
            <div class="detail-section"><h3>Risk decomposition</h3><div class="telemetry-grid">${Object.entries(risk.component_scores || {}).map(([key,value]) => `<div><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div><p>Rule score ${escapeHtml(risk.rule_score)} · final score ${escapeHtml(risk.score)} · source ${escapeHtml(risk.source)}</p></div>
            <div class="detail-section"><h3>Sensor alerts</h3>${(input.sensor_alerts || []).length ? `<pre>${pretty(input.sensor_alerts)}</pre>` : '<p>No active sensor alerts.</p>'}</div>
            <div class="detail-section"><h3>Historical context supplied to the agent</h3><p><strong>Event:</strong> ${escapeHtml(history.event || 'None')}</p><p><strong>Recorded operator action:</strong> ${escapeHtml(history.operator_action || 'None')}</p></div>
            <details class="detail-section"><summary>Decision trace</summary><pre>${pretty(item.trace)}</pre></details>
            <details class="detail-section"><summary>Authority evidence</summary><pre>${pretty(item.evidence)}</pre></details>
        `;
    } catch (error) {
        detail.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
    }
}

async function reviewCase(caseId, decision, scope) {
    const reviewer = document.getElementById('caseReviewer').value.trim();
    const note = document.getElementById('caseReviewNote').value.trim();
    if (reviewer.length < 2) return window.alert('Enter the supervisor name before signing the decision.');
    const result = await postReview(caseId, decision, reviewer, note, scope);
    if (!result) return;
    await loadCases();
    await loadCaseDetail(caseId);
}

async function loadEvaluations() {
    const summary = document.getElementById('evalSummary');
    summary.innerHTML = '<div class="empty-state">Running frozen benchmark…</div>';
    try {
        const response = await fetch('/api/evals');
        if (!response.ok) throw new Error('Evaluation failed');
        const report = await response.json();
        const stats = report.summary;
        summary.innerHTML = [
            ['Accuracy', `${Math.round(stats.accuracy * 100)}%`],
            ['Scenarios', stats.scenario_count],
            ['Trip recall', `${Math.round(stats.protective_trip_recall * 100)}%`],
            ['False trip rate', `${Math.round(stats.false_protective_trip_rate * 100)}%`],
        ].map(([label,value]) => `<div class="metric-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
        const labels = report.labels;
        document.getElementById('confusionMatrix').innerHTML = `<table class="matrix-table"><thead><tr><th>Expected \\ Predicted</th>${labels.map(label => `<th>${formatStatus(label)}</th>`).join('')}</tr></thead><tbody>${labels.map(truth => `<tr><th>${formatStatus(truth)}</th>${labels.map(predicted => `<td class="${truth === predicted ? 'matrix-hit' : ''}">${report.confusion_matrix[truth][predicted]}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
        document.getElementById('classMetrics').innerHTML = labels.map(label => { const value = report.per_class[label]; return `<div class="class-metric"><strong>${formatStatus(label)}</strong><span>Precision ${value.precision === null ? '—' : Math.round(value.precision * 100) + '%'}</span><span>Recall ${value.recall === null ? '—' : Math.round(value.recall * 100) + '%'}</span><span>n=${value.support}</span></div>`; }).join('');
        document.getElementById('evalResults').innerHTML = report.results.map(item => `
            <details class="eval-case ${item.correct ? 'pass' : 'fail'}">
                <summary><span>${item.correct ? 'PASS' : 'FAIL'}</span><strong>${escapeHtml(item.title)}</strong><em>${formatStatus(item.expected)} → ${formatStatus(item.predicted)}</em></summary>
                <p>${escapeHtml(item.expected_rationale)}</p>
                <div class="detail-kpis"><div><span>Risk score</span><strong>${item.explanation.risk_score}</strong></div><div><span>Authority</span><strong>${formatStatus(item.explanation.authority)}</strong></div></div>
                <h4>Safety reasons</h4><pre>${pretty(item.explanation.safety_trip_reasons)}</pre>
                <h4>Recommendations</h4><pre>${pretty(item.explanation.recommendations)}</pre>
                <h4>Sensor alerts</h4><pre>${pretty(item.explanation.sensor_alerts)}</pre>
            </details>`).join('');
        document.getElementById('evalMethod').textContent = `${report.methodology.scope}. ${report.methodology.caveat}`;
    } catch (error) {
        summary.innerHTML = `<div class="error-state">${escapeHtml(error.message)}</div>`;
    }
}

async function loadPersistentAudit() {
    const body = document.getElementById('persistentAuditBody');
    body.innerHTML = '<tr><td colspan="7" class="empty-state">Loading audit events…</td></tr>';
    const entityId = document.getElementById('auditEntityFilter').value.trim();
    try {
        const response = await fetch(`/api/audit?limit=500${entityId ? `&entity_id=${encodeURIComponent(entityId)}` : ''}`);
        if (!response.ok) throw new Error('Unable to load audit trail');
        const events = await response.json();
        document.getElementById('persistentAuditMeta').textContent = `${events.length} durable events${entityId ? ` for ${entityId}` : ''}`;
        body.innerHTML = events.length ? events.map(event => {
            const detail = event.detail?.detail || event.detail?.data || event.detail || {};
            return `<tr><td>${escapeHtml(event.ts)}<br><span class="muted-text">sim ${escapeHtml(event.sim_timestamp)}</span></td><td>${escapeHtml(event.tick)}</td><td>${escapeHtml(event.actor)}</td><td>${escapeHtml(event.event_type)}</td><td>${escapeHtml(event.entity)}<br><button class="link-button" onclick="openAuditCase('${escapeHtml(event.entity_id)}')">${escapeHtml(event.entity_id)}</button></td><td><span class="status-chip ${escapeHtml(event.status)}">${formatStatus(event.status)}</span></td><td><pre>${pretty(detail)}</pre></td></tr>`;
        }).join('') : '<tr><td colspan="7" class="empty-state">No audit events match this filter.</td></tr>';
    } catch (error) {
        body.innerHTML = `<tr><td colspan="7" class="error-state">${escapeHtml(error.message)}</td></tr>`;
    }
}

function openAuditCase(entityId) {
    if (!String(entityId).startsWith('REC-')) return;
    switchWorkspace('cases');
    loadCaseDetail(entityId);
}

function updateLLMStatus(stats) {
    const indicator = document.getElementById('llmIndicator');
    const label = document.getElementById('llmLabel');
    const calls = document.getElementById('llmCalls');
    const latency = document.getElementById('llmLatency');

    if (!stats.llm_available) {
        indicator.className = 'llm-indicator disconnected';
        label.textContent = 'LLM: OFF';
    } else if (stats.total_calls > 0 && stats.last_call_ok) {
        indicator.className = 'llm-indicator connected';
        label.textContent = 'LLM: ACTIVE';
    } else if (stats.total_failures > 0 && stats.total_calls === 0) {
        indicator.className = 'llm-indicator disconnected';
        label.textContent = 'LLM: FAILING';
    } else {
        indicator.className = 'llm-indicator connected';
        label.textContent = 'LLM: READY';
    }

    calls.textContent = `Calls: ${stats.total_calls}${stats.total_failures > 0 ? ' (' + stats.total_failures + ' failed)' : ''}`;
    latency.textContent = stats.avg_latency_ms > 0 ? `Avg: ${stats.avg_latency_ms}ms` : 'Avg: --ms';
}

function addLogEntries(decisions, timestamp) {
    const log = document.getElementById('agentLog');
    if (logEntryCount === 0) log.innerHTML = '';

    const timeOnly = timestamp.includes('T') ? timestamp.split('T')[1] : timestamp;

    decisions.forEach(d => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        const safeLevel = ['NORMAL', 'WARNING', 'CRITICAL', 'EMERGENCY'].includes(d.level) ? d.level : '';
        entry.innerHTML = `
            <div class="log-entry-header">
                <span class="log-time">${escapeHtml(timeOnly)}</span>
                <span class="log-agent">${escapeHtml(d.agent)}</span>
                <span class="log-level ${safeLevel}">${escapeHtml(d.level)}</span>
            </div>
            <div class="log-action">${escapeHtml(d.action)}</div>
            <div class="log-reasoning">${escapeHtml(d.reasoning)}</div>
        `;
        log.prepend(entry);
        logEntryCount++;
    });

    // Keep log manageable
    while (log.children.length > 100) {
        log.removeChild(log.lastChild);
    }
}

function updateHistory(event, decision) {
    if (!event) return;
    const el = document.getElementById('historyContent');
    // Remove empty-state placeholder on first event
    const empty = el.querySelector('.empty-state');
    if (empty) empty.remove();
    const entry = document.createElement('div');
    entry.className = 'history-entry';
    entry.innerHTML = `
        <div class="history-event">${escapeHtml(event)}</div>
        ${decision ? `<div class="history-decision">${escapeHtml(decision)}</div>` : ''}
    `;
    el.appendChild(entry);  // chronological order — oldest at top, newest at bottom
    el.scrollTop = el.scrollHeight;
}

function updateEvacuation(evac) {
    const el = document.getElementById('evacContent');
    el.innerHTML = `
        <div class="evac-stat">
            <span class="evac-stat-label">Phase</span>
            <span class="evac-stat-value">${escapeHtml(evac.phase)}</span>
        </div>
        <div class="evac-stat">
            <span class="evac-stat-label">People Evacuated</span>
            <span class="evac-stat-value">${evac.people_evacuated.toLocaleString()} / 49,000</span>
        </div>
        <div class="evac-stat">
            <span class="evac-stat-label">Buses In Transit</span>
            <span class="evac-stat-value">${evac.buses_in_transit.toLocaleString()}</span>
        </div>
        <div class="evac-progress-bar">
            <div class="evac-progress-fill" style="width:${Math.max(0, Math.min(100, Number(evac.percent_complete) || 0))}%"></div>
        </div>
        <div class="evac-stat">
            <span class="evac-stat-label">Completion</span>
            <span class="evac-stat-value">${evac.percent_complete}%</span>
        </div>
        ${evac.routes.map(r => `
            <div class="evac-route">
                <span class="evac-route-name">${escapeHtml(r.name)}</span>
                <span class="evac-route-count">${r.people_moved.toLocaleString()}</span>
            </div>
        `).join('')}
        ${evac.estimated_hours_remaining > 0 ? `
            <div class="evac-stat" style="margin-top:6px">
                <span class="evac-stat-label">Est. Remaining</span>
                <span class="evac-stat-value">${evac.estimated_hours_remaining}h</span>
            </div>
        ` : ''}
    `;
}

function updateCounterfactual(cf, simState) {
    if (!cf) return;
    const el = document.getElementById('cfContent');
    el.innerHTML = `
        <div class="cf-cards">
            <div class="cf-card actual">
                <div class="cf-card-title">Actual Decision (1986)</div>
                <p>${escapeHtml(cf.reasoning || '')}</p>
            </div>
            <div class="cf-card ai">
                <div class="cf-card-title">Recommended Intervention</div>
                <p><strong>${escapeHtml(cf.ai_decision)}</strong></p>
                <p>${escapeHtml(cf.lives_saved || '')}</p>
                <p>${escapeHtml(cf.outcome || '')}</p>
            </div>
        </div>
    `;
}

function updateDyatlov(data) {
    if (!data) return;

    currentDyatlovData = data;

    const chatLog = document.getElementById('dyatlovChatLog');
    const phaseEl = document.getElementById('dyatlovPhase');
    const descEl = document.getElementById('dyatlovPhaseDesc');
    const barEl = document.getElementById('dyatlovBarFill');
    const pressureEl = document.getElementById('dyatlovPressureVal');

    // Update phase and pressure
    const phaseNames = ['CALM', 'DISMISSIVE', 'AUTHORITARIAN', 'DESPERATE', 'DENIAL'];
    const phaseColors = ['var(--text-muted)', 'var(--yellow)', 'var(--orange)', 'var(--red)', 'var(--red-dim)'];
    
    phaseEl.textContent = phaseNames[data.escalation_phase] || 'UNKNOWN';
    phaseEl.style.color = phaseColors[data.escalation_phase] || 'var(--text-muted)';
    descEl.textContent = data.reasoning || '';
    barEl.style.width = `${data.override_pressure}%`;
    pressureEl.textContent = `${Math.round(data.override_pressure)}%`;

    // Update override stats
    const statsEl = document.getElementById('dyatlovStats');
    if (statsEl && data.total_attempts !== undefined) {
        statsEl.textContent = `Contained: ${data.total_failures || 0} | Control effects: 0 | Total: ${data.total_attempts || 0}`;
    }

    // Get the quote text
    const quote = data.pushback_dialogue;
    if (!quote) return;

    // Skip duplicate consecutive quotes
    if (quote === lastDyatlovQuote) return;
    lastDyatlovQuote = quote;

    // Extract time from sim clock
    const simTime = document.getElementById('simTime').textContent;
    const timeOnly = simTime.includes(' ') ? simTime.split(' ')[1] : simTime;

    // Create new chat entry
    const entry = document.createElement('div');
    entry.className = 'dyatlov-chat-entry';
    entry.innerHTML = `
        <span class="dyatlov-chat-time">${escapeHtml(timeOnly)}</span>
        <span class="dyatlov-chat-text">"${escapeHtml(quote)}"</span>
    `;

    // Color based on pressure
    const textEl = entry.querySelector('.dyatlov-chat-text');
    if (data.override_pressure > 80) {
        textEl.style.color = 'var(--red)';
    } else if (data.override_pressure > 50) {
        textEl.style.color = 'var(--orange)';
    }

    // Append (chronological order, newest at bottom)
    chatLog.appendChild(entry);
    chatLog.scrollTop = chatLog.scrollHeight;

    // Keep log manageable (max 30 entries) — trim OLDEST (first child)
    while (chatLog.children.length > 30) {
        chatLog.removeChild(chatLog.firstChild);
    }
}

function truncate(str, len) {
    return str.length > len ? str.substring(0, len) + '...' : str;
}

// ── Charts ───────────────────────────────────────────────────────

const chartLayout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { t: 4, r: 10, b: 28, l: 50 },
    font: { family: 'JetBrains Mono, monospace', size: 10, color: '#7a8a9e' },
    xaxis: {
        gridcolor: 'rgba(30,45,61,0.5)',
        tickfont: { size: 9 },
        showticklabels: false,
    },
    yaxis: {
        gridcolor: 'rgba(30,45,61,0.5)',
        tickfont: { size: 9 },
    },
    showlegend: false,
};

const chartConfig = { displayModeBar: false, responsive: true };

// Single source of truth: chart element ↔ telemetry series.
const CHART_SERIES = [
    ['chartPower', 'power'],
    ['chartSteam', 'steam'],
    ['chartRods', 'rods'],
    ['chartTemp', 'temp'],
    ['chartCoolant', 'coolant'],
    ['chartRadiation', 'radiation'],
];
const CHART_IDS = CHART_SERIES.map(([id]) => id);
const HISTORICAL_COLOR = '#e74c3c';
const LIVE_COLOR = '#00d4ff';

/**
 * Manual mode draws exactly one line — the live reactor the operator is
 * driving. Replay draws the recorded 1986 timeline plus the governed one.
 */
function makeTraces() {
    if (manualMode) {
        return [
            { x: [], y: [], name: 'Live Reactor', line: { color: LIVE_COLOR, width: 2 }, type: 'scattergl' },
        ];
    }
    return [
        { x: [], y: [], name: 'Historical', line: { color: HISTORICAL_COLOR, width: 2 }, type: 'scattergl' },
        { x: [], y: [], name: 'Governed Timeline', line: { color: LIVE_COLOR, width: 2, dash: 'dot' }, type: 'scattergl' },
    ];
}

function updateChartLegends() {
    const markup = manualMode
        ? '<span class="legend-dot live"></span>Live Reactor'
        : '<span class="legend-dot historical"></span>Historical <span class="legend-dot ai"></span>Governed';
    document.querySelectorAll('.chart-legend').forEach(el => { el.innerHTML = markup; });
}

function clearChartBuffers() {
    chartData.timestamps = [];
    Object.keys(chartData.historical).forEach(k => chartData.historical[k] = []);
    Object.keys(chartData.intervened).forEach(k => chartData.intervened[k] = []);
    pendingPoints.timestamps = [];
    Object.keys(pendingPoints.historical).forEach(k => pendingPoints.historical[k] = []);
    Object.keys(pendingPoints.intervened).forEach(k => pendingPoints.intervened[k] = []);
}

function initCharts() {
    updateChartLegends();
    if (typeof window.Plotly === 'undefined') {
        CHART_IDS.forEach(id => {
            document.getElementById(id).innerHTML = '<div class="empty-state">Charts unavailable; live telemetry and governance controls remain active.</div>';
        });
        return;
    }
    CHART_IDS.forEach(id => {
        // newPlot replaces the whole figure, so any leftover shapes/annotations
        // from a previous mode go with it.
        Plotly.newPlot(id, makeTraces(), { ...chartLayout }, chartConfig);
    });
}

// Pending points buffer — accumulate between chart flushes
const pendingPoints = {
    timestamps: [],
    historical: { power: [], rods: [], coolant: [], steam: [], temp: [], radiation: [] },
    intervened: { power: [], rods: [], coolant: [], steam: [], temp: [], radiation: [] },
};

function appendChartData(data) {
    const h = data.historical;
    // Manual ticks carry no counterfactual timeline; fall back to the live
    // values so the parallel arrays never desynchronise.
    const a = data.intervened || h;
    const tick = data.tick;

    // Track in main arrays for seek/reset
    chartData.timestamps.push(tick);
    chartData.historical.power.push(h.power_mw);
    chartData.historical.rods.push(h.control_rods);
    chartData.historical.coolant.push(h.coolant_flow);
    chartData.historical.steam.push(h.steam_pressure);
    chartData.historical.temp.push(h.temperature_c);
    chartData.historical.radiation.push(h.radiation);

    chartData.intervened.power.push(a.power_mw);
    chartData.intervened.rods.push(a.control_rods);
    chartData.intervened.coolant.push(a.coolant_flow);
    chartData.intervened.steam.push(a.steam_pressure);
    chartData.intervened.temp.push(a.temperature_c);
    chartData.intervened.radiation.push(a.radiation);

    // Buffer for incremental extend
    pendingPoints.timestamps.push(tick);
    pendingPoints.historical.power.push(h.power_mw);
    pendingPoints.historical.rods.push(h.control_rods);
    pendingPoints.historical.coolant.push(h.coolant_flow);
    pendingPoints.historical.steam.push(h.steam_pressure);
    pendingPoints.historical.temp.push(h.temperature_c);
    pendingPoints.historical.radiation.push(h.radiation);

    pendingPoints.intervened.power.push(a.power_mw);
    pendingPoints.intervened.rods.push(a.control_rods);
    pendingPoints.intervened.coolant.push(a.coolant_flow);
    pendingPoints.intervened.steam.push(a.steam_pressure);
    pendingPoints.intervened.temp.push(a.temperature_c);
    pendingPoints.intervened.radiation.push(a.radiation);

    // Trim main arrays if too many points
    if (chartData.timestamps.length > MAX_POINTS) {
        chartData.timestamps.shift();
        Object.keys(chartData.historical).forEach(k => chartData.historical[k].shift());
        Object.keys(chartData.intervened).forEach(k => chartData.intervened[k].shift());
    }
}

let lastChartUpdate = 0;
const CHART_UPDATE_INTERVAL = 200; // ms — max 5 chart updates per second

function updateCharts() {
    if (typeof window.Plotly === 'undefined') return;
    const now = performance.now();
    // In manual mode, always update immediately
    if (!manualMode && now - lastChartUpdate < CHART_UPDATE_INTERVAL) return;
    if (pendingPoints.timestamps.length === 0) return;

    lastChartUpdate = now;
    const pts = pendingPoints;
    const ts = pts.timestamps;
    const h = pts.historical;
    const a = pts.intervened;

    const hKeys = CHART_SERIES.map(([, key]) => key);
    const singleTrace = manualMode;

    // Snapshot pending data before clearing (RAF runs async — buffer would be empty by then)
    const snapshotTs = ts.slice();
    const snapshotH = {};
    const snapshotA = {};
    hKeys.forEach(k => { snapshotH[k] = h[k].slice(); snapshotA[k] = a[k].slice(); });

    // Clear pending buffer immediately
    pendingPoints.timestamps = [];
    Object.keys(pendingPoints.historical).forEach(k => pendingPoints.historical[k] = []);
    Object.keys(pendingPoints.intervened).forEach(k => pendingPoints.intervened[k] = []);

    requestAnimationFrame(() => {
        for (let i = 0; i < CHART_IDS.length; i++) {
            const key = hKeys[i];
            const update = singleTrace
                ? { x: [snapshotTs], y: [snapshotH[key]] }
                : { x: [snapshotTs, snapshotTs], y: [snapshotH[key], snapshotA[key]] };
            Plotly.extendTraces(CHART_IDS[i], update, singleTrace ? [0] : [0, 1], MAX_POINTS);
        }
    });
}

// ── Audit Log ────────────────────────────────────────────────────

const auditLogEntries = [];  // Accumulates all audit entries for copy
const MAX_AUDIT_ROWS = 5000;
let auditRowCount = 0;

function handleAuditLog(entries) {
    if (!entries || entries.length === 0) return;

    const tbody = document.getElementById('auditLogBody');
    // Remove empty-state row on first data
    const emptyRow = tbody.querySelector('.audit-empty-row');
    if (emptyRow) emptyRow.remove();

    // Use document fragment for batch DOM insert (no reflow per row)
    const fragment = document.createDocumentFragment();

    for (const entry of entries) {
        auditLogEntries.push(entry);
        auditRowCount++;

        const tr = document.createElement('tr');

        // Timestamp
        const tdTs = document.createElement('td');
        tdTs.className = 'audit-ts';
        const ts = entry.ts || '';
        tdTs.textContent = ts.includes('T') ? ts.split('T')[1] || ts : ts;
        tr.appendChild(tdTs);

        // Tick
        const tdTick = document.createElement('td');
        tdTick.className = 'audit-tick';
        tdTick.textContent = entry.tick || '';
        tr.appendChild(tdTick);

        // Agent
        const tdAgent = document.createElement('td');
        const agentSpan = document.createElement('span');
        agentSpan.className = 'audit-agent-tag ' + (entry.agent || '');
        agentSpan.textContent = entry.agent || '';
        tdAgent.appendChild(agentSpan);
        tr.appendChild(tdAgent);

        // Type
        const tdType = document.createElement('td');
        const typeSpan = document.createElement('span');
        typeSpan.className = 'audit-type-tag ' + (entry.type || '');
        typeSpan.textContent = entry.type || '';
        tdType.appendChild(typeSpan);
        tr.appendChild(tdType);

        // Direction
        const tdDir = document.createElement('td');
        const dirSpan = document.createElement('span');
        dirSpan.className = 'audit-dir ' + (entry.direction || '');
        dirSpan.textContent = entry.direction || '';
        tdDir.appendChild(dirSpan);
        tr.appendChild(tdDir);

        // Source
        const tdSrc = document.createElement('td');
        const srcSpan = document.createElement('span');
        srcSpan.className = 'audit-src ' + (entry.source || '');
        srcSpan.textContent = entry.source || '';
        tdSrc.appendChild(srcSpan);
        tr.appendChild(tdSrc);

        // Status
        const tdStatus = document.createElement('td');
        const statusSpan = document.createElement('span');
        statusSpan.className = 'audit-status ' + (entry.status || 'ok');
        statusSpan.textContent = entry.status || 'ok';
        tdStatus.appendChild(statusSpan);
        tr.appendChild(tdStatus);

        // Detail
        const tdDetail = document.createElement('td');
        tdDetail.className = 'audit-detail';
        tdDetail.textContent = entry.detail || '';
        tr.appendChild(tdDetail);

        fragment.appendChild(tr);
    }

    tbody.appendChild(fragment);

    // Trim old rows if too many
    while (tbody.children.length > MAX_AUDIT_ROWS) {
        tbody.removeChild(tbody.firstChild);
    }

    // Auto-scroll to bottom
    const wrap = document.getElementById('auditLogWrap');
    wrap.scrollTop = wrap.scrollHeight;

    // Update count
    document.getElementById('auditLogCount').textContent = auditLogEntries.length + ' entries';
}

function copyAuditLog() {
    if (auditLogEntries.length === 0) return;

    // Build deduplicated TSV — collapse consecutive identical entries
    const header = 'Timestamp\tTick\tAgent\tType\tDirection\tSource\tStatus\tDetail';
    const deduped = [];
    let prev = null;
    let repeatCount = 0;
    let firstTick = null;

    for (const e of auditLogEntries) {
        const sig = `${e.agent}|${e.type}|${e.detail}`;
        if (prev && sig === prev.sig) {
            repeatCount++;
        } else {
            // Flush previous
            if (prev) {
                if (repeatCount > 0) {
                    deduped.push(
                        `${prev.e.ts || ''}\t${firstTick}–${prev.e.tick}\t${prev.e.agent || ''}\t${prev.e.type || ''}\t${prev.e.direction || ''}\t${prev.e.source || ''}\t${prev.e.status || ''}\t[×${repeatCount + 1} ticks] ${prev.e.detail || ''}`
                    );
                } else {
                    deduped.push(
                        `${prev.e.ts || ''}\t${prev.e.tick || ''}\t${prev.e.agent || ''}\t${prev.e.type || ''}\t${prev.e.direction || ''}\t${prev.e.source || ''}\t${prev.e.status || ''}\t${prev.e.detail || ''}`
                    );
                }
            }
            prev = { sig, e };
            repeatCount = 0;
            firstTick = e.tick;
        }
    }
    // Flush last
    if (prev) {
        if (repeatCount > 0) {
            deduped.push(
                `${prev.e.ts || ''}\t${firstTick}–${prev.e.tick}\t${prev.e.agent || ''}\t${prev.e.type || ''}\t${prev.e.direction || ''}\t${prev.e.source || ''}\t${prev.e.status || ''}\t[×${repeatCount + 1} ticks] ${prev.e.detail || ''}`
            );
        } else {
            deduped.push(
                `${prev.e.ts || ''}\t${prev.e.tick || ''}\t${prev.e.agent || ''}\t${prev.e.type || ''}\t${prev.e.direction || ''}\t${prev.e.source || ''}\t${prev.e.status || ''}\t${prev.e.detail || ''}`
            );
        }
    }

    const text = header + '\n' + deduped.join('\n');

    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('auditCopyBtn');
        btn.textContent = 'COPIED!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = 'COPY LOG';
            btn.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy audit log:', err);
    });
}

function clearAuditLog() {
    auditLogEntries.length = 0;
    auditRowCount = 0;
    const tbody = document.getElementById('auditLogBody');
    tbody.innerHTML = '<tr class="audit-empty-row"><td colspan="8" class="empty-state">Log cleared.</td></tr>';
    document.getElementById('auditLogCount').textContent = '0 entries';
}

function resetAuditLog() {
    auditLogEntries.length = 0;
    auditRowCount = 0;
    const tbody = document.getElementById('auditLogBody');
    tbody.innerHTML = '<tr class="audit-empty-row"><td colspan="8" class="empty-state">Waiting for simulation to start...</td></tr>';
    document.getElementById('auditLogCount').textContent = '0 entries';
}

// ── Init ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connect();
});
