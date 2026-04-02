"""
Locate918 Scraper - Flask Routes & Data Pipeline
=================================================
All Flask API endpoints, event transformation, LLM normalization,
and venue manager functionality.
"""

import os
import re
import json
import asyncio
import functools
from datetime import datetime
from flask import render_template_string, render_template, request, jsonify, send_file, Response
import httpx

from scraperUtils import (
    OUTPUT_DIR,
    BACKEND_URL,
    LLM_SERVICE_URL,
    HEADERS,
    GOOGLE_PLACES_API_KEY,
    check_robots_txt,
    load_saved_urls,
    save_url,
    delete_saved_url,
    resolve_source_name,
    is_aggregator_url,
    get_source_priority,
    make_content_hash,
)

from scraperExtractors import (
    extract_eventcalendarapp,
    extract_timely,
    extract_bok_center,
    extract_circle_cinema_events,
    extract_expo_square_events,
    extract_eventbrite_api_events,
    extract_simpleview_events,
    extract_sitewrench_events,
    extract_recdesk_events,
    extract_ticketleap_events,
    extract_libnet_events,
    extract_philbrook_events,
    extract_tulsapac_events,
    extract_roosterdays_events,
    extract_tulsabrunchfest_events,
    extract_okeq_events,
    extract_flywheel_events,
    extract_arvest_events,
    extract_tulsatough_events,
    extract_gradient_events,
    extract_tulsafarmersmarket_events,
    extract_okcastle_events,
    extract_broken_arrow_events,
    extract_tulsazoo_events,
    extract_hardrock_tulsa_events,
    extract_gypsy_events,
    extract_badass_renees_events,
    extract_rocklahoma_events,
    extract_tulsa_oktoberfest_events,
    extract_events_universal,
    fetch_with_httpx,
    fetch_with_playwright,
)


# ============================================================================
# HTML TEMPLATE
# ============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Locate918 Scraper</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 30px 20px;
            color: #fff;
        }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { text-align: center; color: #D4AF37; margin-bottom: 5px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 25px; font-size: 13px; }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
        }
        .form-row { display: flex; gap: 12px; margin-bottom: 12px; }
        .form-row .form-group { flex: 1; }
        label { display: block; margin-bottom: 5px; color: #D4AF37; font-size: 12px; font-weight: 600; }
        input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 6px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 14px;
        }
        input:focus { outline: none; border-color: #D4AF37; }
        .checkbox-row { display: flex; align-items: center; gap: 8px; margin: 12px 0; }
        .checkbox-row input[type="checkbox"] { width: 16px; height: 16px; }
        .checkbox-row label { margin: 0; color: #aaa; font-size: 13px; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s;
        }
        .btn-primary { background: #D4AF37; color: #1a1a2e; }
        .btn-primary:hover { background: #e5c04b; }
        .btn-primary:disabled { background: #555; color: #888; cursor: not-allowed; }
        .btn-secondary { background: #444; color: #fff; }
        .btn-secondary:hover { background: #555; }
        .btn-success { background: #28a745; color: #fff; }
        .btn-success:hover { background: #2fbc4e; }
        .btn-danger { background: #dc3545; color: #fff; }
        .btn-group { display: flex; gap: 8px; flex-wrap: wrap; }
        .status {
            padding: 10px 12px; border-radius: 6px; margin-top: 12px; font-size: 13px;
        }
        .status.loading { background: rgba(212,175,55,0.2); border: 1px solid #D4AF37; }
        .status.success { background: rgba(40,167,69,0.2); border: 1px solid #28a745; }
        .status.error { background: rgba(220,53,69,0.2); border: 1px solid #dc3545; }
        .spinner {
            display: inline-block; width: 14px; height: 14px;
            border: 2px solid rgba(255,255,255,0.3); border-radius: 50%;
            border-top-color: #D4AF37; animation: spin 0.7s linear infinite;
            margin-right: 8px; vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .hidden { display: none; }
        h3 { color: #D4AF37; font-size: 15px; margin-bottom: 10px; }

        /* Source chips */
        .sources-grid { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
        .source-chip {
            display: inline-flex; align-items: center; gap: 5px;
            background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px; padding: 5px 12px 5px 14px; font-size: 12px;
            cursor: pointer; transition: all 0.15s; user-select: none;
        }
        .source-chip:hover { background: rgba(212,175,55,0.12); border-color: rgba(212,175,55,0.4); }
        .source-chip.active { background: rgba(212,175,55,0.2); border-color: #D4AF37; }
        .source-chip .name { color: #ccc; }
        .source-chip.active .name { color: #D4AF37; }
        .source-chip .x {
            color: #555; font-size: 13px; line-height: 1; padding: 1px 3px;
            border-radius: 50%; transition: color 0.15s;
        }
        .source-chip .x:hover { color: #dc3545; }
        .source-count { color: #555; font-size: 12px; margin-left: 4px; }

        /* Results */
        .stats { display: flex; gap: 20px; margin: 12px 0; }
        .stat { text-align: center; }
        .stat-val { font-size: 22px; font-weight: bold; color: #D4AF37; }
        .stat-lbl { font-size: 10px; color: #666; text-transform: uppercase; }
        .method-tag {
            display: inline-block; background: #333; color: #aaa;
            padding: 2px 8px; border-radius: 10px; font-size: 10px;
            margin-right: 4px; margin-bottom: 6px;
        }
        .event-list { max-height: 400px; overflow-y: auto; }
        .event-item {
            background: rgba(0,0,0,0.25); border-radius: 6px;
            padding: 10px; margin-bottom: 6px; font-size: 13px;
        }
        .event-item strong { color: #fff; }
        .event-item p { color: #888; margin: 3px 0; font-size: 12px; }
        .event-item a { color: #6cf; font-size: 11px; }

        /* Log */
        .log {
            background: #0a0a0a; border-radius: 5px; padding: 10px;
            margin-top: 10px; max-height: 150px; overflow-y: auto;
            font-family: monospace; font-size: 11px; color: #0f0;
        }
        .log .e { color: #f66; }
        .log .s { color: #6f6; }
        .log .i { color: #6cf; }

        /* Progress */
        .progress-bar {
            height: 8px; border-radius: 4px; background: rgba(255,255,255,0.1);
            margin-top: 10px; overflow: hidden;
        }
        .progress-bar .fill {
            height: 100%; background: #D4AF37;
            transition: width 0.3s ease; width: 0%;
        }
        .scrape-all-log {
            background: #0a0a0a; border-radius: 5px; padding: 10px;
            margin-top: 10px; max-height: 250px; overflow-y: auto;
            font-family: monospace; font-size: 11px; color: #0f0;
        }
        /* Source manager table */
        #source-table tbody tr { border-bottom: 1px solid rgba(255,255,255,0.04); transition: background 0.1s; }
        #source-table tbody tr:hover { background: rgba(255,255,255,0.03); }
        #source-table td { padding: 8px 10px; vertical-align: middle; }
        .src-name { color: #ddd; font-weight: 500; cursor: pointer; }
        .src-name:hover { color: #D4AF37; }
        .src-url { color: #555; font-size: 10px; margin-top: 1px; }
        .p-tag { display:inline-block; padding:2px 7px; border-radius:10px; font-size:10px; font-weight:700; }
        .p-tag-1 { background:rgba(212,175,55,0.18); color:#D4AF37; border:1px solid rgba(212,175,55,0.4); }
        .p-tag-2 { background:rgba(40,167,69,0.15); color:#4caf70; border:1px solid rgba(40,167,69,0.3); }
        .p-tag-3 { background:rgba(85,102,170,0.15); color:#7788cc; border:1px solid rgba(85,102,170,0.3); }
        .status-badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; }
        .sb-working { background:rgba(40,167,69,0.15); color:#4caf70; border:1px solid rgba(40,167,69,0.3); }
        .sb-empty   { background:rgba(255,193,7,0.15); color:#ffc107; border:1px solid rgba(255,193,7,0.3); }
        .sb-error   { background:rgba(220,53,69,0.15); color:#e05565; border:1px solid rgba(220,53,69,0.3); cursor:pointer; }
        .sb-stale   { background:rgba(255,255,255,0.05); color:#666; border:1px solid rgba(255,255,255,0.1); }
        .sb-running { background:rgba(212,175,55,0.1); color:#D4AF37; border:1px solid rgba(212,175,55,0.2); }
        .method-pill { display:inline-block; background:#222; color:#888; padding:2px 7px; border-radius:8px; font-size:10px; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
        .row-btn { padding:3px 10px; font-size:11px; border:none; border-radius:5px; cursor:pointer; font-weight:600; transition:background 0.15s; }
        .row-scrape { background:#2a2a1a; color:#D4AF37; border:1px solid rgba(212,175,55,0.3); }
        .row-scrape:hover { background:rgba(212,175,55,0.2); }
        .row-scrape:disabled { opacity:0.4; cursor:not-allowed; }
        .row-del { background:transparent; color:#555; border:1px solid rgba(255,255,255,0.08); margin-left:4px; }
        .row-del:hover { color:#e05565; border-color:rgba(220,53,69,0.4); }
        .footer { text-align: center; color: #333; margin-top: 25px; font-size: 11px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Locate918</h1>
        <p class="subtitle">Universal Event Scraper &bull; Smart Extraction &bull; LLM Normalized</p>

        <!-- Scrape Form -->
        <div class="card">
            <h3>Scrape Events</h3>
            <div class="form-row">
                <div class="form-group">
                    <label>URL</label>
                    <input type="text" id="url" placeholder="https://venue-website.com/events">
                </div>
                <div class="form-group" style="max-width: 200px;">
                    <label>Source Name</label>
                    <input type="text" id="source" placeholder="Venue Name">
                </div>
                <div class="form-group" style="max-width: 140px;">
                    <label>Venue Priority</label>
                    <select id="venue-priority" style="width:100%;background:#1a1a1a;border:1px solid #333;color:#ccc;padding:8px 10px;border-radius:5px;font-size:13px;">
                        <option value="1">P1 — Flagship</option>
                        <option value="2" selected>P2 — Featured</option>
                        <option value="3">P3 — Standard</option>
                    </select>
                </div>
            </div>
            <div class="checkbox-row">
                <input type="checkbox" id="playwright" checked>
                <label for="playwright">Playwright (JS)</label>
                <input type="checkbox" id="future-only" checked style="margin-left: 16px;">
                <label for="future-only">Future only</label>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" id="scrape-btn" onclick="scrape()">Scrape</button>
                <button class="btn btn-secondary" onclick="saveUrl()">Save Source</button>
            </div>
            <div id="status" class="status hidden"></div>
            <div id="log-box" class="log hidden"></div>
        </div>

        <!-- Results -->
        <div id="results" class="card hidden">
            <h3>Results</h3>
            <div class="stats">
                <div class="stat"><div class="stat-val" id="stat-count">0</div><div class="stat-lbl">Events</div></div>
                <div class="stat"><div class="stat-val" id="stat-html">0</div><div class="stat-lbl">HTML Size</div></div>
            </div>
            <div id="methods-used"></div>
            <div class="btn-group" style="margin-bottom: 10px;">
                <button class="btn btn-success" onclick="sendToDatabase()">Send to Database</button>
                <button class="btn btn-secondary" onclick="saveJSON()">Save JSON</button>
            </div>
            <div id="event-list" class="event-list"></div>
        </div>

        <!-- Source Manager -->
        <div class="card" id="source-manager">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <div style="display:flex;align-items:center;gap:12px;">
                    <h3 style="margin:0;">Sources <span id="source-count" style="color:#555;font-size:12px;font-weight:400;"></span></h3>
                    <div id="tier-badges" style="display:flex;gap:5px;"></div>
                </div>
                <button class="btn btn-primary" id="scrape-all-btn" onclick="scrapeAll()" style="padding:7px 16px;font-size:12px;">&#9889; Scrape All</button>
            </div>
            <div id="scrape-all-status" class="status hidden"></div>
            <div class="progress-bar hidden" id="progress-bar"><div class="fill" id="progress-fill"></div></div>
            <div id="scrape-all-counter" style="text-align:center;color:#888;font-size:11px;margin-top:4px;" class="hidden"></div>
            <div style="overflow-x:auto;margin-top:8px;">
                <table id="source-table" style="width:100%;border-collapse:collapse;font-size:12px;">
                    <thead>
                        <tr style="border-bottom:1px solid rgba(255,255,255,0.08);">
                            <th style="text-align:left;padding:6px 10px;color:#555;font-weight:600;">Source</th>
                            <th style="text-align:center;padding:6px 8px;color:#555;font-weight:600;">P</th>
                            <th style="text-align:left;padding:6px 10px;color:#555;font-weight:600;white-space:nowrap;">Last Run</th>
                            <th style="text-align:center;padding:6px 8px;color:#555;font-weight:600;">Status</th>
                            <th style="text-align:center;padding:6px 6px;color:#555;font-weight:600;">Events</th>
                            <th style="text-align:left;padding:6px 10px;color:#555;font-weight:600;">Method</th>
                            <th style="text-align:center;padding:6px 8px;color:#555;font-weight:600;"></th>
                        </tr>
                    </thead>
                    <tbody id="source-tbody">
                        <tr><td colspan="7" style="text-align:center;padding:20px;color:#555;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">Locate918 &bull; Senior Capstone 2026</div>
    </div>

    <script>
var events = [];
var savedUrls = [];
var scrapeStatus = {};
var runningUrls  = new Set();

function log(msg, cls) {
    var b = document.getElementById("log-box");
    b.classList.remove("hidden");
    b.innerHTML += "<div" + (cls ? " class=\"" + cls + "\"" : "") + ">" + msg + "</div>";
    b.scrollTop = b.scrollHeight;
}
function status(msg, type) {
    type = type || "loading";
    var el = document.getElementById("status");
    el.className = "status " + type;
    el.innerHTML = type === "loading" ? "<span class=\"spinner\"></span>" + msg : msg;
    el.classList.remove("hidden");
}
function esc(s) {
    return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function escJs(s) {
    return String(s || "").replace(/'/g, String.fromCharCode(92) + "'");
}
function relTime(iso) {
    if (!iso) return "never";
    var d = new Date(iso), now = Date.now(), diff = Math.floor((now - d) / 1000);
    if (diff < 60)    return diff + "s ago";
    if (diff < 3600)  return Math.floor(diff/60) + "m ago";
    if (diff < 86400) return Math.floor(diff/3600) + "h ago";
    return Math.floor(diff/86400) + "d ago";
}
function statusBadge(st, errReport) {
    var map = {working:"sb-working", empty:"sb-empty", error:"sb-error", stale:"sb-stale"};
    var cls = map[st] || "sb-stale";
    var label = st || "stale";
    if (st === "error" && errReport) {
        return "<a href=\"/download/" + esc(errReport) + "\" class=\"status-badge " + cls + "\" title=\"Download error report\" download>&#9888; " + label + "</a>";
    }
    return "<span class=\"status-badge " + cls + "\">" + label + "</span>";
}
function pTag(p) {
    p = parseInt(p) || 3;
    return "<span class=\"p-tag p-tag-" + p + "\">P" + p + "</span>";
}

async function loadSourceTable() {
    try {
        var [urlsR, statusR] = await Promise.all([
            fetch("/saved-urls"),
            fetch("/scrape-status")
        ]);
        savedUrls    = await urlsR.json();
        scrapeStatus = await statusR.json();
    } catch(e) {
        savedUrls    = [];
        scrapeStatus = {};
    }
    renderSourceTable();
}

function renderSourceTable() {
    var tbody   = document.getElementById("source-tbody");
    var countEl = document.getElementById("source-count");
    if (!savedUrls.length) {
        tbody.innerHTML = "<tr><td colspan=\"7\" style=\"text-align:center;padding:20px;color:#555;\">No saved sources yet. Scrape a URL above to add one.</td></tr>";
        countEl.textContent = "";
        return;
    }
    countEl.textContent = "(" + savedUrls.length + ")";

    var t = {1:0,2:0,3:0};
    savedUrls.forEach(function(u) { t[parseInt(u.venue_priority||u.priority||3)]++; });
    var tb = document.getElementById("tier-badges");
    if (tb) tb.innerHTML =
        (t[1] ? "<span class=\"p-tag p-tag-1\" style=\"font-size:10px;\">P1 &times;" + t[1] + "</span>" : "") +
        (t[2] ? "<span class=\"p-tag p-tag-2\" style=\"font-size:10px;margin-left:4px;\">P2 &times;" + t[2] + "</span>" : "") +
        (t[3] ? "<span class=\"p-tag p-tag-3\" style=\"font-size:10px;margin-left:4px;\">P3 &times;" + t[3] + "</span>" : "");

    var sorted = savedUrls.slice().sort(function(a,b) {
        var pa = parseInt(a.venue_priority||a.priority||3);
        var pb = parseInt(b.venue_priority||b.priority||3);
        if (pa !== pb) return pa - pb;
        return (a.name||"").localeCompare(b.name||"");
    });

    tbody.innerHTML = sorted.map(function(u) {
        var url = u.url;
        var st  = scrapeStatus[url] || {};
        var p   = parseInt(u.venue_priority || u.priority || 3);
        var isRunning = runningUrls.has(url);

        var statusCell = isRunning
            ? "<span class=\"status-badge sb-running\"><span class=\"spinner\" style=\"width:10px;height:10px;\"></span> running</span>"
            : statusBadge(st.status, st.error_report);

        var methods = (st.methods || []);
        var methodCell = methods.length
            ? "<span class=\"method-pill\" title=\"" + esc(methods.join(", ")) + "\">" + esc(methods[0].replace(/ \(\d+\)/, "")) + "</span>"
            : "<span style=\"color:#444;\">—</span>";

        var evCount = (st.event_count != null)
            ? "<span style=\"color:" + (st.event_count > 0 ? "#4caf70" : "#666") + ";font-weight:600;\">" + st.event_count + "</span>"
            : "<span style=\"color:#444;\">—</span>";

        var rowId = "row-" + btoa(url).replace(/[^a-zA-Z0-9]/g,"").slice(0,12);

        return "<tr id=\"" + rowId + "\">" +
            "<td>" +
              "<div class=\"src-name\" onclick=\"selectSource('" + escJs(url) + "','" + escJs(u.name) + "'," + (u.playwright !== false) + "," + p + ")\">" + esc(u.name) + "</div>" +
              "<div class=\"src-url\">" + esc(url.replace(/^https?:\/\//, "").split("/")[0]) + "</div>" +
            "</td>" +
            "<td style=\"text-align:center;\">" + pTag(p) + "</td>" +
            "<td style=\"color:#555;white-space:nowrap;\">" + esc(relTime(st.last_scraped)) + "</td>" +
            "<td style=\"text-align:center;\">" + statusCell + "</td>" +
            "<td style=\"text-align:center;\">" + evCount + "</td>" +
            "<td>" + methodCell + "</td>" +
            "<td style=\"text-align:center;white-space:nowrap;\">" +
              "<button class=\"row-btn row-scrape\" id=\"btn-" + rowId + "\"" +
                (isRunning ? " disabled" : "") +
                " onclick=\"scrapeSource('" + escJs(url) + "','" + escJs(u.name) + "'," + (u.playwright !== false) + "," + p + ")\"" +
              ">&#9654;</button>" +
              "<button class=\"row-btn row-del\" onclick=\"deleteUrl('" + escJs(url) + "')\">&#215;</button>" +
            "</td>" +
        "</tr>";
    }).join("");
}

function selectSource(url, name, pw, vp) {
    document.getElementById("url").value    = url;
    document.getElementById("source").value = name;
    document.getElementById("playwright").checked = pw;
    document.getElementById("venue-priority").value = vp || 2;
}

async function deleteUrl(url) {
    await fetch("/saved-urls", {
        method: "DELETE",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: url})
    });
    loadSourceTable();
}

async function saveUrl() {
    var url = document.getElementById("url").value.trim();
    var name = document.getElementById("source").value.trim();
    var pw = document.getElementById("playwright").checked;
    var vp = parseInt(document.getElementById("venue-priority").value);
    if (!url || !name) { status("Enter a URL and source name", "error"); return; }
    try {
        await fetch("/saved-urls", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: url, name: name, playwright: pw, venue_priority: vp})
        });
        status("Saved " + name + " (P" + vp + ")", "success");
        loadSourceTable();
    } catch(e) { status("Save error: " + e.message, "error"); }
}

async function scrapeSource(url, name, usePw, vp) {
    if (runningUrls.has(url)) return;
    runningUrls.add(url);
    renderSourceTable();
    try {
        var r = await fetch("/scrape-source", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: url, name: name, use_playwright: usePw, venue_priority: vp})
        });
        var d = await r.json();
        if (d.error && !d.status) {
            scrapeStatus[url] = { status: "error", error: d.error, last_scraped: new Date().toISOString(), event_count: 0, methods: [] };
        } else {
            scrapeStatus[url] = {
                status:       d.status,
                event_count:  d.event_count,
                methods:      d.methods,
                last_scraped: d.last_scraped,
                error:        d.error,
                error_report: d.error_report,
            };
        }
    } catch(e) {
        scrapeStatus[url] = { status: "error", error: e.message, last_scraped: new Date().toISOString(), event_count: 0, methods: [] };
    } finally {
        runningUrls.delete(url);
        renderSourceTable();
    }
}

async function scrapeAll() {
    var statusEl = document.getElementById("scrape-all-status");
    var bar      = document.getElementById("progress-fill");
    var barC     = document.getElementById("progress-bar");
    var counter  = document.getElementById("scrape-all-counter");
    var btn      = document.getElementById("scrape-all-btn");

    btn.disabled = true;
    statusEl.className = "status loading";
    statusEl.innerHTML = "<span class=\"spinner\"></span>Starting priority run...";
    statusEl.classList.remove("hidden");
    barC.classList.remove("hidden");
    counter.classList.remove("hidden");
    bar.style.width = "0%";
    counter.textContent = "";

    try {
        var response = await fetch("/scrape-all", { method: "POST" });
        var reader   = response.body.getReader();
        var decoder  = new TextDecoder();
        var buffer   = "";
        var total    = 0;

        while (true) {
            var chunk = await reader.read();
            if (chunk.done) break;
            buffer += decoder.decode(chunk.value, { stream: true });
            var lines = buffer.split("\n");
            buffer = lines.pop();

            for (var i = 0; i < lines.length; i++) {
                if (lines[i].indexOf("data: ") !== 0) continue;
                try {
                    var d = JSON.parse(lines[i].slice(6));
                    if (d.type === "start") {
                        total = d.total_sources;
                        counter.textContent = "0 / " + total;
                        statusEl.innerHTML = "<span class=\"spinner\"></span>Scraping P1 (" + d.p1 + ") \u2192 P2 (" + d.p2 + ") \u2192 P3 (" + d.p3 + ")";
                    } else if (d.type === "tier_start") {
                        statusEl.innerHTML = "<span class=\"spinner\"></span>Running P" + d.tier + " tier (" + d.count + " sources concurrently)";
                    } else if (d.type === "source_start") {
                        runningUrls.add(d.url);
                        renderSourceTable();
                    } else if (d.type === "source_done") {
                        runningUrls.delete(d.url);
                        scrapeStatus[d.url] = {
                            status:       d.status,
                            event_count:  d.event_count,
                            methods:      d.methods,
                            last_scraped: new Date().toISOString(),
                            error:        d.error,
                            error_report: d.error_report,
                        };
                        bar.style.width = Math.round((d.completed / d.total) * 100) + "%";
                        counter.textContent = d.completed + " / " + d.total;
                        renderSourceTable();
                    } else if (d.type === "complete") {
                        bar.style.width = "100%";
                        statusEl.className = "status success";
                        statusEl.textContent = "Done \u2014 " + d.total_events + " events found, " + d.total_saved + " saved to DB (" + d.sources_scraped + " sources)";
                        counter.textContent = d.sources_scraped + " / " + total;
                    }
                } catch(pe) {}
            }
        }
    } catch(e) {
        statusEl.className = "status error";
        statusEl.textContent = "Error: " + e.message;
    } finally {
        runningUrls.clear();
        btn.disabled = false;
        renderSourceTable();
    }
}

async function scrape() {
    var url       = document.getElementById("url").value.trim();
    var src       = document.getElementById("source").value.trim() || "unknown";
    var pw        = document.getElementById("playwright").checked;
    var futureOnly = document.getElementById("future-only").checked;
    if (!url) { status("Enter a URL", "error"); return; }

    document.getElementById("log-box").innerHTML = "";
    document.getElementById("scrape-btn").disabled = true;
    document.getElementById("results").classList.add("hidden");
    status("Scraping " + src + "...");
    log("Fetching: " + url);
    log("Method: " + (pw ? "Playwright" : "httpx") + " | Future only: " + futureOnly, "i");

    try {
        var r = await fetch("/scrape", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: url, source_name: src, use_playwright: pw, future_only: futureOnly})
        });
        var d = await r.json();

        if (d.robots_blocked) { log("BLOCKED by robots.txt", "e"); status(d.error, "error"); return; }
        if (d.error) { log("ERROR: " + d.error, "e"); status("Error: " + d.error, "error"); return; }

        events = d.events;
        log("HTML: " + (d.html_size/1024).toFixed(1) + "KB | Found " + events.length + " events", "s");
        if (d.methods && d.methods.length) log("Methods: " + d.methods.join(", "), "i");

        document.getElementById("stat-count").textContent = events.length;
        document.getElementById("stat-html").textContent  = (d.html_size/1024).toFixed(1) + "KB";

        var md = document.getElementById("methods-used");
        md.innerHTML = (d.methods||[]).map(function(m){ return "<span class=\"method-tag\">" + m + "</span>"; }).join("");

        var list = document.getElementById("event-list");
        if (!events.length) {
            list.innerHTML = "<p style=\"color:#666;\">No events found.</p>";
        } else {
            list.innerHTML = events.map(function(e) {
                return "<div class=\"event-item\"><strong>" + esc(e.title||"Untitled") + "</strong>" +
                    (e.date ? "<p>" + esc(e.date) + "</p>" : e.start_time ? "<p>" + esc(e.start_time) + "</p>" : "") +
                    (e.venue ? "<p>" + esc(e.venue) + "</p>" : "") +
                    (e.source_url ? "<a href=\"" + esc(e.source_url) + "\" target=\"_blank\">View &#8594;</a>" : "") +
                    "</div>";
            }).join("");
        }

        document.getElementById("results").classList.remove("hidden");
        status("Found " + events.length + " events", "success");
        loadSourceTable();
    } catch(e) {
        log("Error: " + e.message, "e");
        status("Error: " + e.message, "error");
    } finally {
        document.getElementById("scrape-btn").disabled = false;
    }
}

async function saveJSON() {
    if (!events.length) return;
    var src = document.getElementById("source").value.trim() || "unknown";
    try {
        var r = await fetch("/save", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({events: events, source: src})
        });
        var d = await r.json();
        status("Saved " + d.count + " events to " + d.filename, "success");
    } catch(e) { status("Save error: " + e.message, "error"); }
}

async function sendToDatabase() {
    if (!events.length) return;
    status("Normalizing & sending to database...");
    try {
        var r = await fetch("/to-database", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({events: events})
        });
        var d = await r.json();
        var msg = d.saved + "/" + d.total + " saved";
        if (d.normalized)        msg += " (normalized)";
        if (d.venues_registered) msg += " | " + d.venues_registered + " venues";
        if (d.venues_enriched)   msg += " (" + d.venues_enriched + " enriched)";
        status(msg, "success");
    } catch(e) { status("DB error: " + e.message, "error"); }
}

loadSourceTable();
    </script>
</body>
</html>
'''


VENUE_PRIORITY_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Venue Priority — Locate918</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0d0d0d; color: #ccc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 13px; }
        .header { background: #111; border-bottom: 1px solid #222; padding: 14px 24px; display: flex; align-items: center; gap: 16px; }
        .header h1 { color: #D4AF37; font-size: 18px; font-weight: 700; }
        .header a { color: #888; text-decoration: none; font-size: 12px; }
        .header a:hover { color: #D4AF37; }
        .container { max-width: 1100px; margin: 0 auto; padding: 24px; }
        .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 18px; flex-wrap: wrap; }
        .toolbar input { background: #1a1a1a; border: 1px solid #333; color: #ccc; padding: 8px 12px; border-radius: 6px; font-size: 13px; width: 260px; }
        .toolbar input:focus { outline: none; border-color: #D4AF37; }
        .filter-btns { display: flex; gap: 6px; }
        .filter-btn { background: #1a1a1a; border: 1px solid #333; color: #888; padding: 7px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; transition: all 0.2s; }
        .filter-btn.active, .filter-btn:hover { border-color: #D4AF37; color: #D4AF37; }
        .count { color: #555; font-size: 12px; margin-left: auto; }
        table { width: 100%; border-collapse: collapse; }
        thead th { background: #161616; color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 10px 12px; text-align: left; border-bottom: 1px solid #222; position: sticky; top: 0; }
        tbody tr { border-bottom: 1px solid #1a1a1a; transition: background 0.15s; }
        tbody tr:hover { background: #161616; }
        td { padding: 10px 12px; vertical-align: middle; }
        .venue-name { color: #e0e0e0; font-weight: 500; }
        .venue-address { color: #555; font-size: 11px; margin-top: 2px; }
        .website-link { color: #D4AF37; text-decoration: none; font-size: 11px; }
        .website-link:hover { text-decoration: underline; }
        .priority-cell { display: flex; gap: 6px; align-items: center; }
        .p-btn { width: 32px; height: 28px; border-radius: 5px; border: 1px solid #333; background: #1a1a1a; color: #666; cursor: pointer; font-size: 12px; font-weight: 700; transition: all 0.15s; }
        .p-btn:hover { border-color: #888; color: #ccc; }
        .p-btn.active-1 { background: #2a1f00; border-color: #D4AF37; color: #D4AF37; }
        .p-btn.active-2 { background: #0d2a1a; border-color: #4CAF50; color: #4CAF50; }
        .p-btn.active-3 { background: #1a1a2a; border-color: #5566aa; color: #7788cc; }
        .saving { color: #888; font-size: 11px; margin-left: 6px; }
        .saved-flash { color: #4CAF50; font-size: 11px; margin-left: 6px; }
        .error-flash { color: #e74c3c; font-size: 11px; margin-left: 6px; }
        .legend { display: flex; gap: 18px; margin-bottom: 16px; font-size: 12px; }
        .legend-item { display: flex; align-items: center; gap-6px; gap: 6px; }
        .dot { width: 10px; height: 10px; border-radius: 50%; }
        .dot-1 { background: #D4AF37; }
        .dot-2 { background: #4CAF50; }
        .dot-3 { background: #5566aa; }
        .loading { text-align: center; color: #555; padding: 40px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Venue Priority</h1>
        <a href="/">← Scraper</a>
    </div>
    <div class="container">
        <div class="legend">
            <div class="legend-item"><div class="dot dot-1"></div> P1 Flagship — shown first in feed</div>
            <div class="legend-item"><div class="dot dot-2"></div> P2 Featured — shown above P3</div>
            <div class="legend-item"><div class="dot dot-3"></div> P3 Standard — libraries, restaurants, etc.</div>
        </div>
        <div class="toolbar">
            <input type="text" id="search" placeholder="Search venues..." oninput="renderTable()">
            <div class="filter-btns">
                <button class="filter-btn active" onclick="setFilter('all', this)">All</button>
                <button class="filter-btn" onclick="setFilter('1', this)">P1</button>
                <button class="filter-btn" onclick="setFilter('2', this)">P2</button>
                <button class="filter-btn" onclick="setFilter('3', this)">P3</button>
            </div>
            <span class="count" id="count"></span>
        </div>
        <div id="table-wrap">
            <div class="loading">Loading venues...</div>
        </div>
    </div>

<script>
var allVenues = [];
var activeFilter = 'all';

async function loadVenues() {
    try {
        var r = await fetch('/api/venues/all');
        allVenues = await r.json();
        renderTable();
    } catch(e) {
        document.getElementById('table-wrap').innerHTML = '<div class="loading">Error loading venues: ' + e.message + '</div>';
    }
}

function setFilter(f, btn) {
    activeFilter = f;
    document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    renderTable();
}

function renderTable() {
    var q = document.getElementById('search').value.toLowerCase();
    var rows = allVenues.filter(function(v) {
        var matchQ = !q || v.name.toLowerCase().includes(q) || (v.address||'').toLowerCase().includes(q);
        var p = v.venue_priority || 3;
        var matchF = activeFilter === 'all' || String(p) === activeFilter;
        return matchQ && matchF;
    });

    document.getElementById('count').textContent = rows.length + ' venues';

    if (!rows.length) {
        document.getElementById('table-wrap').innerHTML = '<div class="loading">No venues match.</div>';
        return;
    }

    var html = '<table><thead><tr>' +
        '<th>Venue</th><th>Address</th><th>Website</th><th style="width:140px">Priority</th>' +
        '</tr></thead><tbody>';

    rows.forEach(function(v) {
        var p = v.venue_priority || 3;
        html += '<tr id="row-' + v.id + '">' +
            '<td><div class="venue-name">' + esc(v.name) + '</div></td>' +
            '<td><div class="venue-address">' + esc(v.address || '—') + '</div></td>' +
            '<td>' + (v.website ? '<a class="website-link" href="' + esc(v.website) + '" target="_blank">' + esc(v.website.replace(/https?:\\/\\//, '').split('/')[0]) + '</a>' : '<span style="color:#444">—</span>') + '</td>' +
            '<td><div class="priority-cell">' +
                '<button class="p-btn ' + (p===1?'active-1':'') + '" onclick="setPriority(\'' + v.id + '\', 1, this)">P1</button>' +
                '<button class="p-btn ' + (p===2?'active-2':'') + '" onclick="setPriority(\'' + v.id + '\', 2, this)">P2</button>' +
                '<button class="p-btn ' + (p===3?'active-3':'') + '" onclick="setPriority(\'' + v.id + '\', 3, this)">P3</button>' +
                '<span id="msg-' + v.id + '"></span>' +
            '</div></td>' +
        '</tr>';
    });

    html += '</tbody></table>';
    document.getElementById('table-wrap').innerHTML = html;
}

async function setPriority(id, priority, btn) {
    var msg = document.getElementById('msg-' + id);
    msg.className = 'saving';
    msg.textContent = '…';

    // Optimistically update button styles
    var row = document.getElementById('row-' + id);
    row.querySelectorAll('.p-btn').forEach(function(b) {
        b.classList.remove('active-1', 'active-2', 'active-3');
    });
    btn.classList.add('active-' + priority);

    try {
        var r = await fetch('/api/venues/set-priority', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id: id, venue_priority: priority})
        });
        var d = await r.json();
        if (d.ok) {
            // Update local data
            var v = allVenues.find(function(x) { return x.id === id; });
            if (v) v.venue_priority = priority;
            msg.className = 'saved-flash';
            msg.textContent = '✓';
            setTimeout(function() { msg.textContent = ''; }, 1500);
        } else {
            msg.className = 'error-flash';
            msg.textContent = 'Error';
        }
    } catch(e) {
        msg.className = 'error-flash';
        msg.textContent = 'Error';
    }
}

function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

loadVenues();
</script>
</body>
</html>
'''


# ============================================================================
# EVENT TRANSFORMATION
# ============================================================================

def transform_event_for_backend(event: dict, source_priority: int = None) -> dict:
    """
    Transform scraped event to match Rust backend's CreateEvent schema.
    Used as primary transform after normalization, or as fallback if LLM is down.
    """
    from dateutil import parser as date_parser
    from datetime import timezone, datetime, timedelta

    transformed = {
        'title': event.get('title', 'Untitled Event'),
    }

    source_url = (
            event.get('source_url') or
            event.get('detail_url') or
            event.get('url') or
            event.get('tickets_url') or
            ''
    )
    transformed['source_url'] = source_url

    # --- Priority and canonical URL ---
    # Use explicitly passed priority, then check event dict, then auto-detect from URL
    priority = (
            source_priority
            or event.get('source_priority')
            or get_source_priority(source_url)
    )
    transformed['source_priority'] = priority

    # canonical_url only gets set when the source is a direct venue or ticketing site
    if source_url and not is_aggregator_url(source_url):
        transformed['canonical_url'] = source_url

    date_str = (
            event.get('start_time') or
            event.get('startDate') or
            event.get('date') or
            event.get('start_date') or
            ''
    )
    if date_str:
        try:
            import pytz as _pytz
            tulsa_tz = _pytz.timezone('America/Chicago')
            parsed_date = date_parser.parse(str(date_str), fuzzy=True)
            if parsed_date.tzinfo is None:
                # Naive datetime — assume Tulsa local time (CDT/CST) and convert to UTC
                parsed_date = tulsa_tz.localize(parsed_date).astimezone(_pytz.utc)
            else:
                # Already has timezone info — just convert to UTC
                parsed_date = parsed_date.astimezone(_pytz.utc)
            transformed['start_time'] = parsed_date.isoformat()
        except Exception as e:
            print(f"[DB] Timezone parse error for '{date_str}': {e}")
            # Fallback: try basic parse and stamp as UTC
            try:
                parsed_date = date_parser.parse(str(date_str), fuzzy=True)
                from datetime import timezone as _tz
                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(tzinfo=_tz.utc)
                transformed['start_time'] = parsed_date.isoformat()
            except:
                fallback = datetime.now(timezone.utc) + timedelta(days=1)
                transformed['start_time'] = fallback.isoformat()
                print(f"[DB] Warning: Could not parse start date '{date_str}', using fallback")
    else:
        fallback = datetime.now(timezone.utc) + timedelta(days=1)
        transformed['start_time'] = fallback.isoformat()

    end_str = (
            event.get('end_time') or
            event.get('endDate') or
            event.get('end_date') or
            ''
    )
    if end_str:
        try:
            import pytz as _pytz
            tulsa_tz = _pytz.timezone('America/Chicago')
            parsed_end = date_parser.parse(str(end_str), fuzzy=True)
            if parsed_end.tzinfo is None:
                parsed_end = tulsa_tz.localize(parsed_end).astimezone(_pytz.utc)
            else:
                parsed_end = parsed_end.astimezone(_pytz.utc)
            transformed['end_time'] = parsed_end.isoformat()
        except Exception as e:
            try:
                parsed_end = date_parser.parse(str(end_str), fuzzy=True)
                from datetime import timezone as _tz
                if parsed_end.tzinfo is None:
                    parsed_end = parsed_end.replace(tzinfo=_tz.utc)
                transformed['end_time'] = parsed_end.isoformat()
            except:
                pass

    source_name = event.get('source_name') or event.get('source') or ''
    if source_name:
        transformed['source_name'] = source_name

    if event.get('venue'):
        transformed['venue'] = event['venue']
    if event.get('venue_address'):
        transformed['venue_address'] = event['venue_address']

    if event.get('location'):
        loc = event['location']
        if isinstance(loc, str) and ',' in loc and loc.replace(',', '').replace('.', '').replace('-', '').isdigit():
            pass
        else:
            transformed['location'] = loc
    elif event.get('city'):
        transformed['location'] = event['city']

    if event.get('description'):
        desc = event['description']
        if isinstance(desc, str):
            desc = desc.strip()[:2000]
            transformed['description'] = desc

    if event.get('image_url'):
        transformed['image_url'] = event['image_url']

    price_min = None
    price_max = None

    if event.get('price_min') is not None:
        try:
            price_min = float(event['price_min'])
        except (ValueError, TypeError):
            pass
    if event.get('price_max') is not None:
        try:
            price_max = float(event['price_max'])
        except (ValueError, TypeError):
            pass

    if price_min is None and event.get('price'):
        price_str = str(event['price']).replace('$', '').replace(',', '').strip()
        if '-' in price_str:
            parts = price_str.split('-')
            try:
                price_min = float(parts[0].strip())
                price_max = float(parts[1].strip())
            except:
                pass
        elif price_str.lower() in ['free', '0', '0.00']:
            price_min = 0.0
            price_max = 0.0
        else:
            try:
                price_min = float(price_str)
            except:
                pass

    if event.get('is_free') == True:
        price_min = 0.0
        price_max = 0.0

    if price_min is not None:
        transformed['price_min'] = price_min
    if price_max is not None:
        transformed['price_max'] = price_max

    if event.get('categories'):
        cats = event['categories']
        if isinstance(cats, str):
            transformed['categories'] = [cats]
        elif isinstance(cats, list):
            transformed['categories'] = [c for c in cats if c]

    if event.get('outdoor') is not None:
        transformed['outdoor'] = bool(event['outdoor'])
    else:
        transformed['outdoor'] = False

    if event.get('family_friendly') is not None:
        transformed['family_friendly'] = bool(event['family_friendly'])
    else:
        transformed['family_friendly'] = False

    # --- Content hash for cross-source deduplication ---
    transformed['content_hash'] = make_content_hash(
        transformed.get('title', ''),
        transformed.get('start_time', ''),
        transformed.get('venue', ''),
    )

    return transformed


# ============================================================================
# LLM NORMALIZATION (Gemini via LLM Service on :8001)
# ============================================================================

def normalize_batch(events: list, source_url: str = "", source_name: str = "") -> list:
    """
    Send a batch of scraped events through the LLM normalization endpoint.
    Retries on 503 (Gemini overload) with exponential backoff.
    Chunks into groups of 10 to stay within token limits.
    """
    import time

    all_normalized = []
    chunk_size = 10
    failed_chunks = 0
    MAX_RETRIES = 4

    for i in range(0, len(events), chunk_size):
        chunk = events[i:i + chunk_size]

        # Strip blank start_time so Gemini infers from title/description
        # rather than receiving an empty string that fails Pydantic validation
        clean_chunk = []
        for ev in chunk:
            ev_copy = dict(ev)
            if not ev_copy.get('start_time'):
                ev_copy.pop('start_time', None)
            clean_chunk.append(ev_copy)

        payload = {
            "raw_content": json.dumps(clean_chunk),
            "source_url": source_url,
            "content_type": "json"
        }

        success = False
        for attempt in range(MAX_RETRIES):
            try:
                resp = httpx.post(
                    f"{LLM_SERVICE_URL}/api/normalize",
                    json=payload,
                    timeout=120
                )

                if resp.status_code == 200:
                    data = resp.json()
                    normalized = data.get("events", [])
                    if normalized:
                        print(f"[Normalize] Chunk {i // chunk_size + 1}: {len(chunk)} raw → {len(normalized)} normalized")
                        all_normalized.extend(normalized)
                    else:
                        print(f"[Normalize] Chunk {i // chunk_size + 1}: Got empty result, skipping chunk")
                        failed_chunks += 1
                    success = True
                    break

                elif resp.status_code in [500, 503]:
                    wait = 5 * (2 ** attempt)  # 5s, 10s, 20s, 40s
                    print(f"[Normalize] Gemini overloaded (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {wait}s...")
                    time.sleep(wait)

                else:
                    print(f"[Normalize] API returned {resp.status_code}: {resp.text[:200]}")
                    failed_chunks += 1
                    success = True
                    break

            except httpx.ConnectError:
                print(f"[Normalize] ⚠ LLM service not running at {LLM_SERVICE_URL} — using fallback")
                return []
            except Exception as e:
                print(f"[Normalize] Error: {e}")
                failed_chunks += 1
                success = True
                break

        if not success:
            print(f"[Normalize] Chunk {i // chunk_size + 1}: All {MAX_RETRIES} retries failed, skipping")
            failed_chunks += 1

        # Small delay between chunks to avoid hammering Gemini
        time.sleep(2)

    if failed_chunks:
        print(f"[Normalize] {failed_chunks} chunk(s) failed — {len(all_normalized)} events normalized total")

    return all_normalized


def _geocode_venue(venue_name: str, city: str = "Tulsa, OK") -> tuple:
    """
    Quick synchronous geocode via Google Places Text Search.
    Returns (lat, lng) tuple or None.
    """
    if not GOOGLE_PLACES_API_KEY:
        return None

    try:
        resp = httpx.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={
                "query": f"{venue_name} {city}",
                "key": GOOGLE_PLACES_API_KEY,
            },
            timeout=10
        )
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            location = data["results"][0].get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            if lat and lng:
                return (lat, lng)
    except Exception:
        pass
    return None


# ============================================================================
# VENUE MANAGER HELPERS
# ============================================================================

async def lookup_venue_google_places(venue_name: str, city: str = "Tulsa, OK") -> dict:
    """
    Look up venue details from Google Places API.
    """
    result = {
        "address": "",
        "website": "",
        "phone": "",
        "place_id": "",
        "types": [],
        "rating": None,
        "wheelchair_accessible": None,
        "latitude": None,
        "longitude": None,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            search_query = f"{venue_name} {city}"
            search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            search_resp = await client.get(search_url, params={
                "query": search_query,
                "key": GOOGLE_PLACES_API_KEY,
            })
            search_data = search_resp.json()

            if search_data.get("status") != "OK" or not search_data.get("results"):
                return {"error": f"Place not found: {venue_name}"}

            place = search_data["results"][0]
            result["place_id"] = place.get("place_id", "")
            result["address"] = place.get("formatted_address", "")
            result["types"] = place.get("types", [])
            result["rating"] = place.get("rating")

            # Extract lat/lng from text search geometry
            geometry = place.get("geometry", {})
            location = geometry.get("location", {})
            if location.get("lat") and location.get("lng"):
                result["latitude"] = location["lat"]
                result["longitude"] = location["lng"]

            if result["place_id"]:
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                details_resp = await client.get(details_url, params={
                    "place_id": result["place_id"],
                    "fields": "website,formatted_phone_number,wheelchair_accessible_entrance",
                    "key": GOOGLE_PLACES_API_KEY,
                })
                details_data = details_resp.json()

                if details_data.get("status") == "OK" and details_data.get("result"):
                    details = details_data["result"]
                    result["website"] = details.get("website", "")
                    result["phone"] = details.get("formatted_phone_number", "")
                    result["wheelchair_accessible"] = details.get("wheelchair_accessible_entrance")

            return result

    except Exception as e:
        return {"error": str(e)}


def infer_venue_type_from_google(types: list, name: str) -> str:
    """Infer venue type from Google Places types."""
    type_mapping = {
        "bar": "Bar/Club",
        "night_club": "Bar/Club",
        "restaurant": "Restaurant",
        "cafe": "Coffee Shop",
        "museum": "Museum",
        "art_gallery": "Gallery",
        "movie_theater": "Theater",
        "performing_arts_theater": "Theater",
        "stadium": "Arena",
        "church": "Church",
        "park": "Park",
        "library": "Library",
        "university": "University",
        "school": "University",
        "casino": "Casino",
        "lodging": "Hotel",
        "bowling_alley": "Entertainment",
        "amusement_park": "Entertainment",
        "zoo": "Zoo/Aquarium",
        "aquarium": "Zoo/Aquarium",
    }

    for place_type in types:
        if place_type in type_mapping:
            return type_mapping[place_type]

    name_lower = name.lower()
    if "museum" in name_lower:
        return "Museum"
    elif "theater" in name_lower or "theatre" in name_lower:
        return "Theater"
    elif "bar" in name_lower or "pub" in name_lower:
        return "Bar/Club"
    elif "church" in name_lower:
        return "Church"
    elif "park" in name_lower:
        return "Park"
    elif "ballroom" in name_lower or "center" in name_lower:
        return "Concert Hall"
    elif "brewery" in name_lower or "brewing" in name_lower:
        return "Brewery"
    elif "coffee" in name_lower or "cafe" in name_lower:
        return "Coffee Shop"

    return "Venue"


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def register_routes(app):
    """Register all Flask routes on the given app instance."""

    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    CRON_SECRET = os.environ.get("CRON_SECRET", "")

    @app.before_request
    def check_auth():
        if not ADMIN_PASSWORD:
            return  # no password set, open access

        # Allow cron requests authenticated via CRON_SECRET header or query param
        # Works regardless of IP (Railway cron, external triggers, etc.)
        if request.path in ('/cron-scrape', '/scrape-all'):
            cron_token = (
                    request.headers.get('X-Cron-Secret') or
                    request.args.get('secret') or
                    ''
            )
            if CRON_SECRET and cron_token == CRON_SECRET:
                return  # authenticated via cron secret
            # Also allow localhost (backward compat)
            if request.remote_addr in ('127.0.0.1', '::1'):
                return

        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response(
                "Unauthorized", 401,
                {"WWW-Authenticate": 'Basic realm="Locate918 Admin"'}
            )

    @app.route('/')
    def index():
        return render_template('scraperUI.html')

    @app.route('/saved-urls', methods=['GET'])
    def get_saved_urls():
        return jsonify(load_saved_urls())

    @app.route('/saved-urls', methods=['POST'])
    def add_saved_url():
        data = request.json
        urls = save_url(
            data.get('url', ''),
            data.get('name', ''),
            data.get('playwright', True),
            data.get('priority'),        # None → auto-detected from domain
            data.get('venue_priority'),  # None → auto-detected from venue name
        )
        return jsonify(urls)

    @app.route('/saved-urls', methods=['DELETE'])
    def remove_saved_url():
        data = request.json
        urls = delete_saved_url(data.get('url', ''))
        return jsonify(urls)

    @app.route('/scrape', methods=['POST'])
    def scrape():
        data = request.json
        url = data.get('url')
        source_name = data.get('source_name', 'unknown')
        use_playwright = data.get('use_playwright', True)
        future_only = data.get('future_only', True)
        ignore_robots = data.get('ignore_robots', False)

        if not url:
            return jsonify({"error": "URL required"}), 400

        # Resolve canonical venue name from URL (prevents typos like "shrine")
        source_name = resolve_source_name(url, source_name)

        robots_result = check_robots_txt(url)
        print(f"[robots.txt] {url}: {robots_result['message']}")

        if not robots_result['allowed'] and not ignore_robots:
            return jsonify({
                "error": f"Blocked by robots.txt: {robots_result['message']}",
                "robots_blocked": True,
                "events": [],
                "html_size": 0,
                "methods": []
            }), 403

        save_url(url, source_name, use_playwright)

        try:
            if use_playwright:
                html = asyncio.run(fetch_with_playwright(url))
            else:
                html = asyncio.run(fetch_with_httpx(url))

            methods = []
            events = []

            eca_events, eca_detected = asyncio.run(extract_eventcalendarapp(html, source_name, url, future_only))
            if eca_detected and eca_events:
                events = eca_events
                methods.append(f"EventCalendarApp API ({len(events)})")
                print(f"[EventCalendarApp] SUCCESS: {len(events)} events via direct API")

            if not events:
                timely_events, timely_detected = asyncio.run(extract_timely(html, source_name, url, future_only))
                if timely_detected and timely_events:
                    events = timely_events
                    methods.append(f"Timely API ({len(events)})")
                    print(f"[Timely] SUCCESS: {len(events)} events via direct API")

            if not events:
                bok_events, bok_detected = asyncio.run(extract_bok_center(html, source_name, url, future_only))
                if bok_detected and bok_events:
                    events = bok_events
                    methods.append(f"BOK Center API ({len(events)})")
                    print(f"[BOK Center] SUCCESS: {len(events)} events via API")

            if not events:
                cc_events, cc_detected = asyncio.run(extract_circle_cinema_events(html, source_name, url, future_only))
                if cc_detected and cc_events:
                    events = cc_events
                    methods.append(f"Circle Cinema ({len(events)})")
                    print(f"[CircleCinema] SUCCESS: {len(events)} events")

            if not events:
                expo_events, expo_detected = asyncio.run(extract_expo_square_events(html, source_name, url, future_only))
                if expo_detected and expo_events:
                    events = expo_events
                    methods.append(f"Expo Square API ({len(events)})")
                    print(f"[Expo Square] SUCCESS: {len(events)} events via API")

            if not events:
                eb_events, eb_detected = asyncio.run(extract_eventbrite_api_events(html, source_name, url, future_only))
                if eb_detected and eb_events:
                    events = eb_events
                    methods.append(f"Eventbrite API ({len(events)})")
                    print(f"[Eventbrite] SUCCESS: {len(events)} events via API")

            if not events:
                sv_events, sv_detected = asyncio.run(extract_simpleview_events(html, source_name, url, future_only))
                if sv_detected and sv_events:
                    events = sv_events
                    methods.append(f"Simpleview API ({len(events)})")
                    print(f"[Simpleview] SUCCESS: {len(events)} events via API")

            if not events:
                sw_events, sw_detected = asyncio.run(extract_sitewrench_events(html, source_name, url, future_only))
                if sw_detected and sw_events:
                    events = sw_events
                    methods.append(f"SiteWrench API ({len(events)})")
                    print(f"[SiteWrench] SUCCESS: {len(events)} events via API")

            if not events:
                rd_events, rd_detected = asyncio.run(extract_recdesk_events(html, source_name, url, future_only))
                if rd_detected and rd_events:
                    events = rd_events
                    methods.append(f"RecDesk API ({len(events)})")
                    print(f"[RecDesk] SUCCESS: {len(events)} events via API")

            if not events:
                tl_events, tl_detected = asyncio.run(extract_ticketleap_events(html, source_name, url, future_only))
                if tl_detected and tl_events:
                    events = tl_events
                    methods.append(f"TicketLeap ({len(events)})")
                    print(f"[TicketLeap] SUCCESS: {len(events)} events")

            if not events:
                ln_events, ln_detected = asyncio.run(extract_libnet_events(html, source_name, url, future_only))
                if ln_detected and ln_events:
                    events = ln_events
                    methods.append(f"LibNet API ({len(events)})")
                    print(f"[LibNet] SUCCESS: {len(events)} events via API")

            if not events:
                pb_events, pb_detected = asyncio.run(extract_philbrook_events(html, source_name, url, future_only))
                if pb_detected and pb_events:
                    events = pb_events
                    methods.append(f"Philbrook AJAX ({len(events)})")
                    print(f"[Philbrook] SUCCESS: {len(events)} events via admin-ajax")

            if not events:
                tpac_events, tpac_detected = asyncio.run(extract_tulsapac_events(html, source_name, url, future_only))
                if tpac_detected and tpac_events:
                    events = tpac_events
                    methods.append(f"TulsaPAC API ({len(events)})")
                    print(f"[TulsaPAC] SUCCESS: {len(events)} productions via TM API")

            if not events:
                rd_ev, rd_detected = asyncio.run(extract_roosterdays_events(html, source_name, url, future_only))
                if rd_detected and rd_ev:
                    events = rd_ev
                    methods.append(f"RoosterDays ({len(events)})")
                    print(f"[RoosterDays] SUCCESS: {len(events)} event")

            if not events:
                tbf_ev, tbf_detected = asyncio.run(extract_tulsabrunchfest_events(html, source_name, url, future_only))
                if tbf_detected and tbf_ev:
                    events = tbf_ev
                    methods.append(f"TulsaBrunchFest ({len(events)})")
                    print(f"[TulsaBrunchFest] SUCCESS: {len(events)} event")

            if not events:
                okeq_ev, okeq_detected = asyncio.run(extract_okeq_events(html, source_name, url, future_only))
                if okeq_detected and okeq_ev:
                    events = okeq_ev
                    methods.append(f"OKEQ ({len(events)})")
                    print(f"[OKEQ] SUCCESS: {len(events)} events")

            if not events:
                flywheel_ev, flywheel_detected = asyncio.run(extract_flywheel_events(html, source_name, url, future_only))
                if flywheel_detected and flywheel_ev:
                    events = flywheel_ev
                    methods.append(f"Flywheel ({len(events)})")
                    print(f"[Flywheel] SUCCESS: {len(events)} events")

            if not events:
                arvest_ev, arvest_detected = asyncio.run(extract_arvest_events(html, source_name, url, future_only))
                if arvest_detected and arvest_ev:
                    events = arvest_ev
                    methods.append(f"Arvest ({len(events)})")
                    print(f"[Arvest] SUCCESS: {len(events)} events")

            if not events:
                tt_ev, tt_detected = asyncio.run(extract_tulsatough_events(html, source_name, url, future_only))
                if tt_detected and tt_ev:
                    events = tt_ev
                    methods.append(f"TulsaTough ({len(events)})")
                    print(f"[TulsaTough] SUCCESS: {len(events)} events")

            if not events:
                gradient_ev, gradient_detected = asyncio.run(extract_gradient_events(html, source_name, url, future_only))
                if gradient_detected and gradient_ev:
                    events = gradient_ev
                    methods.append(f"Gradient ({len(events)})")
                    print(f"[Gradient] SUCCESS: {len(events)} events")

            if not events:
                tfm_ev, tfm_detected = asyncio.run(extract_tulsafarmersmarket_events(html, source_name, url, future_only))
                if tfm_detected and tfm_ev:
                    events = tfm_ev
                    methods.append(f"TFM ({len(events)})")
                    print(f"[TFM] SUCCESS: {len(events)} events")

            if not events:
                okcastle_ev, okcastle_detected = asyncio.run(extract_okcastle_events(html, source_name, url, future_only))
                if okcastle_detected and okcastle_ev:
                    events = okcastle_ev
                    methods.append(f"OKCastle ({len(events)})")
                    print(f"[OKCastle] SUCCESS: {len(events)} events")

            if not events:
                ba_ev, ba_detected = asyncio.run(extract_broken_arrow_events(html, source_name, url, future_only))
                if ba_detected and ba_ev:
                    events = ba_ev
                    methods.append(f"BrokenArrow ({len(events)})")
                    print(f"[BrokenArrow] SUCCESS: {len(events)} events")

            if not events:
                zoo_ev, zoo_detected = asyncio.run(extract_tulsazoo_events(html, source_name, url, future_only))
                if zoo_detected and zoo_ev:
                    events = zoo_ev
                    methods.append(f"TulsaZoo ({len(events)})")
                    print(f"[TulsaZoo] SUCCESS: {len(events)} events")

            if not events:
                hr_ev, hr_detected = asyncio.run(extract_hardrock_tulsa_events(html, source_name, url, future_only))
                if hr_detected and hr_ev:
                    events = hr_ev
                    methods.append(f"HardRockTulsa ({len(events)})")
                    print(f"[HardRockTulsa] SUCCESS: {len(events)} events")

            if not events:
                gypsy_ev, gypsy_detected = asyncio.run(extract_gypsy_events(html, source_name, url, future_only))
                if gypsy_detected and gypsy_ev:
                    events = gypsy_ev
                    methods.append(f"Gypsy ({len(events)})")
                    print(f"[Gypsy] SUCCESS: {len(events)} events")

            if not events:
                bar_ev, bar_detected = asyncio.run(extract_badass_renees_events(html, source_name, url, future_only))
                if bar_detected and bar_ev:
                    events = bar_ev
                    methods.append(f"BadAssRenees ({len(events)})")
                    print(f"[BadAssRenees] SUCCESS: {len(events)} events")

            if not events:
                rl_ev, rl_detected = asyncio.run(extract_rocklahoma_events(html, source_name, url, future_only))
                if rl_detected and rl_ev:
                    events = rl_ev
                    methods.append(f"Rocklahoma ({len(events)})")
                    print(f"[Rocklahoma] SUCCESS: {len(events)} events")

            if not events:
                ok_ev, ok_detected = asyncio.run(extract_tulsa_oktoberfest_events(html, source_name, url, future_only))
                if ok_detected and ok_ev:
                    events = ok_ev
                    methods.append(f"TulsaOktoberfest ({len(events)})")
                    print(f"[TulsaOktoberfest] SUCCESS: {len(events)} events")

            if not events:
                events = extract_events_universal(html, url, source_name)

                if events and '_extraction_methods' in events[0]:
                    methods = events[0]['_extraction_methods']
                    for e in events:
                        e.pop('_extraction_methods', None)

            # ── FIX: Apply future date filter to universal extraction results ──
            if future_only and events:
                from dateutil import parser as date_parser
                from datetime import timedelta
                now = datetime.now()
                cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                filtered = []
                for ev in events:
                    date_str = ev.get('date', '') or ev.get('date_start', '') or ev.get('start_time', '')
                    if not date_str:
                        filtered.append(ev)  # Keep events without dates (can't determine)
                        continue
                    try:
                        dt = date_parser.parse(str(date_str), fuzzy=True)
                        # FIX: Strip timezone info to avoid TypeError comparing tz-aware vs naive
                        dt = dt.replace(tzinfo=None)
                        # FIX: Year-bumping - only bump if >270 days in past (likely year wrap)
                        # e.g., "Jan 5" parsed in November should become next year's Jan 5
                        # But "Feb 6" parsed in March should NOT become next year
                        if dt < cutoff:
                            days_past = (cutoff - dt).days
                            if days_past > 270:
                                # Likely a year wrap - bump to next year
                                dt = dt.replace(year=dt.year + 1)
                                ev['date'] = dt.strftime('%b %d, %Y')
                                if dt >= cutoff:
                                    filtered.append(ev)
                            else:
                                # Start is in the past — check end_date before dropping.
                                # Multi-day events (e.g. started Mar 16, ends Mar 22) should
                                # be kept if the end date is still in the future.
                                end_str = ev.get('end_date', '') or ev.get('end_time', '') or ev.get('date_end', '')
                                if end_str:
                                    try:
                                        end_dt = date_parser.parse(str(end_str), fuzzy=True).replace(tzinfo=None)
                                        if end_dt >= cutoff:
                                            filtered.append(ev)
                                            continue
                                    except:
                                        pass
                                # genuinely past with no future end — drop it
                        else:
                            filtered.append(ev)
                    except:
                        filtered.append(ev)  # Can't parse - keep it

                dropped = len(events) - len(filtered)
                if dropped:
                    print(f"[FutureFilter] Found: {len(events)}, Kept: {len(filtered)}, Dropped: {dropped} past events")
                events = filtered

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r'[^\w\-]', '_', source_name)
            filename = f"{safe_name}_{timestamp}.html"
            (OUTPUT_DIR / filename).write_text(html, encoding='utf-8')

            return jsonify({
                "events": events,
                "html_size": len(html),
                "filename": filename,
                "methods": methods
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route('/scrape-all', methods=['POST'])
    def scrape_all():
        """Priority-based async scrape-all via asyncScraper."""
        import queue as _queue
        import threading as _threading
        import asyncScraper

        saved = load_saved_urls()
        if not saved:
            return jsonify({"error": "No saved URLs"}), 400

        q = _queue.Queue()
        def _run():
            # Create a fresh event loop in this thread — required under gevent
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(asyncScraper.scrape_all_prioritized(saved, q))
            finally:
                loop.close()
        _threading.Thread(target=_run, daemon=True).start()

        def generate():
            while True:
                try:
                    item = q.get(timeout=25)
                    if item is None:
                        break
                    yield f"data: {json.dumps(item)}\n\n"
                except Exception:
                    # Queue timed out — send SSE keepalive so proxy stays open
                    yield ": keepalive\n\n"

        return Response(generate(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        })

    @app.route('/cron-scrape', methods=['POST'])
    def cron_scrape():
        """
        Cron-safe scrape endpoint. Returns plain JSON report (not SSE).

        Designed for Railway scheduler service, external cron, or curl.
        Runs sequentially: scrape one venue → normalize → submit → next.

        Auth: X-Cron-Secret header or ?secret= query param matching CRON_SECRET env var.

        Optional priority filter:
          ?priority=1          — only scrape priority 1 (flagship) venues
          ?priority=1,2        — scrape priority 1 and 2
          (omit for all)

        Usage:
          Full scrape:  POST /cron-scrape?secret=XXX
          P1 only:      POST /cron-scrape?secret=XXX&priority=1
          P1+P2:        POST /cron-scrape?secret=XXX&priority=1,2
        """
        import asyncScraper

        saved = load_saved_urls()
        if not saved:
            return jsonify({"error": "No saved URLs", "status": "no_sources"}), 400

        # ── Priority filter ──────────────────────────────────────────────
        priority_param = request.args.get('priority', '')
        if not priority_param and request.is_json:
            priority_param = str(request.json.get('priority', ''))

        if priority_param:
            try:
                allowed = {int(p.strip()) for p in priority_param.split(',')}
            except ValueError:
                return jsonify({"error": f"Invalid priority param: {priority_param}"}), 400

            before_count = len(saved)
            saved = [
                e for e in saved
                if (e.get('priority') or e.get('venue_priority') or 3) in allowed
            ]
            print(f"[CronScrape] Priority filter {allowed}: {before_count} → {len(saved)} sources")

            if not saved:
                return jsonify({
                    "error": f"No sources match priority {priority_param}",
                    "status": "no_sources",
                }), 400

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                summary = loop.run_until_complete(asyncScraper.scrape_all_cron(saved))
            finally:
                loop.close()

            return jsonify({
                "status":           "complete",
                "priority_filter":  priority_param or "all",
                "total_sources":    summary.get('total_sources', 0),
                "sources_scraped":  summary.get('sources_scraped', 0),
                "total_events":     summary.get('total_events', 0),
                "total_saved":      summary.get('total_saved', 0),
                "norm_failures":    summary.get('norm_failures', 0),
                "error_count":      summary.get('error_count', 0),
                "elapsed_seconds":  summary.get('elapsed_seconds', 0),
                "timestamp":        summary.get('timestamp', ''),
                "errors":           summary.get('errors', [])[:10],
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                "status": "error",
                "error":  str(e),
            }), 500

    @app.route('/scrape-source', methods=['POST'])
    def scrape_source():
        """Per-row manual scrape — persists to scrape_status.json."""
        import asyncScraper

        data = request.json or {}
        url  = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'url required'}), 400

        saved = load_saved_urls()
        entry = next((e for e in saved if e.get('url') == url), None)
        if not entry:
            entry = {
                'url':            url,
                'name':           data.get('name', resolve_source_name(url, '')),
                'use_playwright': data.get('use_playwright', True),
                'priority':       data.get('priority'),
                'venue_priority': data.get('venue_priority'),
            }

        try:
            result = asyncio.run(asyncScraper.scrape_one_standalone(entry))
            return jsonify({
                'url':          result['url'],
                'name':         result['name'],
                'status':       result['status'],
                'event_count':  result['event_count'],
                'methods':      result['methods'],
                'last_scraped': result['last_scraped'],
                'db_saved':     result['db_saved'],
                'error':        result['error'],
                'error_report': result['error_report'],
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/scrape-status', methods=['GET'])
    def scrape_status():
        """Return scrape_status.json directly — no heavy imports."""
        import json as _json
        status_file = OUTPUT_DIR / "scrape_status.json"
        try:
            data = _json.loads(status_file.read_text()) if status_file.exists() else {}
        except Exception:
            data = {}
        return jsonify(data)

    # ── old sequential generate() was here — replaced by asyncScraper ──

    def _dead_generate():
        total = len(saved)
        yield f"data: {json.dumps({'type': 'start', 'total_sources': total})}\n\n"

        total_events = 0
        total_saved = 0
        sources_scraped = 0

        for i, entry in enumerate(saved):
            url = entry.get('url', '')
            name = entry.get('name', 'unknown')
            use_pw = entry.get('use_playwright', True)

            # Resolve canonical venue name from URL
            name = resolve_source_name(url, name)

            yield f"data: {json.dumps({'type': 'source_start', 'name': name, 'index': i})}\n\n"

            try:
                # Check robots.txt
                robots_result = check_robots_txt(url)
                if not robots_result['allowed']:
                    yield f"data: {json.dumps({'type': 'source_error', 'name': name, 'index': i, 'error': f'Blocked by robots.txt'})}\n\n"
                    continue

                # Fetch
                if use_pw:
                    html = asyncio.run(fetch_with_playwright(url))
                else:
                    html = asyncio.run(fetch_with_httpx(url))

                # Extract - same chain as /scrape
                methods = []
                events = []

                eca_events, eca_detected = asyncio.run(extract_eventcalendarapp(html, name, url, True))
                if eca_detected and eca_events:
                    events = eca_events
                    methods.append(f"EventCalendarApp API ({len(events)})")

                if not events:
                    timely_events, timely_detected = asyncio.run(extract_timely(html, name, url, True))
                    if timely_detected and timely_events:
                        events = timely_events
                        methods.append(f"Timely API ({len(events)})")

                if not events:
                    bok_events, bok_detected = asyncio.run(extract_bok_center(html, name, url, True))
                    if bok_detected and bok_events:
                        events = bok_events
                        methods.append(f"BOK Center API ({len(events)})")

                if not events:
                    cc_events, cc_detected = asyncio.run(extract_circle_cinema_events(html, name, url, True))
                    if cc_detected and cc_events:
                        events = cc_events
                        methods.append(f"Circle Cinema ({len(events)})")

                if not events:
                    expo_events, expo_detected = asyncio.run(extract_expo_square_events(html, name, url, True))
                    if expo_detected and expo_events:
                        events = expo_events
                        methods.append(f"Expo Square API ({len(events)})")

                if not events:
                    eb_events, eb_detected = asyncio.run(extract_eventbrite_api_events(html, name, url, True))
                    if eb_detected and eb_events:
                        events = eb_events
                        methods.append(f"Eventbrite API ({len(events)})")

                if not events:
                    sv_events, sv_detected = asyncio.run(extract_simpleview_events(html, name, url, True))
                    if sv_detected and sv_events:
                        events = sv_events
                        methods.append(f"Simpleview API ({len(events)})")

                if not events:
                    sw_events, sw_detected = asyncio.run(extract_sitewrench_events(html, name, url, True))
                    if sw_detected and sw_events:
                        events = sw_events
                        methods.append(f"SiteWrench API ({len(events)})")

                if not events:
                    rd_events, rd_detected = asyncio.run(extract_recdesk_events(html, name, url, True))
                    if rd_detected and rd_events:
                        events = rd_events
                        methods.append(f"RecDesk API ({len(events)})")

                if not events:
                    tl_events, tl_detected = asyncio.run(extract_ticketleap_events(html, name, url, True))
                    if tl_detected and tl_events:
                        events = tl_events
                        methods.append(f"TicketLeap ({len(events)})")

                if not events:
                    ln_events, ln_detected = asyncio.run(extract_libnet_events(html, name, url, True))
                    if ln_detected and ln_events:
                        events = ln_events
                        methods.append(f"LibNet API ({len(events)})")
                        print(f"[LibNet] SUCCESS: {len(events)} events via API")

                if not events:
                    pb_events, pb_detected = asyncio.run(extract_philbrook_events(html, name, url, True))
                    if pb_detected and pb_events:
                        events = pb_events
                        methods.append(f"Philbrook AJAX ({len(events)})")
                        print(f"[Philbrook] SUCCESS: {len(events)} events via admin-ajax")

                if not events:
                    tpac_events, tpac_detected = asyncio.run(extract_tulsapac_events(html, name, url, True))
                    if tpac_detected and tpac_events:
                        events = tpac_events
                        methods.append(f"TulsaPAC API ({len(events)})")
                        print(f"[TulsaPAC] SUCCESS: {len(events)} productions via TM API")

                if not events:
                    rd_ev, rd_detected = asyncio.run(extract_roosterdays_events(html, name, url, True))
                    if rd_detected and rd_ev:
                        events = rd_ev
                        methods.append(f"RoosterDays ({len(events)})")
                        print(f"[RoosterDays] SUCCESS: {len(events)} event")

                if not events:
                    tbf_ev, tbf_detected = asyncio.run(extract_tulsabrunchfest_events(html, name, url, True))
                    if tbf_detected and tbf_ev:
                        events = tbf_ev
                        methods.append(f"TulsaBrunchFest ({len(events)})")
                        print(f"[TulsaBrunchFest] SUCCESS: {len(events)} event")

                if not events:
                    okeq_ev, okeq_detected = asyncio.run(extract_okeq_events(html, name, url, True))
                    if okeq_detected and okeq_ev:
                        events = okeq_ev
                        methods.append(f"OKEQ ({len(events)})")
                        print(f"[OKEQ] SUCCESS: {len(events)} events")

                if not events:
                    flywheel_ev, flywheel_detected = asyncio.run(extract_flywheel_events(html, name, url, True))
                    if flywheel_detected and flywheel_ev:
                        events = flywheel_ev
                        methods.append(f"Flywheel ({len(events)})")
                        print(f"[Flywheel] SUCCESS: {len(events)} events")

                if not events:
                    arvest_ev, arvest_detected = asyncio.run(extract_arvest_events(html, name, url, True))
                    if arvest_detected and arvest_ev:
                        events = arvest_ev
                        methods.append(f"Arvest ({len(events)})")
                        print(f"[Arvest] SUCCESS: {len(events)} events")

                if not events:
                    tt_ev, tt_detected = asyncio.run(extract_tulsatough_events(html, name, url, True))
                    if tt_detected and tt_ev:
                        events = tt_ev
                        methods.append(f"TulsaTough ({len(events)})")
                        print(f"[TulsaTough] SUCCESS: {len(events)} events")

                if not events:
                    gradient_ev, gradient_detected = asyncio.run(extract_gradient_events(html, name, url, True))
                    if gradient_detected and gradient_ev:
                        events = gradient_ev
                        methods.append(f"Gradient ({len(events)})")
                        print(f"[Gradient] SUCCESS: {len(events)} events")

                if not events:
                    tfm_ev, tfm_detected = asyncio.run(extract_tulsafarmersmarket_events(html, name, url, True))
                    if tfm_detected and tfm_ev:
                        events = tfm_ev
                        methods.append(f"TFM ({len(events)})")
                        print(f"[TFM] SUCCESS: {len(events)} events")

                if not events:
                    okcastle_ev, okcastle_detected = asyncio.run(extract_okcastle_events(html, name, url, True))
                    if okcastle_detected and okcastle_ev:
                        events = okcastle_ev
                        methods.append(f"OKCastle ({len(events)})")
                        print(f"[OKCastle] SUCCESS: {len(events)} events")

                if not events:
                    ba_ev, ba_detected = asyncio.run(extract_broken_arrow_events(html, name, url, True))
                    if ba_detected and ba_ev:
                        events = ba_ev
                        methods.append(f"BrokenArrow ({len(events)})")
                        print(f"[BrokenArrow] SUCCESS: {len(events)} events")

                if not events:
                    zoo_ev, zoo_detected = asyncio.run(extract_tulsazoo_events(html, name, url, True))
                    if zoo_detected and zoo_ev:
                        events = zoo_ev
                        methods.append(f"TulsaZoo ({len(events)})")
                        print(f"[TulsaZoo] SUCCESS: {len(events)} events")

                if not events:
                    hr_ev, hr_detected = asyncio.run(extract_hardrock_tulsa_events(html, name, url, True))
                    if hr_detected and hr_ev:
                        events = hr_ev
                        methods.append(f"HardRockTulsa ({len(events)})")
                        print(f"[HardRockTulsa] SUCCESS: {len(events)} events")

                if not events:
                    gypsy_ev, gypsy_detected = asyncio.run(extract_gypsy_events(html, name, url, True))
                    if gypsy_detected and gypsy_ev:
                        events = gypsy_ev
                        methods.append(f"Gypsy ({len(events)})")
                        print(f"[Gypsy] SUCCESS: {len(events)} events")

                if not events:
                    bar_ev, bar_detected = asyncio.run(extract_badass_renees_events(html, name, url, True))
                    if bar_detected and bar_ev:
                        events = bar_ev
                        methods.append(f"BadAssRenees ({len(events)})")
                        print(f"[BadAssRenees] SUCCESS: {len(events)} events")

                if not events:
                    rl_ev, rl_detected = asyncio.run(extract_rocklahoma_events(html, name, url, True))
                    if rl_detected and rl_ev:
                        events = rl_ev
                        methods.append(f"Rocklahoma ({len(events)})")
                        print(f"[Rocklahoma] SUCCESS: {len(events)} events")

                if not events:
                    ok_ev, ok_detected = asyncio.run(extract_tulsa_oktoberfest_events(html, name, url, True))
                    if ok_detected and ok_ev:
                        events = ok_ev
                        methods.append(f"TulsaOktoberfest ({len(events)})")
                        print(f"[TulsaOktoberfest] SUCCESS: {len(events)} events")

                if not events:
                    events = extract_events_universal(html, url, name)
                    if events and '_extraction_methods' in events[0]:
                        methods = events[0]['_extraction_methods']
                        for e in events:
                            e.pop('_extraction_methods', None)

                # Future filter
                if events:
                    from dateutil import parser as date_parser
                    now = datetime.now()
                    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    filtered = []
                    for ev in events:
                        date_str = ev.get('date', '') or ev.get('date_start', '') or ev.get('start_time', '')
                        if not date_str:
                            filtered.append(ev)
                            continue
                        try:
                            dt = date_parser.parse(str(date_str), fuzzy=True)
                            dt = dt.replace(tzinfo=None)
                            if dt < cutoff:
                                days_past = (cutoff - dt).days
                                if days_past > 270:
                                    dt = dt.replace(year=dt.year + 1)
                                    ev['date'] = dt.strftime('%b %d, %Y')
                                    if dt >= cutoff:
                                        filtered.append(ev)
                            else:
                                filtered.append(ev)
                        except:
                            filtered.append(ev)
                    events = filtered

                yield f"data: {json.dumps({'type': 'source_scraped', 'name': name, 'index': i, 'count': len(events), 'methods': methods})}\n\n"

                # Save JSON to disk (backup)
                saved_count = 0
                if events:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = re.sub(r'[^\w\-]', '_', name)
                    filename = f"{safe_name}_{timestamp}.json"
                    (OUTPUT_DIR / filename).write_text(json.dumps(events, indent=2), encoding='utf-8')

                    # --- Normalize via LLM service then POST to backend ---
                    normalized = normalize_batch(events, source_url=url, source_name=name)
                    events_to_post = normalized if normalized else events

                    db_saved = 0
                    for ev in events_to_post:
                        try:
                            transformed = transform_event_for_backend(ev, source_priority=source.get('priority'))
                            # Ensure source fields are set
                            if not transformed.get('source_url'):
                                transformed['source_url'] = url
                            if not transformed.get('source_name'):
                                transformed['source_name'] = name
                            resp = httpx.post(f"{BACKEND_URL}/api/events", json=transformed, timeout=5)
                            if resp.status_code in [200, 201]:
                                db_saved += 1
                            else:
                                print(f"[ScrapeAll DB] Rejected: {resp.status_code} - {resp.text[:100]}")
                        except Exception as db_err:
                            print(f"[ScrapeAll DB] Error: {db_err}")

                    saved_count = db_saved
                    norm_tag = "normalized" if normalized else "fallback"
                    print(f"[ScrapeAll DB] {name}: {db_saved}/{len(events_to_post)} saved ({norm_tag})")

                total_events += len(events)
                total_saved += saved_count
                sources_scraped += 1

                yield f"data: {json.dumps({'type': 'source_done', 'name': name, 'index': i, 'saved': saved_count, 'count': len(events)})}\n\n"

                print(f"[ScrapeAll] {i+1}/{total} {name}: {len(events)} events {methods}")

            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'source_error', 'name': name, 'index': i, 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'total_events': total_events, 'total_saved': total_saved, 'sources_scraped': sources_scraped, 'total_sources': total})}\n\n"


    @app.route('/save', methods=['POST'])
    def save():
        data = request.json
        events = data.get('events', [])
        source = data.get('source', 'unknown')

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-]', '_', source)
        filename = f"{safe_name}_{timestamp}.json"

        (OUTPUT_DIR / filename).write_text(json.dumps(events, indent=2), encoding='utf-8')

        return jsonify({"filename": filename, "count": len(events)})

    @app.route('/to-database', methods=['POST'])
    def to_database():
        """
        Send events to database via Rust backend.

        Pipeline:
          1. Normalize all events through Gemini (LLM service on :8001)
          2. Transform normalized events to backend schema
          3. POST each event to Rust backend on :3000
          4. Falls back to basic transform if LLM service is unavailable
        """
        import concurrent.futures

        data = request.json
        events = data.get('events', [])

        if not events:
            return jsonify({"saved": 0, "total": 0})

        print(f"[DB] Processing {len(events)} events...")

        # --- Step 1: Normalize through Gemini FIRST ---
        # This must happen before venue registration so we register
        # canonical names ("The Shrine") not raw names ("shrine").
        source_url = events[0].get('source_url', '') if events else ''
        source_name = events[0].get('source', '') or events[0].get('source_name', '') if events else ''

        normalized_events = normalize_batch(events, source_url, source_name)

        use_normalized = len(normalized_events) > 0
        if use_normalized:
            print(f"[DB] ✓ Normalized {len(events)} → {len(normalized_events)} events via Gemini")
            events_to_save = normalized_events
        else:
            print(f"[DB] ⚠ Normalization unavailable, using basic transform fallback")
            events_to_save = events

        # --- Step 2: Collect, register, and auto-enrich venues ---
        # Uses normalized events so venue names are canonical.
        venues_to_save = {}
        for event in events_to_save:
            venue_name = event.get('venue', '').strip()
            if venue_name and venue_name.lower() not in ['tba', 'tbd', 'online', 'online event', 'virtual', '']:
                venue_key = venue_name.lower()
                if venue_key not in venues_to_save:
                    venues_to_save[venue_key] = {
                        'name': venue_name,
                        'address': event.get('venue_address', ''),
                        'city': 'Tulsa',
                        '_venue_website': event.get('_venue_website', ''),
                    }
                elif not venues_to_save[venue_key].get('_venue_website') and event.get('_venue_website'):
                    venues_to_save[venue_key]['_venue_website'] = event.get('_venue_website')

        # Register and auto-enrich venues via Google Places
        venues_with_websites = 0
        venues_enriched = 0
        if venues_to_save:
            print(f"[DB] Registering {len(venues_to_save)} venues...")
            for venue_key, venue_data in venues_to_save.items():
                website = venue_data.pop('_venue_website', '')
                venue_payload = {
                    'name': venue_data['name'],
                    'address': venue_data.get('address', '') or None,
                    'city': venue_data.get('city', 'Tulsa'),
                    'website': website or None,
                }

                if website:
                    venues_with_websites += 1

                # POST to backend (creates or returns existing)
                try:
                    resp = httpx.post(f"{BACKEND_URL}/api/venues", json=venue_payload, timeout=5)
                    if resp.status_code in [200, 201]:
                        existing = resp.json()
                        # Check if venue is missing data we can fill via Google Places
                        missing_address = not existing.get('address')
                        missing_website = not existing.get('website')
                        missing_coords = existing.get('latitude') is None

                        if (missing_address or missing_website or missing_coords) and GOOGLE_PLACES_API_KEY:
                            try:
                                result = asyncio.run(lookup_venue_google_places(venue_data['name'], 'Tulsa, OK'))
                                if 'error' not in result:
                                    patch_data = {}
                                    if missing_address and result.get('address'):
                                        patch_data['address'] = result['address']
                                    if missing_website and result.get('website'):
                                        patch_data['website'] = result['website']
                                    if missing_coords and result.get('latitude') and result.get('longitude'):
                                        patch_data['latitude'] = result['latitude']
                                        patch_data['longitude'] = result['longitude']

                                    if patch_data:
                                        venue_id = existing.get('id')
                                        httpx.patch(
                                            f"{BACKEND_URL}/api/venues/{venue_id}",
                                            json=patch_data,
                                            timeout=5
                                        )
                                        venues_enriched += 1
                                        print(f"[DB] Enriched '{venue_data['name']}': {', '.join(patch_data.keys())}")
                            except Exception as e:
                                print(f"[DB] Enrichment failed for '{venue_data['name']}': {e}")
                except Exception:
                    pass

            print(f"[DB] Venues: {len(venues_to_save)} registered, {venues_with_websites} with websites, {venues_enriched} enriched via Google")

        # --- Step 3: Transform and send to Rust backend ---
        def post_event(event):
            try:
                transformed = transform_event_for_backend(event)
                resp = httpx.post(f"{BACKEND_URL}/api/events", json=transformed, timeout=5)
                if resp.status_code not in [200, 201]:
                    print(f"[DB] Rejected: {resp.status_code} - {resp.text[:100]}")
                return resp.status_code in [200, 201]
            except Exception as e:
                print(f"[DB] Error: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(post_event, events_to_save))

        saved = sum(results)
        print(f"[DB] Complete: {saved}/{len(events_to_save)} saved (normalized: {use_normalized})")

        return jsonify({
            "saved": saved,
            "total": len(events_to_save),
            "normalized": use_normalized,
            "venues_registered": len(venues_to_save),
            "venues_with_websites": venues_with_websites,
            "venues_enriched": venues_enriched
        })

    @app.route('/upload-all-to-database', methods=['POST'])
    def upload_all_to_database():
        """Read all saved JSON files and send events to database concurrently."""
        import concurrent.futures

        total_events = 0
        total_saved = 0
        files_processed = 0
        errors = []

        json_files = sorted(OUTPUT_DIR.glob("*.json"), reverse=True)
        skip_files = {'venues.json', 'saved_urls.json'}

        all_events = []
        for f in json_files:
            if f.name in skip_files:
                continue
            try:
                file_events = json.loads(f.read_text())
                if isinstance(file_events, list) and len(file_events) > 0:
                    files_processed += 1
                    all_events.extend(file_events)
            except Exception as e:
                errors.append(f"{f.name}: {str(e)}")

        total_events = len(all_events)
        print(f"[Upload] {total_events} events from {files_processed} files")

        # Normalize through Gemini before sending to database
        source_url = all_events[0].get('source_url', '') if all_events else ''
        source_name = all_events[0].get('source', '') or all_events[0].get('source_name', '') if all_events else ''
        normalized = normalize_batch(all_events, source_url, source_name)

        use_normalized = len(normalized) > 0
        if use_normalized:
            print(f"[Upload] ✓ Normalized {total_events} → {len(normalized)} events via Gemini")
            events_to_post = normalized
        else:
            print(f"[Upload] ⚠ Normalization unavailable, using basic transform fallback")
            events_to_post = all_events

        def post_event(event):
            try:
                transformed = transform_event_for_backend(event)
                resp = httpx.post(f"{BACKEND_URL}/api/events", json=transformed, timeout=5)
                return resp.status_code in [200, 201]
            except Exception as e:
                print(f"[Upload] Error: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(post_event, events_to_post))

        total_saved = sum(results)
        print(f"[Upload] Complete: {total_saved}/{len(events_to_post)} saved (normalized: {use_normalized})")

        return jsonify({
            "files_processed": files_processed,
            "total_events": total_events,
            "saved": total_saved,
            "normalized": use_normalized,
            "errors": errors
        })

    @app.route('/clear-files', methods=['POST'])
    def clear_files():
        """Delete all saved JSON files."""
        deleted = 0
        for f in OUTPUT_DIR.glob("*.json"):
            if f.name == 'venues.json':
                continue
            try:
                f.unlink()
                deleted += 1
            except:
                pass

        for f in OUTPUT_DIR.glob("*.html"):
            try:
                f.unlink()
                deleted += 1
            except:
                pass

        return jsonify({"deleted": deleted})

    @app.route('/files')
    def list_files():
        files = []
        for f in sorted(OUTPUT_DIR.glob("*.json"), reverse=True):
            if f.name != 'saved_urls.json':
                files.append({"name": f.name, "size": f.stat().st_size})
        return jsonify(files)

    @app.route('/download/<filename>')
    def download(filename):
        path = OUTPUT_DIR / filename
        if path.exists():
            return send_file(path, as_attachment=True)
        return jsonify({"error": "Not found"}), 404

    @app.route('/venues-missing-urls')
    def venues_missing_urls():
        """Fetch venues from backend that are missing website URLs."""
        try:
            resp = httpx.get(f"{BACKEND_URL}/api/venues/missing", timeout=10)
            if resp.status_code == 200:
                venues = resp.json()
                names = [v.get('name', '') for v in venues if v.get('name')]
                return jsonify({
                    "count": len(names),
                    "venues": names
                })
            else:
                return jsonify({"error": f"Backend returned {resp.status_code}"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ============================================================================
    # VENUE PRIORITY ADMIN
    # ============================================================================

    @app.route('/venue-priority')
    def venue_priority_page():
        """Admin panel for manually setting venue display priority."""
        return render_template_string(VENUE_PRIORITY_HTML)

    @app.route('/api/venues/all', methods=['GET'])
    def get_all_venues_for_admin():
        """Return all venues with their current priority for the admin panel."""
        try:
            resp = httpx.get(f"{BACKEND_URL}/api/venues?limit=1000", timeout=15)
            if resp.status_code != 200:
                return jsonify({"error": f"Backend returned {resp.status_code}"}), 500
            venues = resp.json()
            # Sort: unset (null/3) first so the ones needing attention are on top,
            # then by name within each tier.
            venues.sort(key=lambda v: (v.get('venue_priority') or 3, v.get('name', '').lower()))
            return jsonify(venues)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/venues/set-priority', methods=['POST'])
    def set_venue_priority():
        """Update a single venue's display priority via the Rust backend PATCH endpoint."""
        data = request.json
        venue_id = data.get('id')
        priority = data.get('venue_priority')

        if not venue_id or priority is None:
            return jsonify({"error": "id and venue_priority required"}), 400
        if priority not in (1, 2, 3):
            return jsonify({"error": "venue_priority must be 1, 2, or 3"}), 400

        try:
            resp = httpx.patch(
                f"{BACKEND_URL}/api/venues/{venue_id}",
                json={"venue_priority": priority},
                timeout=10,
            )
            if resp.status_code == 200:
                return jsonify({"ok": True, "venue": resp.json()})
            else:
                return jsonify({"error": f"Backend returned {resp.status_code}: {resp.text}"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ============================================================================
    # VENUE MANAGER API
    # ============================================================================

    @app.route('/api/venues/incomplete', methods=['GET'])
    def get_incomplete_venues():
        """Fetch venues that are missing key data fields."""
        try:
            resp = httpx.get(f"{BACKEND_URL}/api/venues", timeout=10)
            venues = resp.json() if resp.status_code == 200 else []

            incomplete = []
            for v in venues:
                missing = []
                if not v.get('address'):
                    missing.append('address')
                if not v.get('capacity'):
                    missing.append('capacity')
                if not v.get('venue_type'):
                    missing.append('type')
                if not v.get('parking_info'):
                    missing.append('parking')
                if not v.get('website'):
                    missing.append('website')

                if missing:
                    incomplete.append({
                        'id': v.get('id'),
                        'name': v.get('name'),
                        'address': v.get('address', ''),
                        'website': v.get('website', ''),
                        'missing': missing,
                        'missing_count': len(missing),
                    })

            incomplete.sort(key=lambda x: -x['missing_count'])

            return jsonify({
                'total': len(venues),
                'incomplete': len(incomplete),
                'venues': incomplete
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/venues/lookup', methods=['POST'])
    def lookup_venue():
        """Look up venue details from Google Places API."""
        data = request.json
        venue_name = data.get('name', '')
        city = data.get('city', 'Tulsa, OK')

        if not venue_name:
            return jsonify({'error': 'Venue name required'}), 400

        if not GOOGLE_PLACES_API_KEY:
            return jsonify({'error': 'Google Places API key not configured. Add GOOGLE_PLACES_API_KEY to .env'}), 500

        try:
            result = asyncio.run(lookup_venue_google_places(venue_name, city))

            if result.get('types'):
                result['inferred_type'] = infer_venue_type_from_google(result['types'], venue_name)

            return jsonify(result)

        except Exception as e:
            return jsonify({'error': str(e)}), 500