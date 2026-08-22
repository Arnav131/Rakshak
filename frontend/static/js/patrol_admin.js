/**
 * Rakshak — Patrol Review Admin Dashboard JavaScript
 * frontend/static/js/patrol_admin.js
 */

let allPatrols = [];
let selectedPatrolCode = null;
let currentPatrol = null;
let chartInstances = {};
let selectedDecision = null;

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', () => {
    // Load initial data from page context if available
    const dataEl = document.getElementById('initial-patrols-data');
    if (dataEl && dataEl.textContent) {
        try {
            allPatrols = JSON.parse(dataEl.textContent);
        } catch (e) {
            console.error("Error parsing initial patrols JSON:", e);
        }
    }

    initEventListeners();
    renderPatrolsTable();
    updateSummaryCards();

    // Auto-select first patrol if available
    if (allPatrols.length > 0) {
        openPatrolDetail(allPatrols[0].patrol_code);
    }

    // Auto-refresh every 10 seconds
    setInterval(fetchPatrols, 10000);
});

function initEventListeners() {
    // Search and Filter
    const searchInput = document.getElementById('admin-search-patrol');
    if (searchInput) {
        searchInput.addEventListener('input', renderPatrolsTable);
    }

    const filterSelect = document.getElementById('admin-filter-status');
    if (filterSelect) {
        filterSelect.addEventListener('change', renderPatrolsTable);
    }

    // Weight slider
    const weightSlider = document.getElementById('weight-ratio-slider');
    if (weightSlider) {
        weightSlider.addEventListener('input', onWeightSliderChange);
    }

    const saveWeightBtn = document.getElementById('btn-save-weights');
    if (saveWeightBtn) {
        saveWeightBtn.addEventListener('click', saveWeights);
    }

    // Decision buttons
    document.querySelectorAll('.btn-decision').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.btn-decision').forEach(b => b.classList.remove('selected'));
            const targetBtn = e.currentTarget;
            targetBtn.classList.add('selected');
            selectedDecision = targetBtn.dataset.decision;

            const speedWrap = document.getElementById('speed-restriction-input-wrap');
            if (speedWrap) {
                speedWrap.style.display = selectedDecision === 'restricted' ? 'block' : 'none';
            }
        });
    });

    const submitDecisionBtn = document.getElementById('btn-submit-decision');
    if (submitDecisionBtn) {
        submitDecisionBtn.addEventListener('click', submitDecision);
    }
}

async function fetchPatrols() {
    try {
        const resp = await fetch('/api/patrol/reports/');
        const data = await resp.json();
        if (data.status === 'success' && data.patrols) {
            allPatrols = data.patrols;
            updateSummaryCards();
            renderPatrolsTable();

            // Refresh open detail if active
            if (selectedPatrolCode) {
                const refreshed = allPatrols.find(p => p.patrol_code === selectedPatrolCode);
                if (refreshed && currentPatrol && refreshed.updated_at !== currentPatrol.updated_at) {
                    currentPatrol = refreshed;
                    renderDetailView(currentPatrol);
                }
            }
        }
    } catch (err) {
        console.error("Polling fetch error:", err);
    }
}

function updateSummaryCards() {
    const totalCount = allPatrols.length;
    const pendingCount = allPatrols.filter(p => p.admin_decision === 'pending' || p.status !== 'decided').length;
    const conflictCount = allPatrols.filter(p => p.conflict_detected).length;
    const decidedCount = allPatrols.filter(p => p.admin_decision !== 'pending' && p.status === 'decided').length;

    const elTotal = document.getElementById('kpi-total-patrols');
    if (elTotal) elTotal.textContent = totalCount;

    const elPending = document.getElementById('kpi-pending-patrols');
    if (elPending) elPending.textContent = pendingCount;

    const elConflicts = document.getElementById('kpi-conflicts-detected');
    if (elConflicts) elConflicts.textContent = conflictCount;

    const elDecided = document.getElementById('kpi-decided-patrols');
    if (elDecided) elDecided.textContent = decidedCount;
}

function renderPatrolsTable() {
    const tbody = document.getElementById('admin-patrols-tbody');
    if (!tbody) return;

    const search = (document.getElementById('admin-search-patrol')?.value || '').toLowerCase();
    const filter = document.getElementById('admin-filter-status')?.value || 'all';

    const filtered = allPatrols.filter(p => {
        const matchSearch = p.patrol_code.toLowerCase().includes(search) ||
                            (p.worker && p.worker.toLowerCase().includes(search)) ||
                            (p.section_name && p.section_name.toLowerCase().includes(search));

        if (!matchSearch) return false;

        if (filter === 'conflicts') return p.conflict_detected;
        if (filter === 'pending') return p.status !== 'decided';
        if (filter === 'decided') return p.status === 'decided';
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--text-tertiary);padding:2rem;">No matching patrol reports.</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(p => {
        let statusBadge = `<span class="patrol-badge">${p.status_display}</span>`;
        if (p.status === 'decided') {
            statusBadge = `<span class="patrol-badge patrol-badge-green">${p.admin_decision_display || 'Decided'}</span>`;
        } else if (p.conflict_detected) {
            statusBadge = `<span class="patrol-badge patrol-badge-red">Conflict Alert</span>`;
        }

        const isSelected = p.patrol_code === selectedPatrolCode;
        const rowStyle = isSelected ? 'background:rgba(201, 162, 74, 0.12);' : '';

        return `
            <tr class="clickable-row" onclick="openPatrolDetail('${p.patrol_code}')" style="${rowStyle}">
                <td class="mono" style="font-weight:700;color:var(--gold-soft);">${p.patrol_code}</td>
                <td><span style="font-weight:500;">${p.worker_name || p.worker}</span></td>
                <td>${p.section_name}</td>
                <td class="mono">${p.worker_overall_score !== null ? p.worker_overall_score.toFixed(1) : '--'}</td>
                <td class="mono">${p.iot_overall_score !== null ? p.iot_overall_score.toFixed(1) : '--'}</td>
                <td class="mono" style="font-weight:700;color:var(--emerald-soft);">${p.composite_score !== null ? p.composite_score.toFixed(1) : '--'}</td>
                <td>${statusBadge}</td>
                <td style="color:var(--text-secondary);font-size:0.8rem;">${p.created_at || '--'}</td>
            </tr>
        `;
    }).join('');
}

async function openPatrolDetail(patrolCode) {
    selectedPatrolCode = patrolCode;
    renderPatrolsTable();

    try {
        const resp = await fetch(`/api/patrol/${patrolCode}/`);
        const data = await resp.json();
        if (data.status === 'success' && data.patrol) {
            currentPatrol = data.patrol;
            renderDetailView(currentPatrol);
        }
    } catch (err) {
        console.error("Failed to load patrol detail:", err);
    }
}

function renderDetailView(patrol) {
    const detailPanel = document.getElementById('admin-detail-panel');
    if (!detailPanel) return;
    detailPanel.style.display = 'block';

    // Header info
    document.getElementById('detail-patrol-code').textContent = patrol.patrol_code;
    document.getElementById('detail-route-title').textContent = `${patrol.section_name} (${patrol.track_section_code})`;
    document.getElementById('detail-worker-name').textContent = patrol.worker_name || patrol.worker;

    // Conflict banner
    const conflictBanner = document.getElementById('detail-conflict-banner');
    if (conflictBanner) {
        conflictBanner.style.display = patrol.conflict_detected ? 'flex' : 'none';
    }

    // Worker category ratings breakdown
    renderWorkerCategoryBars(patrol.category_ratings || []);

    // IoT Telemetry Charts
    renderIoTCharts(patrol.iot_readings || []);

    // ML prediction summary
    const mlSummary = document.getElementById('detail-ml-summary');
    if (mlSummary && patrol.iot_prediction) {
        const p = patrol.iot_prediction;
        const anomalyScore = p.anomaly_score !== undefined ? (p.anomaly_score * 100).toFixed(1) + '%' : 'N/A';
        const fault = p.fault_type_display || p.fault_type || 'Nominal';
        mlSummary.innerHTML = `
            <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.4rem;">
                <span style="color:var(--text-secondary);">Anomaly Risk:</span>
                <span class="mono" style="font-weight:700;color:${p.anomaly_score > 0.5 ? '#f87171' : '#4ade80'};">${anomalyScore}</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.85rem;">
                <span style="color:var(--text-secondary);">Primary Flavour / Fault:</span>
                <span class="mono" style="color:var(--gold-soft);">${patrol.iot_scenario_flavour || fault}</span>
            </div>
        `;
    }

    // Weight slider
    const slider = document.getElementById('weight-ratio-slider');
    if (slider) {
        slider.value = Math.round(patrol.worker_weight * 100);
        updateWeightLabels(patrol.worker_weight, patrol.iot_weight);
    }

    // Composite gauge
    updateCompositeGauge(patrol.composite_score);

    // Decision status & notes
    const decisionStateEl = document.getElementById('detail-decision-state');
    if (decisionStateEl) {
        if (patrol.status === 'decided') {
            decisionStateEl.innerHTML = `
                <div class="patrol-badge patrol-badge-green" style="font-size:0.9rem;padding:0.4rem 0.8rem;">
                    Decided: ${patrol.admin_decision_display} by ${patrol.admin_decision_by}
                </div>
                ${patrol.admin_notes ? `<div style="font-size:0.825rem;color:var(--text-secondary);margin-top:0.4rem;"><strong>Notes:</strong> ${patrol.admin_notes}</div>` : ''}
            `;
        } else {
            decisionStateEl.innerHTML = `<span class="patrol-badge patrol-badge-amber">Decision Pending</span>`;
        }
    }
}

function renderWorkerCategoryBars(ratings) {
    const container = document.getElementById('worker-ratings-bars');
    if (!container) return;

    if (ratings.length === 0) {
        container.innerHTML = `<div style="color:var(--text-tertiary);font-size:0.85rem;">No category ratings recorded.</div>`;
        return;
    }

    const colors = {
        1: '#ef4444',
        2: '#f97316',
        3: '#f59e0b',
        4: '#3b82f6',
        5: '#10b981'
    };

    container.innerHTML = ratings.map(r => {
        const pct = (r.rating / 5) * 100;
        const color = colors[r.rating] || '#10b981';
        return `
            <div class="cat-bar-row">
                <div class="cat-bar-label-wrap">
                    <span style="font-weight:500;color:var(--text-primary);">${r.category_display}</span>
                    <span class="mono" style="color:${color};font-weight:700;">${r.rating_label} (${r.rating}/5)</span>
                </div>
                <div class="cat-bar-track">
                    <div class="cat-bar-fill" style="width:${pct}%;background:${color};"></div>
                </div>
                ${r.notes ? `<div style="font-size:0.75rem;color:var(--text-tertiary);font-style:italic;">"${r.notes}"</div>` : ''}
            </div>
        `;
    }).join('');
}

function renderIoTCharts(readings) {
    if (!window.Chart) return;

    const labels = readings.map((_, i) => `T${i + 1}`);
    const temps = readings.map(r => r.ambient_temp);
    const hums = readings.map(r => r.humidity);
    const vibs = readings.map(r => r.vibration_rms);
    const gauges = readings.map(r => r.gauge_width);

    // Latest values display
    if (readings.length > 0) {
        const last = readings[readings.length - 1];
        const tVal = document.getElementById('val-iot-temp');
        if (tVal) tVal.textContent = last.ambient_temp + ' °C';
        const hVal = document.getElementById('val-iot-hum');
        if (hVal) hVal.textContent = last.humidity + ' %';
        const vVal = document.getElementById('val-iot-vib');
        if (vVal) vVal.textContent = last.vibration_rms + ' mm/s';
        const gVal = document.getElementById('val-iot-gauge');
        if (gVal) gVal.textContent = last.gauge_width + ' mm';
    }

    createOrUpdateMiniChart('chart-temp', labels, temps, '#f97316', 'Ambient Temp (°C)');
    createOrUpdateMiniChart('chart-hum', labels, hums, '#38bdf8', 'Humidity (%)');
    createOrUpdateMiniChart('chart-vib', labels, vibs, '#ef4444', 'Vibration (mm/s)');
    createOrUpdateMiniChart('chart-gauge', labels, gauges, '#c9a24a', 'Gauge Width (mm)');
}

function createOrUpdateMiniChart(canvasId, labels, data, color, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }

    const ctx = canvas.getContext('2d');
    chartInstances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: color,
                backgroundColor: color + '22',
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointRadius: 2,
                pointHoverRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                x: { display: false },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        }
    });
}

function onWeightSliderChange(e) {
    const wVal = parseInt(e.target.value);
    const workerWeight = wVal / 100;
    const iotWeight = (100 - wVal) / 100;

    updateWeightLabels(workerWeight, iotWeight);

    if (currentPatrol && currentPatrol.worker_overall_score !== null && currentPatrol.iot_overall_score !== null) {
        const previewScore = (workerWeight * currentPatrol.worker_overall_score) + (iotWeight * currentPatrol.iot_overall_score);
        updateCompositeGauge(previewScore);
    }
}

function updateWeightLabels(wWeight, iWeight) {
    const wLabel = document.getElementById('label-worker-weight');
    if (wLabel) wLabel.textContent = `Worker: ${Math.round(wWeight * 100)}%`;

    const iLabel = document.getElementById('label-iot-weight');
    if (iLabel) iLabel.textContent = `IoT: ${Math.round(iWeight * 100)}%`;
}

async function saveWeights() {
    if (!selectedPatrolCode) return;

    const slider = document.getElementById('weight-ratio-slider');
    const wVal = parseInt(slider.value);
    const worker_weight = wVal / 100;
    const iot_weight = (100 - wVal) / 100;

    const saveBtn = document.getElementById('btn-save-weights');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const resp = await fetch(`/api/patrol/${selectedPatrolCode}/weights/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ worker_weight, iot_weight })
        });

        const data = await resp.json();
        if (data.status === 'success' && data.patrol) {
            currentPatrol = data.patrol;
            renderDetailView(currentPatrol);
            fetchPatrols();
            alert("Weights updated and composite score recalculated.");
        } else {
            alert("Failed to update weights: " + (data.message || "Unknown error"));
        }
    } catch (e) {
        console.error("Save weights error:", e);
        alert("Network error.");
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Apply & Recompute';
    }
}

function updateCompositeGauge(score) {
    const scoreVal = score !== null && score !== undefined ? parseFloat(score) : 0;
    const numEl = document.getElementById('gauge-score-value');
    if (numEl) {
        numEl.textContent = score !== null ? scoreVal.toFixed(1) : '--';
        if (scoreVal >= 75) numEl.style.color = '#10b981';
        else if (scoreVal >= 50) numEl.style.color = '#f59e0b';
        else numEl.style.color = '#ef4444';
    }

    const circle = document.getElementById('gauge-circle-fill');
    if (circle) {
        // Circumference of r=70 is 2 * PI * 70 = 439.82
        const circumference = 2 * Math.PI * 70;
        const offset = circumference - (scoreVal / 100) * circumference;
        circle.style.strokeDashoffset = offset;
        if (scoreVal >= 75) circle.style.stroke = '#10b981';
        else if (scoreVal >= 50) circle.style.stroke = '#f59e0b';
        else circle.style.stroke = '#ef4444';
    }
}

async function submitDecision() {
    if (!selectedPatrolCode) {
        alert("Please select a patrol case first.");
        return;
    }
    if (!selectedDecision) {
        alert("Please select a Go/No-Go decision (Cleared, Speed Restriction, or Blocked).");
        return;
    }

    const notes = document.getElementById('admin-decision-notes')?.value || '';
    const speed = document.getElementById('input-speed-restriction')?.value || 0;

    const submitBtn = document.getElementById('btn-submit-decision');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Recording Decision...';

    try {
        const resp = await fetch(`/api/patrol/${selectedPatrolCode}/decide/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({
                decision: selectedDecision,
                notes: notes,
                speed_restriction: parseInt(speed) || 0,
            })
        });

        const data = await resp.json();
        if (data.status === 'success') {
            alert(`Decision recorded successfully: ${selectedDecision.toUpperCase()}`);
            currentPatrol = data.patrol;
            renderDetailView(currentPatrol);
            fetchPatrols();
        } else {
            alert("Error recording decision: " + (data.message || "Unknown error"));
        }
    } catch (e) {
        console.error("Decision submit error:", e);
        alert("Network error while submitting decision.");
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Controller Decision';
    }
}
