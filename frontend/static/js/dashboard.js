// frontend/static/js/dashboard.js
//
// Rakshak - Core JavaScript
// Handles: live clock, KPI counter animations, Chart.js initialization,
//          sidebar behavior, and shared utilities.
// This file is loaded on every page via base.html.

'use strict';

// ====================================================================
// LIVE CLOCK — Updates every second with IST time
// ====================================================================
function initLiveClock() {
    const clockTime = document.getElementById('clock-time');
    const clockDate = document.getElementById('clock-date');

    if (!clockTime) return;

    function updateClock() {
        const now = new Date();
        clockTime.textContent = new Intl.DateTimeFormat('en-IN', {
            timeZone: 'Asia/Kolkata',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        }).format(now);
        clockDate.textContent = new Intl.DateTimeFormat('en-IN', {
            timeZone: 'Asia/Kolkata',
            weekday: 'short',
            day: '2-digit',
            month: 'short',
            year: 'numeric',
        }).format(now);
    }

    updateClock();
    setInterval(updateClock, 1000);
}

// ====================================================================
// KPI COUNTER ANIMATION — Animates numbers from 0 to target
// ====================================================================
function animateCounters() {
    const counters = document.querySelectorAll('.num[data-target], .kpi-item-value[data-target]');

    counters.forEach(counter => {
        const target = parseFloat(counter.getAttribute('data-target'));
        const duration = 1500; // milliseconds
        const startTime = performance.now();
        const isDecimal = target % 1 !== 0;

        // Format large numbers with Indian locale (Lakhs/Crores)
        function formatValue(val) {
            if (target >= 100000) {
                // Format as Lakhs: 24,50,000 → "24.5L"
                return (val / 100000).toFixed(1) + 'L';
            }
            if (isDecimal) {
                return val.toFixed(1);
            }
            return Math.round(val).toLocaleString('en-IN');
        }

        function step(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease-out cubic for smooth deceleration
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = eased * target;

            counter.textContent = formatValue(current);

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }

        requestAnimationFrame(step);
    });
}

// ====================================================================
// CHART.JS INITIALIZATION — Sensor trend charts on the dashboard
// ====================================================================

// Shared Chart.js defaults — theme-aware
// Shared Chart.js defaults — glass-themed
function getCompactChartDefaults() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(36, 27, 44, 0.94)',
                titleColor: '#f5f3f7',
                bodyColor: '#a89db0',
                borderColor: 'rgba(240, 168, 200, 0.16)',
                borderWidth: 1,
                padding: 10,
                cornerRadius: 10,
                titleFont: { family: 'Sora', size: 11, weight: '600' },
                bodyFont: { family: 'IBM Plex Mono', size: 10 },
                boxPadding: 3,
                usePointStyle: true,
            },
        },
        scales: {
            x: {
                display: false,
            },
            y: {
                grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
                ticks: { color: '#6f6579', font: { family: 'IBM Plex Mono', size: 9 }, maxTicksLimit: 4 },
            },
        },
    };
}

/**
 * Create a gradient fill for line charts.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} colorTop - Top color (RGBA)
 * @param {string} colorBottom - Bottom color (RGBA)
 * @returns {CanvasGradient}
 */
function createGradient(ctx, colorTop, colorBottom) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, colorTop);
    gradient.addColorStop(1, colorBottom);
    return gradient;
}

// Store chart instances globally to allow destruction
window.rakshakChartInstances = window.rakshakChartInstances || {};

function getChartColorConfig(type, values) {
    if (!values || values.length === 0) return { main: '#4fbf7a', bg: 'rgba(79,191,122,0.22)', status: 'healthy' };
    const lastValue = values[values.length - 1];
    let status = 'healthy';
    
    if (type === 'vibration') {
        if (lastValue > 5.0) status = 'critical';
        else if (lastValue >= 3.5) status = 'warning';
    } else if (type === 'temperature') {
        if (lastValue > 50) status = 'critical';
        else if (lastValue >= 40) status = 'warning';
    } else if (type === 'gauge') {
        const absVal = Math.abs(lastValue);
        if (absVal > 6) status = 'critical';
        else if (absVal >= 2) status = 'warning';
    } else if (type === 'acoustic') {
        status = 'healthy';
    } else if (type === 'strain') {
        if (lastValue > 3.5) status = 'critical';
        else if (lastValue >= 2.5) status = 'warning';
    } else if (type === 'accelerometer') {
        if (lastValue > 1.8) status = 'critical';
        else if (lastValue >= 1.2) status = 'warning';
    }

    if (status === 'critical') return { main: '#f28b8b', bg: 'rgba(242,139,139,0.22)', status: status };
    if (status === 'warning') return { main: '#e0c07a', bg: 'rgba(224,192,122,0.22)', status: status };
    return { main: '#4fbf7a', bg: 'rgba(79,191,122,0.20)', status: status };
}

/**
 * Generate plain-English data insight for a chart.
 * This makes graphs understandable to non-technical judges.
 */
function generateDataInsight(type, values) {
    if (!values || values.length < 2) return { text: 'Collecting data...', level: 'info' };
    
    const last = values[values.length - 1];
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const max = Math.max(...values);
    const min = Math.min(...values);
    const trend = values[values.length - 1] - values[Math.max(0, values.length - 6)];
    const trendDir = trend > 0.1 ? 'rising' : trend < -0.1 ? 'falling' : 'stable';
    const trendIcon = trend > 0.1 ? '↑' : trend < -0.1 ? '↓' : '→';
    
    let insight = { text: '', level: 'healthy' };
    
    if (type === 'vibration') {
        if (last > 5.0) {
            insight = { text: `Vibration is <strong>critically high</strong> at ${last.toFixed(1)} mm/s ${trendIcon} — immediate inspection needed`, level: 'critical' };
        } else if (last >= 3.5) {
            insight = { text: `Vibration <strong>approaching threshold</strong> at ${last.toFixed(1)} mm/s ${trendIcon} — monitor closely`, level: 'warning' };
        } else {
            insight = { text: `Vibration <strong>within safe range</strong> at ${last.toFixed(1)} mm/s ${trendIcon} — all clear`, level: 'healthy' };
        }
    } else if (type === 'temperature') {
        if (last > 50) {
            insight = { text: `Rail temp <strong>dangerously high</strong> at ${last.toFixed(0)}°C ${trendIcon} — risk of track buckling`, level: 'critical' };
        } else if (last >= 40) {
            insight = { text: `Rail temp <strong>elevated</strong> at ${last.toFixed(0)}°C ${trendIcon} — ${trendDir === 'rising' ? 'still rising' : 'stabilizing'}`, level: 'warning' };
        } else {
            insight = { text: `Rail temp <strong>normal</strong> at ${last.toFixed(0)}°C ${trendIcon} — safe operating range`, level: 'healthy' };
        }
    } else if (type === 'gauge') {
        const absLast = Math.abs(last);
        if (absLast > 6) {
            insight = { text: `Gauge deviation <strong>critical</strong> at ${last.toFixed(1)}mm ${trendIcon} — track alignment issue`, level: 'critical' };
        } else if (absLast >= 2) {
            insight = { text: `Gauge deviation <strong>notable</strong> at ${last.toFixed(1)}mm ${trendIcon} — schedule inspection`, level: 'warning' };
        } else {
            insight = { text: `Gauge deviation <strong>minimal</strong> at ${last.toFixed(1)}mm ${trendIcon} — track well-aligned`, level: 'healthy' };
        }
    } else if (type === 'strain') {
        if (last > 3.5) {
            insight = { text: `Strain load <strong>excessive</strong> at ${last.toFixed(1)} kN ${trendIcon} — structural stress detected`, level: 'critical' };
        } else if (last >= 2.5) {
            insight = { text: `Strain load <strong>elevated</strong> at ${last.toFixed(1)} kN ${trendIcon} — increased traffic load`, level: 'warning' };
        } else {
            insight = { text: `Strain load <strong>normal</strong> at ${last.toFixed(1)} kN ${trendIcon} — structure healthy`, level: 'healthy' };
        }
    }
    
    return insight;
}

/**
 * Update the data-insight box in the DOM for a chart.
 */
function generateDataInsight(type, values) {
    if (!values || values.length < 2) return { text: 'Collecting data...', level: 'info' };

    const last = values[values.length - 1];
    const trend = values[values.length - 1] - values[Math.max(0, values.length - 6)];
    const trendDir = trend > 0.1 ? 'rising' : trend < -0.1 ? 'falling' : 'stable';
    const trendLabel = trend > 0.1 ? 'up' : trend < -0.1 ? 'down' : 'steady';

    if (type === 'vibration') {
        if (last > 5.0) return { text: `Vibration is <strong>critically high</strong> at ${last.toFixed(1)} mm/s (${trendLabel}) - immediate inspection needed`, level: 'critical' };
        if (last >= 3.5) return { text: `Vibration <strong>approaching threshold</strong> at ${last.toFixed(1)} mm/s (${trendLabel}) - monitor closely`, level: 'warning' };
        return { text: `Vibration <strong>within safe range</strong> at ${last.toFixed(1)} mm/s (${trendLabel}) - all clear`, level: 'healthy' };
    }

    if (type === 'temperature') {
        if (last > 50) return { text: `Rail temp <strong>dangerously high</strong> at ${last.toFixed(0)} deg C (${trendLabel}) - buckling risk`, level: 'critical' };
        if (last >= 40) return { text: `Rail temp <strong>elevated</strong> at ${last.toFixed(0)} deg C (${trendLabel}) - ${trendDir === 'rising' ? 'still rising' : 'stabilizing'}`, level: 'warning' };
        return { text: `Rail temp <strong>normal</strong> at ${last.toFixed(0)} deg C (${trendLabel}) - safe range`, level: 'healthy' };
    }

    if (type === 'gauge') {
        const absLast = Math.abs(last);
        if (absLast > 6) return { text: `Gauge deviation <strong>critical</strong> at ${last.toFixed(1)}mm (${trendLabel}) - alignment issue`, level: 'critical' };
        if (absLast >= 2) return { text: `Gauge deviation <strong>notable</strong> at ${last.toFixed(1)}mm (${trendLabel}) - schedule inspection`, level: 'warning' };
        return { text: `Gauge deviation <strong>minimal</strong> at ${last.toFixed(1)}mm (${trendLabel}) - well aligned`, level: 'healthy' };
    }

    if (type === 'strain') {
        if (last > 3.5) return { text: `Strain load <strong>excessive</strong> at ${last.toFixed(1)} kN (${trendLabel}) - structural stress`, level: 'critical' };
        if (last >= 2.5) return { text: `Strain load <strong>elevated</strong> at ${last.toFixed(1)} kN (${trendLabel}) - traffic load rising`, level: 'warning' };
        return { text: `Strain load <strong>normal</strong> at ${last.toFixed(1)} kN (${trendLabel}) - structure healthy`, level: 'healthy' };
    }

    return { text: 'Telemetry stream healthy.', level: 'healthy' };
}

function updateDataInsightUI(chartId, type, values) {
    const el = document.getElementById(`insight-${chartId}`);
    if (!el) return;
    const insight = generateDataInsight(type, values);
    el.innerHTML = insight.text;
    el.className = 'data-insight';
    if (insight.level === 'warning') el.classList.add('data-insight--warning');
    else if (insight.level === 'critical') el.classList.add('data-insight--critical');
}

function updateChartStats(id, values, statsData, statKey) {
    const latestEl = document.getElementById(`stat-${id}-latest`);
    const maxEl = document.getElementById(`stat-${id}-max`);
    const minEl = document.getElementById(`stat-${id}-min`);
    if (latestEl && values && values.length > 0) {
        const latest = values[values.length - 1];
        latestEl.textContent = id === 'temperature' ? latest.toFixed(0) : latest.toFixed(2);
    }
    if (maxEl && minEl) {
        if (statsData && statsData[statKey]) {
            maxEl.textContent = statsData[statKey].max.toFixed(2);
            minEl.textContent = statsData[statKey].min.toFixed(2);
        } else if (values && values.length > 0) {
            maxEl.textContent = Math.max(...values).toFixed(2);
            minEl.textContent = Math.min(...values).toFixed(2);
        }
    }
}

/**
 * Initialize all six dashboard sensor trend charts.
 * Called from dashboard.html after DOM load with parsed JSON data.
 * @param {Object} data - Sensor trend data
 */
function initDashboardCharts(data) {
    // Only run on pages that have the chart canvases
    if (!document.getElementById('chart-vibration')) return;

    // Store data for re-rendering if needed
    window.rakshakLastChartData = data;

    // Destroy existing instances
    ['vibration', 'temperature', 'gauge', 'strain'].forEach(type => {
        if (window.rakshakChartInstances[type]) {
            window.rakshakChartInstances[type].destroy();
        }
    });

    const timestamps = data.timestamps;
    
    function createCompactChart(id, label, values, statsKey) {
        const canvas = document.getElementById(`chart-${id}`);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const colors = getChartColorConfig(id, values);
        const pointBg = '#1a1420';
        
        window.rakshakChartInstances[id] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [{
                    label: label,
                    data: values,
                    borderColor: colors.main,
                    backgroundColor: createGradient(ctx, colors.bg, 'rgba(0,0,0,0)'),
                    borderWidth: 2.25,
                    pointBackgroundColor: colors.main,
                    pointBorderColor: pointBg,
                    pointBorderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: colors.main,
                    pointHoverBorderColor: '#ffffff',
                    pointHoverBorderWidth: 2,
                    fill: true,
                    tension: 0.42,
                }],
            },
            options: getCompactChartDefaults(),
        });
        
        updateChartStats(id, values, data.sensor_stats, statsKey || id);
        updateDataInsightUI(id, id === 'gauge' ? 'gauge' : (id === 'strain' ? 'strain' : id), values);
    }

    createCompactChart('vibration', 'Vibration (mm/s)', data.vibration);
    createCompactChart('temperature', 'Temperature (deg C)', data.temperature);
    createCompactChart('gauge', 'Gauge Deviation (mm)', data.gauge_deviation, 'gauge_deviation');
    createCompactChart('strain', 'Strain Gauge Load (kN)', data.strain_gauge_load, 'strain_gauge_load');
}

function initSystemSummaryChart(summary) {
    const canvas = document.getElementById('system-summary-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    const labels = Array.isArray(summary && summary.labels) ? summary.labels : [];
    const values = Array.isArray(summary && summary.values)
        ? summary.values.map(value => Number(value) || 0)
        : [];
    const total = values.reduce((sum, value) => sum + value, 0);
    const chartLabels = total > 0 ? labels : ['No records'];
    const chartValues = total > 0 ? values : [1];
    const legendValues = total > 0 ? values : [0];
    const colors = total > 0
        ? ['#4fbf7a', '#e0c07a', '#f28b8b', '#7fb0ff', '#c9a24a']
        : ['rgba(168,157,176,0.28)'];

    if (window.rakshakChartInstances.systemSummary) {
        window.rakshakChartInstances.systemSummary.destroy();
    }

    window.rakshakChartInstances.systemSummary = new Chart(canvas.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{
                data: chartValues,
                backgroundColor: colors,
                borderColor: 'rgba(10,8,14,0.82)',
                borderWidth: 3,
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '66%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(20, 19, 16, 0.96)',
                    titleColor: '#f5f3f7',
                    bodyColor: '#a89db0',
                    borderColor: 'rgba(201,162,74,0.22)',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 10,
                },
            },
        },
    });

    const totalEl = document.getElementById('system-summary-total');
    if (totalEl) totalEl.textContent = total.toLocaleString('en-IN');

    const legendEl = document.getElementById('system-summary-legend');
    if (!legendEl) return;
    legendEl.innerHTML = '';

    chartLabels.forEach((label, index) => {
        const row = document.createElement('div');
        row.className = 'summary-legend-row';

        const dot = document.createElement('span');
        dot.className = 'summary-dot';
        dot.style.background = colors[index % colors.length];

        const labelEl = document.createElement('span');
        labelEl.textContent = label;

        const valueEl = document.createElement('b');
        valueEl.className = 'mono';
        valueEl.textContent = legendValues[index].toLocaleString('en-IN');

        row.append(dot, labelEl, valueEl);
        legendEl.appendChild(row);
    });
}

// ====================================================================
// THEME-AWARE HELPERS
// ====================================================================
function isDarkMode() {
    const theme = document.documentElement.getAttribute('data-theme');
    return theme !== 'light';
}

window.addEventListener('themeChanged', function(e) {
    const isDark = e.detail.theme === 'dark';
    
    // Update Chart.js instances
    var trendsEl = document.getElementById('sensor-trends-data');
    if (trendsEl && window.rakshakChartInstances) {
        Object.values(window.rakshakChartInstances).forEach(chart => chart.destroy());
        window.rakshakChartInstances = {};
        initDashboardCharts(JSON.parse(trendsEl.textContent));
        var summaryEl = document.getElementById('system-summary-data');
        if (summaryEl) {
            initSystemSummaryChart(JSON.parse(summaryEl.textContent));
        }
    }
});

// ====================================================================
// APP SIDEBAR TOGGLE
// ====================================================================
function initSidebar() {
    const sidebar = document.getElementById('app-sidebar');
    if (!sidebar) return;
    
    // Load state from local storage
    if (localStorage.getItem('rakshak_sidebar_collapsed') === 'true') {
        sidebar.classList.add('collapsed');
    }

    // Use event delegation for the toggle button
    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('#sidebar-toggle');
        if (!toggleBtn) return;
        
        e.preventDefault();
        const appSidebar = document.getElementById('app-sidebar');
        if (!appSidebar) return;
        
        appSidebar.classList.toggle('collapsed');
        const isCollapsed = appSidebar.classList.contains('collapsed');
        localStorage.setItem('rakshak_sidebar_collapsed', isCollapsed);
        
        // Explicitly resize charts after CSS transition (which is ~250ms)
        setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
            
            // Explicit Chart.js resize
            if (window.rakshakChartInstances) {
                Object.values(window.rakshakChartInstances).forEach(chart => {
                    if(chart && typeof chart.resize === 'function') chart.resize();
                });
            }
        }, 260); 
    });
}

// ====================================================================
// INITIALIZE ON DOM READY
// ====================================================================
document.addEventListener('DOMContentLoaded', function () {
    initLiveClock();
    animateCounters();
    initSidebar();
    
    // Dashboard charts
    var trendsEl = document.getElementById('sensor-trends-data');
    if (trendsEl) {
        var trendData = JSON.parse(trendsEl.textContent);
        initDashboardCharts(trendData);
    }

    var summaryEl = document.getElementById('system-summary-data');
    if (summaryEl) {
        var summaryData = JSON.parse(summaryEl.textContent);
        initSystemSummaryChart(summaryData);
    }
});

// ====================================================================
// SPARKLINE RENDERER — SVG sparklines for data-spark divs
// (Appended from handoff/static/js/dashboard.js)
// ====================================================================
(function () {
  function renderSpark(el) {
    const values = (el.dataset.values || '').split(',').map(Number).filter(v => !isNaN(v));
    if (!values.length) return;
    const stroke = el.dataset.color || '#c9a24a';
    const w = 200, h = 44, pad = 4;
    const min = Math.min(...values), max = Math.max(...values);
    const stepX = (w - pad * 2) / (values.length - 1);
    const scaleY = v => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2);
    const pts = values.map((v, i) => [pad + i * stepX, scaleY(v)]);
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      const cx = (x0 + x1) / 2;
      d += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
    }
    const area = `${d} L ${pts[pts.length - 1][0]} ${h} L ${pts[0][0]} ${h} Z`;
    const gid = 'g' + Math.random().toString(36).slice(2, 8);
    el.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${stroke}" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${area}" fill="url(#${gid})"/>
        <path d="${d}" stroke="${stroke}" stroke-width="2" fill="none" stroke-linecap="round"/>
      </svg>`;
  }
  document.querySelectorAll('[data-spark]').forEach(renderSpark);

})();
