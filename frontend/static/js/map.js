// frontend/static/js/map.js
//
// Rakshak railway map.
// Restores the old working API-driven Leaflet behavior and wraps it in the
// current emerald/gold control-center theme.

"use strict";

var RAKSHAK_MAP_COLORS = {
    healthy: "#4fbf7a",
    warning: "#e0c07a",
    critical: "#f28b8b",
    ticket: "#7fb0ff",
    train: "#c9a24a",
    routeDefault: "#9aa4b2",
};

var RAKSHAK_MAP_GLOWS = {
    healthy: "rgba(79,191,122,0.28)",
    warning: "rgba(224,192,122,0.30)",
    critical: "rgba(242,139,139,0.32)",
    ticket: "rgba(127,176,255,0.28)",
    train: "rgba(201,162,74,0.30)",
};

var RAKSHAK_TICKET_COLORS = {
    critical: RAKSHAK_MAP_COLORS.critical,
    high: RAKSHAK_MAP_COLORS.warning,
    medium: RAKSHAK_MAP_COLORS.ticket,
    low: RAKSHAK_MAP_COLORS.healthy,
};

var rakshakMapState = null;

function initRakshakControlMap() {
    var mapEl = document.getElementById("railway-map");
    if (!mapEl || typeof L === "undefined") return;

    injectRakshakMapStyles();

    var page = document.getElementById("map-page");
    var preferredTheme = localStorage.getItem("rakshak-map-theme") || "dark";
    if (page) page.setAttribute("data-map-theme", preferredTheme);
    syncThemeButtons(preferredTheme);

    var map = L.map("railway-map", {
        center: [22.5, 79.0],
        zoom: 5,
        minZoom: 4,
        maxZoom: 14,
        zoomControl: false,
        attributionControl: false,
        preferCanvas: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
        subdomains: "abcd",
        maxZoom: 20,
    }).addTo(map);

    var layers = {
        routes: L.layerGroup().addTo(map),
        stations: L.layerGroup().addTo(map),
        tickets: L.layerGroup().addTo(map),
        alerts: L.layerGroup().addTo(map),
        trains: L.layerGroup().addTo(map),
    };

    rakshakMapState = {
        map: map,
        layers: layers,
        data: {
            stations: [],
            routes: [],
            tickets: [],
            alerts: [],
            trains: [],
            summary: {},
        },
        visible: {
            routes: true,
            stations: true,
            tickets: true,
            alerts: true,
            trains: true,
        },
        condition: "all",
        alertMarkers: {},
        trainMarkers: {},
        selectedRoute: null,
    };

    bindMapControls(rakshakMapState);
    bindLayerControls(rakshakMapState);
    bindThemeControls(rakshakMapState);

    Promise.all([
        fetchJson("/api/stations/"),
        fetchJson("/api/routes/"),
        fetchJson("/api/tickets/"),
        fetchJson("/api/alerts/"),
        fetchJson("/api/summary/"),
    ]).then(function (results) {
        rakshakMapState.data.stations = results[0] || [];
        rakshakMapState.data.routes = normalizeRoutes(results[1] || []);
        rakshakMapState.data.tickets = results[2] || [];
        rakshakMapState.data.alerts = results[3] || [];
        rakshakMapState.data.summary = results[4] || {};

        renderAllMapLayers(rakshakMapState);
        renderZoneList(rakshakMapState);
        updateMapMetrics(rakshakMapState);
        updateDefaultInspector(rakshakMapState);
        fitIndia(rakshakMapState);
        focusRequestedAlert(rakshakMapState);
        refreshTrains(rakshakMapState);

        window.setTimeout(function () {
            map.invalidateSize();
        }, 100);
    }).catch(function (error) {
        updateInspector({
            type: "Error",
            title: "Map data could not load",
            rows: [
                ["Message", error.message || "Unknown error"],
                ["Action", "Check API/session"],
            ],
        });
    });
}

// Backwards-compatible alias for older templates.
function initRailwayMapFromAPI() {
    initRakshakControlMap();
}

function fetchJson(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (response) {
        if (!response.ok) throw new Error(url + " returned HTTP " + response.status);
        return response.json();
    });
}

function normalizeRoutes(routes) {
    return routes.filter(function (route) {
        return Array.isArray(route.coordinates) && route.coordinates.length >= 2;
    }).map(function (route) {
        route.status = route.status || "healthy";
        return route;
    });
}

function bindMapControls(state) {
    var zoomIn = document.getElementById("btn-zoom-in");
    var zoomOut = document.getElementById("btn-zoom-out");
    var fitBtn = document.getElementById("btn-reset-india");
    var condition = document.getElementById("condition-filter");

    if (zoomIn) zoomIn.addEventListener("click", function () { state.map.zoomIn(); });
    if (zoomOut) zoomOut.addEventListener("click", function () { state.map.zoomOut(); });
    if (fitBtn) fitBtn.addEventListener("click", function () { fitIndia(state); });
    if (condition) {
        condition.addEventListener("change", function () {
            state.condition = condition.value || "all";
            renderAllMapLayers(state);
            updateMapMetrics(state);
        });
    }
}

function bindLayerControls(state) {
    document.querySelectorAll("[data-layer-toggle]").forEach(function (input) {
        input.addEventListener("change", function () {
            var key = input.getAttribute("data-layer-toggle");
            state.visible[key] = input.checked;
            if (input.checked) {
                state.layers[key].addTo(state.map);
            } else {
                state.map.removeLayer(state.layers[key]);
            }
        });
    });
}

function bindThemeControls(state) {
    document.querySelectorAll("[data-map-theme-choice]").forEach(function (button) {
        button.addEventListener("click", function () {
            var theme = button.getAttribute("data-map-theme-choice") || "dark";
            var page = document.getElementById("map-page");
            if (page) page.setAttribute("data-map-theme", theme);
            localStorage.setItem("rakshak-map-theme", theme);
            syncThemeButtons(theme);
            window.setTimeout(function () {
                state.map.invalidateSize();
            }, 60);
        });
    });
}

function syncThemeButtons(theme) {
    document.querySelectorAll("[data-map-theme-choice]").forEach(function (button) {
        button.classList.toggle("active", button.getAttribute("data-map-theme-choice") === theme);
    });
}

function renderAllMapLayers(state) {
    state.alertMarkers = {};
    state.selectedRoute = null;
    Object.keys(state.layers).forEach(function (key) {
        if (key !== "trains") state.layers[key].clearLayers();
    });

    renderRoutes(state);
    renderStations(state);
    renderTickets(state);
    renderAlerts(state);
}

function passesCondition(status, condition) {
    return condition === "all" || status === condition;
}

function renderRoutes(state) {
    state.data.routes.forEach(function (route) {
        if (!passesCondition(route.status, state.condition)) return;

        var color = RAKSHAK_MAP_COLORS[route.status] || RAKSHAK_MAP_COLORS.routeDefault;
        var line = L.polyline(route.coordinates, {
            color: color,
            weight: route.status === "critical" ? 4.4 : 3.1,
            opacity: route.status === "healthy" ? 0.62 : 0.84,
            dashArray: route.status === "healthy" ? null : "8, 7",
            lineCap: "round",
            lineJoin: "round",
        });

        line.bindTooltip(routeTooltip(route), {
            sticky: true,
            className: "rakshak-map-tooltip",
        });

        line.bindPopup(routePopup(route), {
            maxWidth: 320,
            className: "rakshak-map-popup",
        });

        line.on("mouseover", function () {
            line.setStyle({ weight: 5.5, opacity: 0.96 });
        });
        line.on("mouseout", function () {
            if (state.selectedRoute !== line) {
                line.setStyle({
                    weight: route.status === "critical" ? 4.4 : 3.1,
                    opacity: route.status === "healthy" ? 0.62 : 0.84,
                });
            }
        });
        line.on("click", function () {
            if (state.selectedRoute && state.selectedRoute !== line) {
                var previousRoute = state.selectedRoute.options._routeData;
                state.selectedRoute.setStyle({
                    weight: previousRoute.status === "critical" ? 4.4 : 3.1,
                    opacity: previousRoute.status === "healthy" ? 0.62 : 0.84,
                });
            }
            line.options._routeData = route;
            state.selectedRoute = line;
            line.setStyle({ weight: 6, opacity: 1 });
            line.bringToFront();
            updateInspector(routeInspector(route));
        });

        line.options._routeData = route;
        state.layers.routes.addLayer(line);
    });
}

function renderStations(state) {
    state.data.stations.forEach(function (station) {
        if (!passesCondition(station.status, state.condition)) return;
        if (!isFiniteNumber(station.lat) || !isFiniteNumber(station.lng)) return;

        var color = RAKSHAK_MAP_COLORS[station.status] || RAKSHAK_MAP_COLORS.healthy;
        var glow = RAKSHAK_MAP_GLOWS[station.status] || RAKSHAK_MAP_GLOWS.healthy;

        state.layers.stations.addLayer(L.circleMarker([station.lat, station.lng], {
            radius: 16,
            color: "transparent",
            fillColor: glow,
            fillOpacity: 0.55,
            interactive: false,
        }));

        var marker = L.circleMarker([station.lat, station.lng], {
            radius: station.is_junction ? 8.5 : 6.8,
            color: "#f5f3f7",
            weight: 1.5,
            fillColor: color,
            fillOpacity: 0.92,
        });

        marker.bindTooltip(escapeHtml(station.code || ""), {
            permanent: true,
            direction: "top",
            offset: [0, -12],
            className: "station-label",
        });

        marker.bindPopup(stationPopup(station), {
            maxWidth: 300,
            className: "rakshak-map-popup",
        });

        marker.on("click", function () {
            updateInspector(stationInspector(station));
        });

        state.layers.stations.addLayer(marker);
    });
}

function renderTickets(state) {
    state.data.tickets.forEach(function (ticket) {
        if (!isFiniteNumber(ticket.lat) || !isFiniteNumber(ticket.lng)) return;

        var color = RAKSHAK_TICKET_COLORS[ticket.priority] || RAKSHAK_MAP_COLORS.ticket;
        var marker = L.circleMarker([ticket.lat, ticket.lng], {
            radius: 6,
            color: "#f5f3f7",
            fillColor: color,
            fillOpacity: 0.88,
            weight: 1.2,
        });

        marker.bindPopup(ticketPopup(ticket), {
            maxWidth: 320,
            className: "rakshak-map-popup",
        });

        marker.on("click", function () {
            updateInspector(ticketInspector(ticket));
        });

        state.layers.tickets.addLayer(marker);
    });
}

function renderAlerts(state) {
    state.data.alerts.forEach(function (alert) {
        if (!isFiniteNumber(alert.lat) || !isFiniteNumber(alert.lng)) return;

        var color = RAKSHAK_MAP_COLORS[alert.severity] || RAKSHAK_MAP_COLORS.warning;

        state.layers.alerts.addLayer(L.circleMarker([alert.lat, alert.lng], {
            radius: 19,
            color: "transparent",
            fillColor: color,
            fillOpacity: alert.severity === "critical" ? 0.24 : 0.16,
            interactive: false,
        }));

        var marker = L.circleMarker([alert.lat, alert.lng], {
            radius: alert.severity === "critical" ? 7.4 : 6.2,
            color: "#f5f3f7",
            fillColor: color,
            fillOpacity: 1,
            weight: 1.6,
        });

        marker.bindPopup(alertPopup(alert), {
            maxWidth: 330,
            className: "rakshak-map-popup",
        });

        marker.on("click", function () {
            updateInspector(alertInspector(alert));
        });

        state.alertMarkers[alert.id] = marker;
        state.layers.alerts.addLayer(marker);
    });
}

function refreshTrains(state) {
    fetchJson("/api/trains/").then(function (trains) {
        state.data.trains = trains || [];
        renderTrains(state);
        updateMapMetrics(state);
        updateStatusTime();
    }).catch(function () {
        state.data.trains = state.data.trains || [];
        updateMapMetrics(state);
    });
}

function renderTrains(state) {
    var active = {};
    state.data.trains.forEach(function (train) {
        if (!isFiniteNumber(train.lat) || !isFiniteNumber(train.lng)) return;
        active[train.id] = true;

        if (state.trainMarkers[train.id]) {
            state.trainMarkers[train.id].setLatLng([train.lat, train.lng]);
            state.trainMarkers[train.id].setPopupContent(trainPopup(train));
            return;
        }

        var marker = L.marker([train.lat, train.lng], {
            icon: L.divIcon({
                className: "train-marker-icon",
                html: "<span>🚆</span>",
                iconSize: [34, 34],
                iconAnchor: [17, 17],
            }),
            zIndexOffset: 1000,
        });

        marker.bindTooltip(escapeHtml(train.id || "TRAIN"), {
            direction: "top",
            offset: [0, -12],
            className: "station-label",
        });

        marker.bindPopup(trainPopup(train), {
            maxWidth: 260,
            className: "rakshak-map-popup",
        });

        marker.on("click", function () {
            updateInspector(trainInspector(train));
        });

        state.trainMarkers[train.id] = marker;
        state.layers.trains.addLayer(marker);
    });

    Object.keys(state.trainMarkers).forEach(function (id) {
        if (!active[id]) {
            state.layers.trains.removeLayer(state.trainMarkers[id]);
            delete state.trainMarkers[id];
        }
    });
}

function renderZoneList(state) {
    var zoneList = document.getElementById("zone-list");
    if (!zoneList) return;

    var zones = {};
    state.data.stations.forEach(function (station) {
        var zone = station.zone || "Unknown Zone";
        zones[zone] = (zones[zone] || 0) + 1;
    });

    var html = '<div class="zone-item active" data-zone="all"><span>All Zones</span><span class="zone-count">' +
        state.data.stations.length + "</span></div>";

    Object.keys(zones).sort().forEach(function (zone) {
        html += '<div class="zone-item" data-zone="' + escapeHtml(zone) + '"><span>' +
            escapeHtml(zone) + '</span><span class="zone-count">' + zones[zone] + "</span></div>";
    });

    zoneList.innerHTML = html;

    zoneList.querySelectorAll(".zone-item").forEach(function (item) {
        item.addEventListener("click", function () {
            zoneList.querySelectorAll(".zone-item").forEach(function (el) {
                el.classList.remove("active");
            });
            item.classList.add("active");
            focusZone(state, item.getAttribute("data-zone"));
        });
    });
}

function focusZone(state, zoneName) {
    if (!zoneName || zoneName === "all") {
        fitIndia(state);
        return;
    }

    var points = state.data.stations.filter(function (station) {
        return station.zone === zoneName && isFiniteNumber(station.lat) && isFiniteNumber(station.lng);
    }).map(function (station) {
        return [station.lat, station.lng];
    });

    if (!points.length) return;
    state.map.fitBounds(L.latLngBounds(points), { padding: [36, 36], maxZoom: 8 });
}

function focusRequestedAlert(state) {
    var params = new URLSearchParams(window.location.search);
    var focusAlert = params.get("focus_alert");
    if (!focusAlert || !state.alertMarkers[focusAlert]) return;

    var marker = state.alertMarkers[focusAlert];
    state.map.setView(marker.getLatLng(), 12);
    marker.openPopup();
}

function fitIndia(state) {
    var indiaBounds = L.latLngBounds([6.5, 68.0], [35.5, 97.5]);
    state.map.fitBounds(indiaBounds, { padding: [22, 22] });
}

function updateMapMetrics(state) {
    var routeCounts = countByStatus(state.data.routes);
    setText("kpi-live-trains", state.data.trains.length);
    setText("kpi-critical-tracks", routeCounts.critical || 0);
    setText("kpi-warning-tracks", routeCounts.warning || 0);
    setText("kpi-healthy-tracks", routeCounts.healthy || 0);
    setText("stat-route-count", visibleRouteCount(state));
    setText("stat-station-count", state.data.stations.length);
    setText("inspect-route-count", state.data.routes.length);
    setText("inspect-station-count", state.data.stations.length);
    setText("inspect-train-count", state.data.trains.length);
}

function visibleRouteCount(state) {
    return state.data.routes.filter(function (route) {
        return passesCondition(route.status, state.condition);
    }).length;
}

function countByStatus(items) {
    return items.reduce(function (acc, item) {
        var status = item.status || "healthy";
        acc[status] = (acc[status] || 0) + 1;
        return acc;
    }, {});
}

function updateStatusTime() {
    var now = new Date();
    setText("stat-updated-at", now.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    }));
}

function updateDefaultInspector(state) {
    updateInspector({
        type: "Network",
        title: "India Railway Network",
        rows: [
            ["Stations", state.data.stations.length],
            ["Track Sections", state.data.routes.length],
            ["Tickets Layer", state.data.tickets.length],
            ["Alerts Layer", state.data.alerts.length],
        ],
    });
}

function updateInspector(model) {
    var content = document.getElementById("inspector-content");
    var status = document.getElementById("inspector-status");
    if (!content) return;

    if (status) status.textContent = model.type || "LIVE";

    var rows = (model.rows || []).map(function (row) {
        return '<div class="prop-row"><span>' + escapeHtml(row[0]) +
            '</span><span class="prop-val">' + escapeHtml(row[1]) + "</span></div>";
    }).join("");

    content.innerHTML =
        '<div class="inspector-card">' +
        '<div class="inspector-title"><span>' + escapeHtml(model.title || "Map Element") +
        '</span><span class="inspector-type">' + escapeHtml(model.type || "Live") + "</span></div>" +
        rows +
        "</div>";
}

function routeTooltip(route) {
    return "<strong>" + escapeHtml(route.id || route.name || "Track") + "</strong><br>" +
        '<span class="tooltip-muted">' + escapeHtml(formatStatus(route.status)) + " condition</span>";
}

function routePopup(route) {
    return popupShell("Track Section", route.name || route.id, [
        ["Section", route.id || "N/A"],
        ["Condition", formatStatus(route.status)],
        ["From", route.source || "N/A"],
        ["To", route.destination || "N/A"],
        ["Distance", route.distance_km ? route.distance_km + " km" : "N/A"],
    ]);
}

function stationPopup(station) {
    return popupShell("Station", station.name, [
        ["Code", station.code],
        ["Zone", station.zone],
        ["Division", station.division],
        ["Condition", formatStatus(station.status)],
        ["Tracks", station.tracks_monitored],
        ["Daily Trains", station.daily_trains],
    ]);
}

function ticketPopup(ticket) {
    return popupShell("Ticket", ticket.id, [
        ["Issue", ticket.title],
        ["Priority", formatStatus(ticket.priority)],
        ["Status", formatStatus(ticket.status)],
        ["Station", ticket.station],
        ["Team", ticket.team],
        ["Section", ticket.section],
    ]);
}

function alertPopup(alert) {
    return popupShell("Alert", alert.title, [
        ["Code", alert.id],
        ["Severity", formatStatus(alert.severity)],
        ["Status", formatStatus(alert.status)],
        ["Zone", alert.zone],
        ["Station", alert.station],
        ["Details", alert.description],
    ]);
}

function trainPopup(train) {
    return popupShell("Live Train", "🚆 " + train.id, [
        ["Route", train.route_id],
        ["Speed", train.speed_kmph + " km/h"],
        ["Progress", Math.round((train.progress || 0) * 100) + "%"],
    ]);
}

function popupShell(type, title, rows) {
    var body = rows.map(function (row) {
        return '<div class="popup-row"><span class="popup-label">' + escapeHtml(row[0]) +
            '</span><span class="popup-value">' + escapeHtml(row[1] == null ? "N/A" : row[1]) +
            "</span></div>";
    }).join("");

    return '<div class="map-popup-card">' +
        '<div class="popup-kind">' + escapeHtml(type) + "</div>" +
        "<h3>" + escapeHtml(title || type) + "</h3>" +
        body +
        "</div>";
}

function routeInspector(route) {
    return {
        type: "Track",
        title: route.name || route.id,
        rows: [
            ["Section", route.id || "N/A"],
            ["Condition", formatStatus(route.status)],
            ["Source", route.source || "N/A"],
            ["Destination", route.destination || "N/A"],
            ["Distance", route.distance_km ? route.distance_km + " km" : "N/A"],
        ],
    };
}

function stationInspector(station) {
    return {
        type: "Station",
        title: station.name,
        rows: [
            ["Code", station.code],
            ["Zone", station.zone],
            ["Division", station.division],
            ["Condition", formatStatus(station.status)],
            ["Tracks", station.tracks_monitored],
            ["Daily Trains", station.daily_trains],
        ],
    };
}

function ticketInspector(ticket) {
    return {
        type: "Ticket",
        title: ticket.id,
        rows: [
            ["Issue", ticket.title],
            ["Priority", formatStatus(ticket.priority)],
            ["Status", formatStatus(ticket.status)],
            ["Team", ticket.team],
            ["Station", ticket.station],
        ],
    };
}

function alertInspector(alert) {
    return {
        type: "Alert",
        title: alert.title,
        rows: [
            ["Code", alert.id],
            ["Severity", formatStatus(alert.severity)],
            ["Status", formatStatus(alert.status)],
            ["Zone", alert.zone],
            ["Station", alert.station],
        ],
    };
}

function trainInspector(train) {
    return {
        type: "Train",
        title: train.id,
        rows: [
            ["Route", train.route_id],
            ["Speed", train.speed_kmph + " km/h"],
            ["Progress", Math.round((train.progress || 0) * 100) + "%"],
        ],
    };
}

function formatStatus(value) {
    if (!value) return "N/A";
    return String(value).replace(/_/g, " ").replace(/\b\w/g, function (char) {
        return char.toUpperCase();
    });
}

function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value == null ? "--" : value;
}

function isFiniteNumber(value) {
    return typeof value === "number" && Number.isFinite(value);
}

function escapeHtml(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function injectRakshakMapStyles() {
    if (document.getElementById("rakshak-map-runtime-styles")) return;

    var style = document.createElement("style");
    style.id = "rakshak-map-runtime-styles";
    style.textContent = [
        ".station-label {",
        "  background: rgba(18,16,14,0.76) !important;",
        "  color: #f5f3f7 !important;",
        "  border: 1px solid rgba(201,162,74,0.22) !important;",
        "  border-radius: 7px !important;",
        "  box-shadow: 0 6px 16px rgba(0,0,0,0.24) !important;",
        "  font-family: var(--font-mono) !important;",
        "  font-size: 9.5px !important;",
        "  font-weight: 800 !important;",
        "  letter-spacing: 0.08em !important;",
        "  padding: 2px 6px !important;",
        "}",
        ".station-label::before { border-top-color: rgba(18,16,14,0.76) !important; }",
        ".rakshak-map-tooltip {",
        "  background: rgba(18,16,14,0.86) !important;",
        "  color: #f5f3f7 !important;",
        "  border: 1px solid rgba(255,255,255,0.10) !important;",
        "  border-radius: 8px !important;",
        "  box-shadow: 0 8px 20px rgba(0,0,0,0.25) !important;",
        "  font-family: var(--font-body) !important;",
        "}",
        ".tooltip-muted { color: #a89db0; font-size: 11px; }",
        ".rakshak-map-popup .leaflet-popup-content-wrapper {",
        "  background: rgba(20,19,16,0.94) !important;",
        "  color: #f5f3f7 !important;",
        "  border: 1px solid rgba(255,255,255,0.12) !important;",
        "  border-radius: 16px !important;",
        "  box-shadow: 0 14px 32px rgba(0,0,0,0.38) !important;",
        "  backdrop-filter: blur(18px) saturate(135%);",
        "}",
        ".rakshak-map-popup .leaflet-popup-tip { background: rgba(20,19,16,0.94) !important; }",
        ".rakshak-map-popup .leaflet-popup-content { margin: 14px; }",
        ".map-popup-card { min-width: 230px; font-family: var(--font-body); }",
        ".map-popup-card h3 { margin: 2px 0 10px; font-size: 14px; line-height: 1.25; color: #f5f3f7; }",
        ".popup-kind { color: #e0c07a; font-family: var(--font-mono); font-size: 10px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; }",
        ".popup-row { display: flex; justify-content: space-between; gap: 14px; padding: 5px 0; border-top: 1px solid rgba(255,255,255,0.06); font-size: 12px; }",
        ".popup-label { color: #a89db0; }",
        ".popup-value { color: #f5f3f7; font-family: var(--font-mono); font-size: 11px; text-align: right; max-width: 160px; }",
        ".train-marker-icon {",
        "  display: grid !important;",
        "  place-items: center !important;",
        "  width: 34px !important;",
        "  height: 34px !important;",
        "  border: 1px solid rgba(201,162,74,0.42) !important;",
        "  border-radius: 50% !important;",
        "  background: rgba(18,16,14,0.84) !important;",
        "  color: #e0c07a !important;",
        "  box-shadow: 0 0 0 5px rgba(201,162,74,0.12), 0 8px 18px rgba(0,0,0,0.24) !important;",
        "  font-size: 18px !important;",
        "  line-height: 1 !important;",
        "}",
        ".train-marker-icon span { transform: translateY(1px); }",
    ].join("");
    document.head.appendChild(style);
}

window.initRakshakControlMap = initRakshakControlMap;
window.initRailwayMapFromAPI = initRailwayMapFromAPI;
