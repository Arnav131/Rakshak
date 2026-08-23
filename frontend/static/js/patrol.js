/**
 * Rakshak — Worker Patrol System JavaScript
 * frontend/static/js/patrol.js
 */

let activePatrolCode = null;

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

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

const RATING_LABELS = {
    1: { text: "Critical (1/5)", class: "rating-1" },
    2: { text: "Poor (2/5)", class: "rating-2" },
    3: { text: "Fair (3/5)", class: "rating-3" },
    4: { text: "Good (4/5)", class: "rating-4" },
    5: { text: "Excellent (5/5)", class: "rating-5" }
};

document.addEventListener('DOMContentLoaded', () => {
    initCategorySliders();
    initQuickPresets();
    initPatrolButtons();
});

function initCategorySliders() {
    document.querySelectorAll('.rating-slider').forEach(slider => {
        slider.addEventListener('input', (e) => {
            const category = e.target.dataset.category;
            const val = parseInt(e.target.value);
            const badge = document.getElementById(`badge-${category}`);
            if (badge && RATING_LABELS[val]) {
                badge.className = `rating-badge ${RATING_LABELS[val].class}`;
                badge.textContent = RATING_LABELS[val].text;
            }
        });
    });
}

function initQuickPresets() {
    const btnAll5 = document.getElementById('btn-preset-nominal');
    const btnAll4 = document.getElementById('btn-preset-good');
    const btnDegraded = document.getElementById('btn-preset-degraded');

    if (btnAll5) {
        btnAll5.addEventListener('click', () => setAllRatings(5, "Nominal condition verified. All parameters strictly within RDSO safety envelopes."));
    }
    if (btnAll4) {
        btnAll4.addEventListener('click', () => setAllRatings(4, "Minor wear observed; routine re-greasing / tightening recommended on next cycle."));
    }
    if (btnDegraded) {
        btnDegraded.addEventListener('click', () => {
            const pattern = [2, 3, 2, 2, 3, 2, 3, 2];
            let i = 0;
            document.querySelectorAll('.rating-slider').forEach(slider => {
                const val = pattern[i % pattern.length];
                slider.value = val;
                const cat = slider.dataset.category;
                const badge = document.getElementById(`badge-${cat}`);
                if (badge && RATING_LABELS[val]) {
                    badge.className = `rating-badge ${RATING_LABELS[val].class}`;
                    badge.textContent = RATING_LABELS[val].text;
                }
                const notesInput = document.getElementById(`notes-${cat}`);
                if (notesInput) {
                    notesInput.value = "Defects and loosening detected; attention required.";
                }
                i++;
            });
        });
    }
}

function setAllRatings(val, defaultNote) {
    document.querySelectorAll('.rating-slider').forEach(slider => {
        slider.value = val;
        const cat = slider.dataset.category;
        const badge = document.getElementById(`badge-${cat}`);
        if (badge && RATING_LABELS[val]) {
            badge.className = `rating-badge ${RATING_LABELS[val].class}`;
            badge.textContent = RATING_LABELS[val].text;
        }
        const notesInput = document.getElementById(`notes-${cat}`);
        if (notesInput) {
            notesInput.value = defaultNote;
        }
    });
}

function initPatrolButtons() {
    const startBtn = document.getElementById('btn-start-patrol');
    if (startBtn) {
        startBtn.addEventListener('click', startPatrol);
    }

    const submitBtn = document.getElementById('btn-submit-ratings');
    if (submitBtn) {
        submitBtn.addEventListener('click', submitRatings);
    }
}

async function startPatrol() {
    const sectionSelect = document.getElementById('select-track-section');
    const trackSectionId = sectionSelect ? sectionSelect.value : null;

    if (!trackSectionId) {
        alert("Please select a valid track section to inspect.");
        return;
    }

    const startBtn = document.getElementById('btn-start-patrol');
    startBtn.disabled = true;
    startBtn.innerHTML = `<span>Starting...</span>`;

    try {
        const resp = await fetch('/api/patrol/start/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ track_section_id: trackSectionId })
        });

        const data = await resp.json();
        if (data.status === 'success') {
            activePatrolCode = data.patrol_code;

            // Update UI elements
            document.getElementById('active-patrol-banner').style.display = 'flex';
            document.getElementById('display-patrol-code').textContent = activePatrolCode;
            document.getElementById('display-patrol-section').textContent = sectionSelect.options[sectionSelect.selectedIndex].text;
            
            // Show Inspection Form
            document.getElementById('inspection-form-container').style.display = 'block';
            document.getElementById('btn-submit-ratings').disabled = false;
            
            // Scroll to inspection form
            document.getElementById('inspection-form-container').scrollIntoView({ behavior: 'smooth' });
        } else {
            alert("Error starting patrol: " + (data.message || "Unknown error"));
        }
    } catch (err) {
        console.error("Start patrol error:", err);
        alert("Failed to communicate with server.");
    } finally {
        startBtn.disabled = false;
        startBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg> Start Inspection`;
    }
}

async function submitRatings() {
    if (!activePatrolCode) {
        alert("No active patrol session in progress. Please start a patrol first.");
        return;
    }

    const ratings = [];
    document.querySelectorAll('.rating-slider').forEach(slider => {
        const category = slider.dataset.category;
        const rating = parseInt(slider.value);
        const notesEl = document.getElementById(`notes-${category}`);
        const notes = notesEl ? notesEl.value : "";
        ratings.push({ category, rating, notes });
    });

    const submitBtn = document.getElementById('btn-submit-ratings');
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
        <span style="display:inline-flex;align-items:center;gap:0.5rem;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
            Generating Post-Inspection IoT & ML Telemetry...
        </span>
    `;

    try {
        const resp = await fetch(`/api/patrol/${activePatrolCode}/submit/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ ratings })
        });

        const data = await resp.json();
        if (data.status === 'success') {
            const patrol = data.patrol;
            showSubmissionResult(patrol);
            reloadMyPatrols();
        } else {
            alert("Error submitting patrol: " + (data.message || "Unknown error"));
            submitBtn.disabled = false;
            submitBtn.innerHTML = `Submit Inspection Report`;
        }
    } catch (err) {
        console.error("Submit patrol error:", err);
        alert("Network error while submitting patrol report.");
        submitBtn.disabled = false;
        submitBtn.innerHTML = `Submit Inspection Report`;
    }
}

function showSubmissionResult(patrol) {
    const resultBox = document.getElementById('submission-result-card');
    if (!resultBox) return;

    resultBox.style.display = 'block';
    document.getElementById('res-patrol-code').textContent = patrol.patrol_code;
    document.getElementById('res-worker-score').textContent = (patrol.worker_overall_score !== null ? patrol.worker_overall_score.toFixed(1) : "--") + " / 100";
    document.getElementById('res-iot-score').textContent = (patrol.iot_overall_score !== null ? patrol.iot_overall_score.toFixed(1) : "--") + " / 100";
    document.getElementById('res-composite-score').textContent = (patrol.composite_score !== null ? patrol.composite_score.toFixed(1) : "--") + " / 100";

    const conflictBadge = document.getElementById('res-conflict-badge');
    if (conflictBadge) {
        if (patrol.conflict_detected) {
            conflictBadge.className = "patrol-badge patrol-badge-red";
            conflictBadge.textContent = "CONFLICT DETECTED (>30 pt Discrepancy)";
        } else {
            conflictBadge.className = "patrol-badge patrol-badge-green";
            conflictBadge.textContent = "Worker & IoT In Concordance";
        }
    }

    // Scroll to results
    resultBox.scrollIntoView({ behavior: 'smooth' });

    // Reset submit button
    const submitBtn = document.getElementById('btn-submit-ratings');
    submitBtn.innerHTML = `Inspection Submitted Successfully ✅`;
    submitBtn.disabled = true;
}

async function reloadMyPatrols() {
    try {
        const resp = await fetch('/api/patrol/reports/');
        const data = await resp.json();
        if (data.status === 'success' && data.patrols) {
            renderPatrolTable(data.patrols);
        }
    } catch (e) {
        console.error("Failed to reload history:", e);
    }
}

function renderPatrolTable(patrols) {
    const tbody = document.getElementById('my-patrols-tbody');
    if (!tbody) return;

    if (patrols.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-tertiary);padding:2rem;">No patrol reports submitted yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = patrols.map(p => {
        let statusBadge = `<span class="patrol-badge">${escapeHtml(p.status_display)}</span>`;
        if (p.status === 'decided') {
            statusBadge = `<span class="patrol-badge patrol-badge-green">${escapeHtml(p.admin_decision_display || 'Decided')}</span>`;
        } else if (p.conflict_detected) {
            statusBadge = `<span class="patrol-badge patrol-badge-red">Conflict Alert</span>`;
        }

        return `
            <tr>
                <td class="mono" style="font-weight:600;color:var(--gold-soft);">${escapeHtml(p.patrol_code)}</td>
                <td>${escapeHtml(p.section_name)}</td>
                <td class="mono">${p.worker_overall_score !== null ? p.worker_overall_score.toFixed(1) : '--'}</td>
                <td class="mono">${p.iot_overall_score !== null ? p.iot_overall_score.toFixed(1) : '--'}</td>
                <td class="mono" style="font-weight:700;color:var(--emerald-soft);">${p.composite_score !== null ? p.composite_score.toFixed(1) : '--'}</td>
                <td>${statusBadge}</td>
                <td style="color:var(--text-secondary);font-size:0.8rem;">${escapeHtml(p.created_at || '--')}</td>
            </tr>
        `;
    }).join('');
}
