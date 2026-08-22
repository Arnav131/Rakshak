// frontend/static/js/simulation.js
//
// Rakshak — Live Simulation
// Drives the terminal/pixel-art train animation, calls the backend to
// generate + predict on a fresh synthetic journey, and renders the result.

'use strict';

(function () {
    var setupEl = document.getElementById('sim-setup');
    var terminalEl = document.getElementById('sim-terminal');
    var resultsEl = document.getElementById('sim-results');
    var startBtn = document.getElementById('sim-start-btn');
    var resetBtn = document.getElementById('sim-reset-btn');
    var errorEl = document.getElementById('sim-error');
    var logEl = document.getElementById('sim-log');
    var trainEl = document.getElementById('sim-train');
    var trackWrapEl = document.querySelector('.sim-track');
    var stationSourceEl = document.getElementById('sim-station-source');
    var stationDestEl = document.getElementById('sim-station-dest');

    var chartInstance = null;
    var animationTimer = null;
    var MIN_ANIMATION_MS = 5000;   // journey animation always takes at least this long,
                                    // even if the backend responds faster — keeps the
                                    // demo feeling like a real journey, not an instant API call

    // --- Real stations + route preview -----------------------------------
    var stationsByName = {};       // "New Delhi (NDLS)" -> {code,name,lat,lng}
    var routeMap = null;           // Leaflet map (created lazily)
    var routeLine = null;
    var stopMarkers = [];

    loadStations();

    function loadStations() {
        fetch('/api/simulation/stations/')
            .then(function (res) {
                var ct = res.headers.get('content-type') || '';
                if (ct.indexOf('application/json') !== -1) return res.json();
                return null;
            })
            .then(function (data) {
                if (!data || !data.success) return;
                var datalist = document.getElementById('sim-station-list');
                if (!datalist) return;
                data.stations.forEach(function (s) {
                    var label = s.name + ' (' + s.code + ')';
                    stationsByName[label] = s;
                    stationsByName[s.name] = s;
                    stationsByName[s.code] = s;
                    var opt = document.createElement('option');
                    opt.value = label;
                    datalist.appendChild(opt);
                });
                document.getElementById('sim-source').placeholder = 'e.g. ' + data.stations[0].name;
                document.getElementById('sim-destination').addEventListener('input', maybeDrawRoute);
                document.getElementById('sim-source').addEventListener('input', maybeDrawRoute);
            })
            .catch(function () { /* datalist stays empty; free-text still works */ });
    }

    function resolveStation(inputId) {
        var raw = document.getElementById(inputId).value.trim();
        if (!raw) return null;
        if (stationsByName[raw]) return stationsByName[raw];
        var match = raw.match(/\(([A-Za-z0-9]+)\)$/);
        if (match && stationsByName[match[1]]) {
            return stationsByName[match[1]];
        }
        for (var k in stationsByName) {
            if (k.toLowerCase() === raw.toLowerCase()) {
                return stationsByName[k];
            }
        }
        return null;
    }

    function maybeDrawRoute() {
        var src = resolveStation('sim-source');
        var dst = resolveStation('sim-destination');
        if (!src || !dst || src.code === dst.code) {
            setRouteMeta('');
            return;
        }
        fetch('/api/simulation/route/?from=' + encodeURIComponent(src.code) +
              '&to=' + encodeURIComponent(dst.code))
            .then(function (res) {
                var ct = res.headers.get('content-type') || '';
                if (ct.indexOf('application/json') !== -1) return res.json();
                return { success: false, error: 'Route lookup unavailable' };
            })
            .then(function (data) {
                if (!data || !data.success) {
                    setRouteMeta((data && data.error) || 'No route found');
                    clearRouteLayers();
                    return;
                }
                drawRoute(data);
            })
            .catch(function () { setRouteMeta('Route lookup failed'); });
    }

    function ensureMap() {
        var container = document.getElementById('sim-route-map');
        if (routeMap) return routeMap;

        routeMap = L.map(container, { scrollWheelZoom: false }).setView([22.5, 79], 5);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19,
        }).addTo(routeMap);
        return routeMap;
    }

    function clearRouteLayers() {
        if (!routeMap) return;
        if (routeLine) { routeMap.removeLayer(routeLine); routeLine = null; }
        stopMarkers.forEach(function (m) { routeMap.removeLayer(m); });
        stopMarkers = [];
    }

    function drawRoute(data) {
        var map = ensureMap();
        clearRouteLayers();

        routeLine = L.polyline(data.waypoints, {
            color: '#38bdf8',
            weight: 4,
            opacity: 0.9,
        }).addTo(map);

        data.stations.forEach(function (s, i) {
            var isEnd = i === 0 || i === data.stations.length - 1;
            var marker = L.circleMarker([s.lat, s.lng], {
                radius: isEnd ? 7 : 3,
                color: isEnd ? '#f59e0b' : '#38bdf8',
                fillColor: isEnd ? '#f59e0b' : '#38bdf8',
                fillOpacity: 0.9,
            }).addTo(map);
            marker.bindTooltip(s.name + ' (' + s.code + ')');
            stopMarkers.push(marker);
        });

        map.fitBounds(routeLine.getBounds(), { padding: [30, 30] });
        setRouteMeta(
            data.from + ' → ' + data.to + ' · ' + data.total_distance_km + ' km · ' +
            data.stops_count + ' stations'
        );
    }

    function setRouteMeta(text) {
        var el = document.getElementById('sim-route-meta');
        if (el) el.textContent = text;
    }

    var LOG_LINES = [
        { text: '> Initializing onboard sensor array...', cls: 'sim-log-line--dim' },
        { text: '> Establishing telemetry link...', cls: '' },
        { text: '> Sampling ambient_temp, humidity, vibration_rms, gauge_width...', cls: '' },
        { text: '> Streaming readings from track section...', cls: '' },
        { text: '> Awaiting full 16-reading window...', cls: 'sim-log-line--dim' },
    ];

    if (!startBtn) return;  // page not loaded (defensive)

    startBtn.addEventListener('click', startSimulation);
    if (resetBtn) resetBtn.addEventListener('click', resetSimulation);

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            document.cookie.split(';').forEach(function (cookie) {
                var trimmed = cookie.trim();
                if (trimmed.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(trimmed.substring(name.length + 1));
                }
            });
        }
        return cookieValue;
    }

    function startSimulation() {
        var srcStation = resolveStation('sim-source');
        var dstStation = resolveStation('sim-destination');
        var source = srcStation ? srcStation.name : document.getElementById('sim-source').value.trim();
        var destination = dstStation ? dstStation.name : document.getElementById('sim-destination').value.trim();
        errorEl.textContent = '';

        if (!source || !destination) {
            errorEl.textContent = 'Please enter both a source and destination station.';
            return;
        }
        if (source.toLowerCase() === destination.toLowerCase()) {
            errorEl.textContent = 'Source and destination must be different.';
            return;
        }

        startBtn.disabled = true;
        setupEl.style.display = 'none';
        resultsEl.style.display = 'none';
        terminalEl.style.display = 'block';

        stationSourceEl.textContent = truncateLabel(source);
        stationDestEl.textContent = truncateLabel(destination);
        logEl.innerHTML = '';
        trainEl.style.left = '0px';

        var startTime = Date.now();

        // Kick off the train animation (purely visual, CSS-driven position updates)
        animateTrain();
        typeLogLines();

        var conditionEl = document.getElementById('sim-condition');
        var condition = conditionEl ? conditionEl.value : 'auto';

        // Call the backend — this does the REAL LLM generation + REAL
        // prediction pipeline call, not preloaded/hardcoded data.
        var csrfToken = getCookie('csrftoken') || (document.querySelector('[name=csrfmiddlewaretoken]') ? document.querySelector('[name=csrfmiddlewaretoken]').value : '');
        fetch('/api/simulation/run/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ source: source, destination: destination, condition: condition }),
        })
            .then(function (res) {
                var ct = res.headers.get('content-type') || '';
                if (ct.indexOf('application/json') !== -1) {
                    return res.json().then(function (data) {
                        return { ok: res.ok, status: res.status, data: data };
                    });
                } else {
                    return res.text().then(function () {
                        var errMsg = 'Server returned HTTP ' + res.status + '.';
                        if (res.status === 401 || res.status === 403) {
                            errMsg = 'Administrator session required to run live simulation.';
                        }
                        return {
                            ok: false,
                            status: res.status,
                            data: { success: false, error: errMsg }
                        };
                    });
                }
            })
            .then(function (result) {
                var data = result.data;
                var elapsed = Date.now() - startTime;
                var remaining = Math.max(0, MIN_ANIMATION_MS - elapsed);
                animationTimer = setTimeout(function () {
                    finishJourney(data, source, destination);
                }, remaining);
            })
            .catch(function (err) {
                var elapsed = Date.now() - startTime;
                var remaining = Math.max(0, MIN_ANIMATION_MS - elapsed);
                setTimeout(function () {
                    showError('Simulation request failed: ' + err.message);
                }, remaining);
            });
    }

    function truncateLabel(s) {
        return s.length > 14 ? s.slice(0, 13) + '…' : s;
    }

    function animateTrain() {
        var start = performance.now();
        var trackWidth = trackWrapEl.getBoundingClientRect().width - 60;

        function step(now) {
            var elapsed = now - start;
            var progress = Math.min(elapsed / MIN_ANIMATION_MS, 1.0);
            trainEl.style.left = (progress * trackWidth) + 'px';
            if (progress < 1.0) {
                requestAnimationFrame(step);
            }
        }
        requestAnimationFrame(step);
    }

    function typeLogLines() {
        LOG_LINES.forEach(function (line, i) {
            setTimeout(function () {
                var div = document.createElement('div');
                div.className = 'sim-log-line ' + (line.cls || '');
                div.textContent = line.text;
                logEl.appendChild(div);
                logEl.scrollTop = logEl.scrollHeight;
            }, i * (MIN_ANIMATION_MS / (LOG_LINES.length + 1)));
        });
    }

    function finishJourney(data, source, destination) {
        if (!data || !data.success) {
            showError((data && data.error) || 'Simulation failed for an unknown reason.');
            return;
        }

        var arrivalLine = document.createElement('div');
        arrivalLine.className = 'sim-log-line';
        arrivalLine.textContent = '> 🚉 Train reached "' + destination + '" station — 16-reading window complete.';
        logEl.appendChild(arrivalLine);
        logEl.scrollTop = logEl.scrollHeight;

        setTimeout(function () {
            terminalEl.style.display = 'none';
            renderResults(data, source, destination);
            resultsEl.style.display = 'block';
        }, 900);
    }

    function showError(msg) {
        terminalEl.style.display = 'none';
        setupEl.style.display = 'flex';
        startBtn.disabled = false;
        errorEl.textContent = msg;
    }

    function renderResults(data, source, destination) {
        var prediction = data.prediction || {};
        var alertLevel = prediction.alert_level || 'none';
        var score = typeof prediction.anomaly_score === 'number' ? prediction.anomaly_score : 0;
        var faultType = prediction.fault_type || 'unknown';
        var faultConf = typeof prediction.fault_confidence === 'number' ? prediction.fault_confidence : 0;
        var explanation = prediction.explanation || prediction.metadata && prediction.metadata.explanation || '';

        document.getElementById('sim-arrival-banner').textContent =
            '🚉 Journey complete: ' + source + ' → ' + destination +
            '  |  sensor_id: ' + data.sensor_id;

        var isHealthy = score < 0.20 || alertLevel === 'none' || faultType === 'unknown' || faultType === 'normal';

        var alertCard = document.getElementById('sim-alert-card');
        alertCard.className = 'sim-card sim-card--alert level-' + alertLevel;
        document.getElementById('sim-alert-level').textContent = alertLevel === 'none' ? 'NORMAL / SAFE' : alertLevel.toUpperCase();
        document.getElementById('sim-alert-score').textContent = 'score: ' + score.toFixed(3);

        if (isHealthy) {
            document.getElementById('sim-fault-type').textContent = 'None (Healthy)';
            document.getElementById('sim-fault-conf').textContent = 'Safe parameters';
        } else {
            document.getElementById('sim-fault-type').textContent = faultType.replace(/_/g, ' ');
            document.getElementById('sim-fault-conf').textContent = 'confidence: ' + (faultConf > 0 ? (faultConf * 100).toFixed(1) + '%' : 'Elevated');
        }

        document.getElementById('sim-flavour').textContent = (data.scenario_flavour || 'unknown').replace(/_/g, ' ');
        document.getElementById('sim-backend-used').textContent = 'generator: ' + (data.generator_backend || 'unknown');

        document.getElementById('sim-score-bar-fill').style.width = Math.min(100, score * 100) + '%';

        var suggestionsEl = document.getElementById('sim-suggestions');
        suggestionsEl.innerHTML = '';
        (data.suggestions || []).forEach(function (s) {
            var div = document.createElement('div');
            div.className = 'sim-suggestion-line';
            div.textContent = s;
            suggestionsEl.appendChild(div);
        });

        var readinessBtn = document.getElementById('sim-readiness-btn');
        if (readinessBtn && data.readiness_url) {
            readinessBtn.href = data.readiness_url;
        }

        renderChart(data.readings || []);
    }

    function renderChart(readings) {
        var canvas = document.getElementById('sim-chart');
        if (!canvas || typeof Chart === 'undefined') return;

        if (chartInstance) {
            chartInstance.destroy();
        }

        var labels = readings.map(function (_, i) { return 't-' + (readings.length - i); });
        var gauge = readings.map(function (r) { return r.gauge_width; });
        var vibration = readings.map(function (r) { return r.vibration_rms; });

        chartInstance = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Gauge Width (mm)',
                        data: gauge,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56,189,248,0.08)',
                        yAxisID: 'y',
                        tension: 0.3,
                    },
                    {
                        label: 'Vibration RMS',
                        data: vibration,
                        borderColor: '#f87171',
                        backgroundColor: 'rgba(248,113,113,0.08)',
                        yAxisID: 'y1',
                        tension: 0.3,
                    },
                ],
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: { type: 'linear', position: 'left', title: { display: true, text: 'mm' } },
                    y1: { type: 'linear', position: 'right', title: { display: true, text: 'RMS' }, grid: { drawOnChartArea: false } },
                },
                plugins: { legend: { labels: { color: '#94a3b8' } } },
            },
        });
    }

    function resetSimulation() {
        resultsEl.style.display = 'none';
        setupEl.style.display = 'flex';
        startBtn.disabled = false;
        document.getElementById('sim-source').value = '';
        document.getElementById('sim-destination').value = '';
        errorEl.textContent = '';
        setRouteMeta('');
        if (animationTimer) clearTimeout(animationTimer);
    }
})();
