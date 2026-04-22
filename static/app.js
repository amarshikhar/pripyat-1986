/**
 * PRIPYAT-1986 Web Dashboard — Frontend
 * Real-time simulation visualization via WebSocket + Plotly.js
 */

// ── State ────────────────────────────────────────────────────────

const state = {
    playing: false,
    speed: 60,
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
    // Update time display
    const ts = data.timestamp;
    document.getElementById('simTime').textContent = ts.replace('T', ' ');

    // Progress
    document.getElementById('progressBar').style.width = data.progress_pct + '%';
    state.currentTick = data.tick;

    // Scrubber
    const scrubber = document.getElementById('scrubber');
    scrubber.max = state.totalTicks || 100;
    scrubber.value = data.tick;
    document.getElementById('scrubberTick').textContent = `Tick: ${data.tick} / ${state.totalTicks}`;
    document.getElementById('scrubberPct').textContent = data.progress_pct.toFixed(1) + '%';

    // Badges
    toggleBadge('scramBadge', data.state.reactor_scrammed);
    toggleBadge('evacBadge', data.state.evacuation_ordered);
    toggleBadge('divergedBadge', data.state.diverged);

    // Risk gauge
    updateRisk(data.risk_score, data.alert_level);

    // Charts
    appendChartData(data);
    updateCharts();

    // Pipeline animation
    animatePipeline(data.decisions);

    // Dyatlov override panel
    if (data.dyatlov) updateDyatlov(data.dyatlov);

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
}

function handleStateUpdate(data) {
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
                    <p><strong>Explosion:</strong> ${report.actual_timeline?.explosion || 'Apr 26, 01:23:40'}</p>
                    <p><strong>Evacuation:</strong> 36 hours delayed</p>
                    <p><strong>Deaths:</strong> 31 immediate, ~4000 long-term</p>
                </div>
                <div class="cf-card ai">
                    <div class="cf-card-title">AI Agent Timeline</div>
                    <p><strong>SCRAM ordered:</strong> ${report.ai_timeline.scram_ordered}</p>
                    <p><strong>Evacuation:</strong> ${report.ai_timeline.evacuation_hours_earlier ? report.ai_timeline.evacuation_hours_earlier + 'h earlier' : 'N/A'}</p>
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
    // Clear chart data
    chartData.timestamps = [];
    Object.keys(chartData.historical).forEach(k => chartData.historical[k] = []);
    Object.keys(chartData.intervened).forEach(k => chartData.intervened[k] = []);
    logEntryCount = 0;
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
    document.getElementById('historyContent').innerHTML = '<div class="empty-state">Events will appear as the simulation progresses...</div>';
    document.getElementById('evacContent').innerHTML = '<div class="empty-state">No evacuation order yet.</div>';
    updateRisk(0, 'NORMAL');
    initCharts();
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

// ── UI Helpers ───────────────────────────────────────────────────

function toggleBadge(id, active) {
    document.getElementById(id).classList.toggle('active', active);
}

function updateRisk(score, level) {
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
    if (score >= 85) decisionEl.textContent = '[AUTO-EXECUTE ⚡]';
    else if (score >= 60) decisionEl.textContent = '[CONFIRM REQUIRED]';
    else decisionEl.textContent = '[ADVISORY]';
}

function animatePipeline(decisions) {
    // S and R are always active
    pipelineActivated.pipeS = true;
    pipelineActivated.pipeR = true;

    // Once an agent acts, it stays activated permanently
    decisions.forEach(d => {
        if (d.agent === 'DecisionAgent') pipelineActivated.pipeD = true;
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

function addLogEntries(decisions, timestamp) {
    const log = document.getElementById('agentLog');
    if (logEntryCount === 0) log.innerHTML = '';

    decisions.forEach(d => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `
            <div class="log-entry-header">
                <span class="log-agent ${d.agent}">${d.agent}</span>
                <span class="log-level ${d.level}">${d.level}</span>
            </div>
            <div class="log-action">${d.action}</div>
            <div class="log-reasoning">${d.reasoning}</div>
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
        <div class="history-event">${event}</div>
        ${decision ? `<div class="history-decision">${decision}</div>` : ''}
    `;
    el.prepend(entry);  // newest at top (reverse chronological)
}

function updateEvacuation(evac) {
    const el = document.getElementById('evacContent');
    el.innerHTML = `
        <div class="evac-stat">
            <span class="evac-stat-label">Phase</span>
            <span class="evac-stat-value">${evac.phase}</span>
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
            <div class="evac-progress-fill" style="width:${evac.percent_complete}%"></div>
        </div>
        <div class="evac-stat">
            <span class="evac-stat-label">Completion</span>
            <span class="evac-stat-value">${evac.percent_complete}%</span>
        </div>
        ${evac.routes.map(r => `
            <div class="evac-route">
                <span class="evac-route-name">${r.name}</span>
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
                <p>${cf.reasoning || ''}</p>
            </div>
            <div class="cf-card ai">
                <div class="cf-card-title">AI Agent Decision</div>
                <p><strong>${cf.ai_decision}</strong></p>
                <p>${cf.lives_saved || ''}</p>
                <p>${cf.outcome || ''}</p>
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
    descEl.textContent = data.reasoning;
    barEl.style.width = `${data.override_pressure}%`;
    pressureEl.textContent = `${Math.round(data.override_pressure)}%`;

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
        <span class="dyatlov-chat-time">${timeOnly}</span>
        <span class="dyatlov-chat-text">"${quote}"</span>
    `;

    // Color based on pressure
    const textEl = entry.querySelector('.dyatlov-chat-text');
    if (data.override_pressure > 80) {
        textEl.style.color = 'var(--red)';
    } else if (data.override_pressure > 50) {
        textEl.style.color = 'var(--orange)';
    }

    // Prepend (newest at top due to column-reverse)
    chatLog.prepend(entry);

    // Keep log manageable (max 30 entries)
    while (chatLog.children.length > 30) {
        chatLog.removeChild(chatLog.lastChild);
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

function makeTraces(histColor, aiColor) {
    return [
        { x: [], y: [], name: 'Historical', line: { color: histColor, width: 2 }, type: 'scattergl' },
        { x: [], y: [], name: 'AI Timeline', line: { color: aiColor, width: 2, dash: 'dot' }, type: 'scattergl' },
    ];
}

const charts = {};

function initCharts() {
    const defs = [
        ['chartPower', '#e74c3c', '#00d4ff'],
        ['chartRods', '#e74c3c', '#00d4ff'],
        ['chartCoolant', '#e74c3c', '#00d4ff'],
        ['chartSteam', '#e74c3c', '#00d4ff'],
        ['chartTemp', '#e74c3c', '#00d4ff'],
        ['chartRadiation', '#e74c3c', '#00d4ff'],
    ];

    defs.forEach(([id, hc, ac]) => {
        const traces = makeTraces(hc, ac);
        Plotly.newPlot(id, traces, { ...chartLayout }, chartConfig);
        charts[id] = true;
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
    const a = data.intervened;
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
    const now = performance.now();
    if (now - lastChartUpdate < CHART_UPDATE_INTERVAL) return;
    if (pendingPoints.timestamps.length === 0) return;

    lastChartUpdate = now;
    const pts = pendingPoints;
    const ts = pts.timestamps;
    const h = pts.historical;
    const a = pts.intervened;

    const chartIds = ['chartPower', 'chartRods', 'chartCoolant', 'chartSteam', 'chartTemp', 'chartRadiation'];
    const hKeys = ['power', 'rods', 'coolant', 'steam', 'temp', 'radiation'];

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
        for (let i = 0; i < chartIds.length; i++) {
            Plotly.extendTraces(chartIds[i], {
                x: [snapshotTs, snapshotTs],
                y: [snapshotH[hKeys[i]], snapshotA[hKeys[i]]],
            }, [0, 1], MAX_POINTS);
        }
    });
}

// ── Init ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connect();
});
