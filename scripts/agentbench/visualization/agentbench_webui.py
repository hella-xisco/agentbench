#!/usr/bin/env python3
from __future__ import annotations

import argparse
import atexit
import json
import shlex
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from pathlib import Path

from datasets import Dataset, load_dataset

from agentbench.benchmarks.agentbench import AgentbenchInstance, filter_instances
from agentbench.environments import get_environment
from agentbench.planners.human_planner import HumanPlanner


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agentbench Instance Explorer</title>
  <style>
    :root {
      --ink: #201e1b;
      --ink-muted: #5b5852;
      --paper: #f4f0e6;
      --paper-2: #fff8eb;
      --accent: #d6672b;
      --accent-2: #2a6a74;
      --accent-3: #ad3d2c;
      --card: rgba(255, 255, 255, 0.86);
      --border: rgba(32, 30, 27, 0.15);
      --shadow: rgba(32, 30, 27, 0.12);
      --code-bg: #151412;
      --code-ink: #f3efe6;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: "Palatino Linotype", "Palatino", "Book Antiqua", serif;
      background:
        radial-gradient(circle at 10% 10%, #f1d7b2 0%, transparent 45%),
        radial-gradient(circle at 90% 20%, #cbe7e2 0%, transparent 40%),
        linear-gradient(120deg, #f6efe4 0%, #efe5d6 50%, #f7efe0 100%);
      min-height: 100vh;
    }

    header {
      padding: 28px 32px 16px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 16px;
      border-bottom: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.7);
      backdrop-filter: blur(8px);
    }

    header h1 {
      margin: 0;
      font-size: 28px;
      letter-spacing: 0.5px;
    }

    header .meta {
      color: var(--ink-muted);
      font-size: 14px;
    }

    main {
      padding: 24px 32px 36px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 20px;
    }

    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 10px 30px var(--shadow);
      padding: 18px 20px;
      animation: rise 0.6s ease both;
    }

    .card h2 {
      margin: 0 0 12px;
      font-size: 18px;
      text-transform: uppercase;
      letter-spacing: 1.2px;
      color: var(--accent-2);
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }

    select, button, input, textarea {
      font-family: "Palatino Linotype", "Palatino", "Book Antiqua", serif;
      font-size: 14px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #fff;
      color: var(--ink);
    }

    button {
      background: var(--accent);
      color: #fff;
      border: none;
      cursor: pointer;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    button.secondary {
      background: var(--accent-2);
    }

    button.ghost {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--border);
    }

    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }

    button:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
    }

    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .tab {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 16px;
      cursor: pointer;
      transition: background 0.2s ease, color 0.2s ease, transform 0.15s ease;
    }

    .tab.active {
      background: var(--accent-2);
      color: #fff;
      border-color: transparent;
    }

    .tab-panel {
      display: none;
    }

    .tab-panel.active {
      display: block;
    }

    .code {
      font-family: "JetBrains Mono", "Fira Mono", "Menlo", "Consolas", "Courier New", monospace;
      background: var(--code-bg);
      color: var(--code-ink);
      padding: 12px;
      border-radius: 10px;
      white-space: pre-wrap;
      overflow-x: auto;
      font-size: 13px;
      line-height: 1.5;
    }

    .problem-input {
      width: 100%;
      min-height: 220px;
      resize: vertical;
      white-space: pre-wrap;
      font-size: 15px;
      line-height: 1.6;
    }

    .file-list details {
      border: 1px dashed var(--border);
      border-radius: 10px;
      padding: 10px;
      margin-bottom: 10px;
      background: rgba(255, 255, 255, 0.6);
    }

    .file-list summary {
      font-weight: bold;
      cursor: pointer;
      color: var(--accent-3);
    }

    .test-file-input {
      width: 100%;
      min-height: 220px;
      resize: vertical;
      font-family: "JetBrains Mono", "Fira Mono", "Menlo", "Consolas", "Courier New", monospace;
      background: var(--code-bg);
      color: var(--code-ink);
      padding: 12px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }

    .patch-input {
      width: 100%;
      min-height: 160px;
      resize: vertical;
      font-family: "JetBrains Mono", "Fira Mono", "Menlo", "Consolas", "Courier New", monospace;
      background: var(--code-bg);
      color: var(--code-ink);
      padding: 12px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }

    .actions {
      display: grid;
      gap: 10px;
    }

    .actions .row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    .actions .row input[type="text"] {
      flex: 1;
      min-width: 220px;
    }

    .log {
      height: 220px;
      overflow: auto;
    }

    .status {
      font-size: 12px;
      color: var(--ink-muted);
    }

    .shell-output {
      height: 200px;
      overflow: auto;
      margin-top: 8px;
    }

    @keyframes rise {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 960px) {
      main {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Agentbench Instance Explorer</h1>
      <div class="meta" id="datasetMeta">Loading dataset...</div>
    </div>
  </header>

  <main>
    <div class="tabs">
      <button class="tab active" data-tab="instanceTab">Instance</button>
      <button class="tab" data-tab="dockerTab">Docker Actions</button>
    </div>

    <section class="card tab-panel active" id="instanceTab">
      <h2>Instance</h2>
      <div class="controls">
        <button class="ghost" id="prevBtn">Prev</button>
        <select id="instanceSelect"></select>
        <button class="ghost" id="nextBtn">Next</button>
      </div>
      <div class="status" id="instanceStatus"></div>
      <h2>Problem Description</h2>
      <div class="controls">
        <button class="secondary" id="saveStatementBtn">Save Statement</button>
        <button class="ghost" id="resetStatementBtn">Reset</button>
        <div class="status" id="statementStatus">Saved</div>
      </div>
      <textarea class="problem-input" id="problemInput" placeholder="Edit the problem statement..."></textarea>
      <h2>Test Files</h2>
      <div class="controls">
        <button class="secondary" id="saveTestsBtn">Save Test Files</button>
        <button class="ghost" id="resetTestsBtn">Reset</button>
        <div class="status" id="testsStatus">Saved</div>
      </div>
      <div class="file-list" id="testFiles"></div>
      <h2>PR Patch</h2>
      <pre class="code" id="prPatch"></pre>
    </section>

    <section class="card actions tab-panel" id="dockerTab">
      <h2>Docker Actions</h2>
      <div class="row">
        <label><input type="checkbox" id="setupRepo" checked> setup repo</label>
        <label><input type="checkbox" id="cleanGit" checked> clean git history</label>
      </div>
      <div class="row">
        <button id="startBtn">Start Docker</button>
        <button class="secondary" id="removeDocsBtn">Remove Docs</button>
        <button class="secondary" id="setupTestsBtn">Setup Tests</button>
        <button class="secondary" id="applyPatchBtn">Apply PR Patch</button>
        <button class="secondary" id="fetchPlanBtn">Fetch Plan</button>
        <button class="secondary" id="runRepoTestsBtn">Run Repo Tests</button>
        <button class="secondary" id="runPrTestsBtn">Run PR Tests</button>
        <button class="ghost" id="stopBtn">Stop Docker</button>
      </div>
      <div class="status" id="envStatus">Environment: not started</div>
      <div class="status" id="actionStatus">Idle</div>
      <pre class="code log" id="actionLog"></pre>

      <h2>Custom Patch</h2>
      <textarea class="patch-input" id="customPatchInput" placeholder="Paste a git patch to apply..."></textarea>
      <div class="row">
        <button class="secondary" id="applyCustomPatchBtn">Apply Custom Patch</button>
      </div>

      <h2>Write File</h2>
      <div class="row">
        <input type="text" id="writeFilePath" placeholder="File path in container">
      </div>
      <textarea class="patch-input" id="writeFileContent" placeholder="File contents..."></textarea>
      <div class="row">
        <button class="secondary" id="writeFileBtn">Write File</button>
      </div>
      <div class="status" id="writeFileStatus">Ready</div>

      <h2>Shell</h2>
      <div class="row">
        <input type="text" id="shellInput" placeholder="Command to run in container">
        <button id="shellRunBtn">Run</button>
      </div>
      <pre class="code shell-output" id="shellOutput"></pre>

      <h2>Dataset Upload</h2>
      <div class="row">
        <input type="text" id="uploadDataset" placeholder="Dataset id (owner/name)">
        <button class="secondary" id="uploadBtn">Upload Dataset</button>
      </div>
      <div class="status" id="uploadStatus">Not uploaded</div>
    </section>
  </main>

  <script>
    const state = {
      ids: [],
      currentId: null,
      envInstanceId: null,
      dataset: null,
      split: null,
      filter: null,
      slice: null,
      shuffle: null,
      busy: false,
      originalStatement: "",
      originalTestFiles: [],
    };

    const actionButtons = [
      "startBtn",
      "removeDocsBtn",
      "setupTestsBtn",
      "applyPatchBtn",
      "applyCustomPatchBtn",
      "writeFileBtn",
      "fetchPlanBtn",
      "runRepoTestsBtn",
      "runPrTestsBtn",
      "stopBtn",
      "shellRunBtn",
      "saveStatementBtn",
      "resetStatementBtn",
      "saveTestsBtn",
      "resetTestsBtn",
      "uploadBtn",
    ];

    function setText(id, text) {
      document.getElementById(id).textContent = text || "";
    }

    function setBusy(busy, message) {
      state.busy = busy;
      actionButtons.forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
          el.disabled = busy;
        }
      });
      const select = document.getElementById("instanceSelect");
      if (select) {
        select.disabled = busy;
      }
      const problemInput = document.getElementById("problemInput");
      if (problemInput) {
        problemInput.disabled = busy;
      }
      const testsInputs = document.querySelectorAll(".test-file-input");
      testsInputs.forEach((input) => {
        input.disabled = busy;
      });
      const uploadDataset = document.getElementById("uploadDataset");
      if (uploadDataset) {
        uploadDataset.disabled = busy;
      }
      const shellInput = document.getElementById("shellInput");
      if (shellInput) {
        shellInput.disabled = busy;
      }
      const writeFilePath = document.getElementById("writeFilePath");
      if (writeFilePath) {
        writeFilePath.disabled = busy;
      }
      const writeFileContent = document.getElementById("writeFileContent");
      if (writeFileContent) {
        writeFileContent.disabled = busy;
      }
      const customPatchInput = document.getElementById("customPatchInput");
      if (customPatchInput) {
        customPatchInput.disabled = busy;
      }
      if (message) {
        setText("actionStatus", message);
      } else if (!busy) {
        setText("actionStatus", "Idle");
      }
      updateNav();
    }

    function activateTab(tabId) {
      document.querySelectorAll(".tab").forEach((btn) => {
        const isActive = btn.dataset.tab === tabId;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === tabId);
      });
    }

    function appendLog(targetId, text) {
      if (!text) {
        return;
      }
      const el = document.getElementById(targetId);
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
      el.textContent += text;
      if (atBottom) {
        el.scrollTop = el.scrollHeight;
      }
    }

    async function apiGet(path) {
      const res = await fetch(path);
      if (!res.ok) {
        throw new Error("Request failed: " + res.status);
      }
      return await res.json();
    }

    async function apiPost(path, body) {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {})
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || ("Request failed: " + res.status));
      }
      return await res.json();
    }

    function renderInstance(data) {
      state.currentId = data.instance_id;
      setText("instanceStatus", "Instance: " + data.instance_id + " | Repo: " + data.repo);
      const problemInput = document.getElementById("problemInput");
      problemInput.value = data.problem_description || "";
      state.originalStatement = problemInput.value;
      setText("statementStatus", "Saved");
      setText("prPatch", data.pr_patch || "");

      state.originalTestFiles = (data.test_files || []).map((file) => ({
        name: file.name,
        content: file.content || "",
      }));
      setText("testsStatus", "Saved");

      const list = document.getElementById("testFiles");
      list.innerHTML = "";
      state.originalTestFiles.forEach((file, idx) => {
        const details = document.createElement("details");
        if (idx === 0) {
          details.open = true;
        }
        const summary = document.createElement("summary");
        summary.textContent = file.name;
        const textarea = document.createElement("textarea");
        textarea.className = "test-file-input";
        textarea.value = file.content || "";
        textarea.dataset.index = String(idx);
        details.appendChild(summary);
        details.appendChild(textarea);
        list.appendChild(details);
      });

      const select = document.getElementById("instanceSelect");
      select.value = data.instance_id;
      updateNav();
    }

    function updateNav() {
      const idx = state.ids.indexOf(state.currentId);
      document.getElementById("prevBtn").disabled = state.busy || idx <= 0;
      document.getElementById("nextBtn").disabled = state.busy || idx === -1 || idx >= state.ids.length - 1;
    }

    function collectTestFiles() {
      const inputs = Array.from(document.querySelectorAll(".test-file-input"));
      return inputs.map((input, idx) => ({
        name: state.originalTestFiles[idx] ? state.originalTestFiles[idx].name : "unknown",
        content: input.value || ""
      }));
    }

    function hasUnsavedTests() {
      const inputs = Array.from(document.querySelectorAll(".test-file-input"));
      if (inputs.length !== state.originalTestFiles.length) {
        return true;
      }
      return inputs.some((input, idx) => {
        const original = state.originalTestFiles[idx];
        const value = input.value || "";
        return !original || value !== (original.content || "");
      });
    }

    async function loadInstances() {
      const data = await apiGet("/api/instances");
      state.ids = data.instance_ids;
      state.dataset = data.dataset;
      state.split = data.split;
      state.filter = data.filter_spec || "";
      state.slice = data.slice_spec || "";
      state.shuffle = data.shuffle;

      const metaParts = [
        "Dataset: " + state.dataset,
        "Split: " + state.split,
        "Count: " + state.ids.length
      ];
      if (state.filter) metaParts.push("Filter: " + state.filter);
      if (state.slice) metaParts.push("Slice: " + state.slice);
      if (state.shuffle) metaParts.push("Shuffle: true");
      setText("datasetMeta", metaParts.join(" | "));
      const uploadDataset = document.getElementById("uploadDataset");
      if (uploadDataset && !uploadDataset.value) {
        uploadDataset.value = state.dataset || "";
      }

      const select = document.getElementById("instanceSelect");
      select.innerHTML = "";
      state.ids.forEach((id) => {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = id;
        select.appendChild(option);
      });

      if (state.ids.length) {
        await loadInstance(state.ids[0]);
      }
    }

    async function loadInstance(id) {
      const data = await apiGet("/api/instance/" + encodeURIComponent(id));
      renderInstance(data);
    }

    async function refreshStatus() {
      const data = await apiGet("/api/status");
      state.envInstanceId = data.instance_id || null;
      setText(
        "envStatus",
        data.active
          ? "Environment: running for " + data.instance_id
          : "Environment: not started"
      );
    }

    function pollJob(jobId, logTarget) {
      let offset = 0;
      return new Promise((resolve, reject) => {
        const poll = async () => {
          try {
            const data = await apiGet("/api/job/" + encodeURIComponent(jobId) + "?from=" + offset);
            if (data.log) {
              appendLog(logTarget, data.log);
            }
            if (typeof data.next === "number") {
              offset = data.next;
            }
            if (data.status === "running") {
              setTimeout(poll, 700);
              return;
            }
            if (data.error) {
              appendLog(logTarget, data.error + "\\n");
            }
            resolve(data);
          } catch (err) {
            reject(err);
          }
        };
        poll();
      });
    }

    async function runJob(action, payload, logTarget, statusLabel) {
      if (state.busy) {
        appendLog(logTarget, "Another action is running. Please wait.\\n");
        return;
      }
      setBusy(true, statusLabel);
      appendLog(logTarget, "\\n== " + statusLabel + " ==\\n");
      try {
        const data = await apiPost(action, payload);
        if (!data.job_id) {
          throw new Error("No job id returned");
        }
        const result = await pollJob(data.job_id, logTarget);
        if (result.status === "error") {
          appendLog(logTarget, "== failed ==\\n");
        } else {
          appendLog(logTarget, "== done ==\\n");
        }
        return result;
      } catch (err) {
        appendLog(logTarget, "Error: " + err.message + "\\n");
        return null;
      } finally {
        try {
          await refreshStatus();
        } catch (err) {
          const msg = err && err.message ? err.message : String(err);
          appendLog(logTarget, "Status refresh failed: " + msg + "\\n");
        }
        setBusy(false, "Idle");
      }
    }

    document.getElementById("prevBtn").addEventListener("click", async () => {
      const idx = state.ids.indexOf(state.currentId);
      if (idx > 0) {
        await loadInstance(state.ids[idx - 1]);
      }
    });

    document.getElementById("nextBtn").addEventListener("click", async () => {
      const idx = state.ids.indexOf(state.currentId);
      if (idx !== -1 && idx < state.ids.length - 1) {
        await loadInstance(state.ids[idx + 1]);
      }
    });

    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateTab(btn.dataset.tab);
      });
    });

    document.getElementById("instanceSelect").addEventListener("change", async (e) => {
      await loadInstance(e.target.value);
    });

    document.getElementById("problemInput").addEventListener("input", (e) => {
      const value = e.target.value;
      if (value === state.originalStatement) {
        setText("statementStatus", "Saved");
      } else {
        setText("statementStatus", "Unsaved changes");
      }
    });

    document.getElementById("testFiles").addEventListener("input", (e) => {
      if (!e.target.classList.contains("test-file-input")) {
        return;
      }
      if (hasUnsavedTests()) {
        setText("testsStatus", "Unsaved changes");
      } else {
        setText("testsStatus", "Saved");
      }
    });

    document.getElementById("saveStatementBtn").addEventListener("click", async () => {
      const statement = document.getElementById("problemInput").value;
      const result = await runJob(
        "/api/update_statement",
        { instance_id: state.currentId, statement },
        "actionLog",
        "Saving statement"
      );
      if (result && result.status === "done") {
        await loadInstance(state.currentId);
      }
    });

    document.getElementById("resetStatementBtn").addEventListener("click", () => {
      const input = document.getElementById("problemInput");
      input.value = state.originalStatement;
      setText("statementStatus", "Saved");
    });

    document.getElementById("saveTestsBtn").addEventListener("click", async () => {
      const testFiles = collectTestFiles();
      const result = await runJob(
        "/api/update_tests",
        { instance_id: state.currentId, test_files: testFiles },
        "actionLog",
        "Saving test files"
      );
      if (result && result.status === "done") {
        await loadInstance(state.currentId);
      }
    });

    document.getElementById("resetTestsBtn").addEventListener("click", () => {
      const inputs = document.querySelectorAll(".test-file-input");
      inputs.forEach((input) => {
        const idx = Number(input.dataset.index || 0);
        const original = state.originalTestFiles[idx];
        if (original) {
          input.value = original.content || "";
        }
      });
      setText("testsStatus", "Saved");
    });

    document.getElementById("startBtn").addEventListener("click", async () => {
      const setupRepo = document.getElementById("setupRepo").checked;
      const cleanGit = document.getElementById("cleanGit").checked;
      await runJob("/api/start", {
        instance_id: state.currentId,
        setup_repo: setupRepo,
        clean_git_history: cleanGit
      }, "actionLog", "Starting docker");
    });

    document.getElementById("setupTestsBtn").addEventListener("click", async () => {
      await runJob("/api/setup_tests", { instance_id: state.currentId }, "actionLog", "Setting up tests");
    });

    document.getElementById("removeDocsBtn").addEventListener("click", async () => {
      await runJob("/api/remove_docs", { instance_id: state.currentId }, "actionLog", "Removing docs");
    });

    document.getElementById("applyPatchBtn").addEventListener("click", async () => {
      await runJob("/api/apply_patch", { instance_id: state.currentId }, "actionLog", "Applying PR patch");
    });

    document.getElementById("applyCustomPatchBtn").addEventListener("click", async () => {
      const patchInput = document.getElementById("customPatchInput");
      const patchRaw = patchInput.value || "";
      if (!patchRaw.trim()) {
        appendLog("actionLog", "Custom patch is empty.\\n");
        return;
      }
      await runJob(
        "/api/apply_patch",
        { instance_id: state.currentId, patch: patchRaw },
        "actionLog",
        "Applying custom patch"
      );
    });

    document.getElementById("writeFileBtn").addEventListener("click", async () => {
      const pathInput = document.getElementById("writeFilePath");
      const contentInput = document.getElementById("writeFileContent");
      const path = (pathInput.value || "").trim();
      const content = contentInput.value || "";
      if (!path) {
        setText("writeFileStatus", "File path required");
        return;
      }
      setText("writeFileStatus", "Writing...");
      const result = await runJob(
        "/api/write_file",
        { path, content },
        "actionLog",
        "Writing file"
      );
      if (result && result.status === "done") {
        setText("writeFileStatus", "Wrote " + path);
      } else {
        setText("writeFileStatus", "Write failed");
      }
    });

    document.getElementById("fetchPlanBtn").addEventListener("click", async () => {
      await runJob("/api/fetch_plan", { instance_id: state.currentId }, "actionLog", "Fetching plan");
    });

    document.getElementById("runRepoTestsBtn").addEventListener("click", async () => {
      await runJob("/api/run_repo_tests", { instance_id: state.currentId }, "actionLog", "Running repo tests");
    });

    document.getElementById("runPrTestsBtn").addEventListener("click", async () => {
      await runJob("/api/run_pr_tests", { instance_id: state.currentId }, "actionLog", "Running PR tests");
    });

    document.getElementById("stopBtn").addEventListener("click", async () => {
      await runJob("/api/stop", {}, "actionLog", "Stopping docker");
    });

    document.getElementById("shellRunBtn").addEventListener("click", async () => {
      const cmd = document.getElementById("shellInput").value.trim();
      if (!cmd) return;
      document.getElementById("shellInput").value = "";
      await runJob("/api/shell", { command: cmd }, "shellOutput", "Running shell command");
    });

    document.getElementById("uploadBtn").addEventListener("click", async () => {
      const datasetId = document.getElementById("uploadDataset").value.trim();
      if (!datasetId) {
        setText("uploadStatus", "Dataset id required");
        return;
      }
      setText("uploadStatus", "Uploading...");
      const result = await runJob(
        "/api/upload_dataset",
        { dataset_id: datasetId },
        "actionLog",
        "Uploading dataset"
      );
      if (result && result.status === "done") {
        setText("uploadStatus", "Uploaded " + datasetId);
      } else if (result && result.status === "error") {
        setText("uploadStatus", "Upload failed");
      }
    });

    activateTab("instanceTab");
    loadInstances().then(refreshStatus).catch((err) => {
      setText("datasetMeta", "Failed to load dataset: " + err.message);
    });
  </script>
</body>
</html>
"""


def instance_from_row(row: dict[str, Any]) -> AgentbenchInstance:
    return AgentbenchInstance(
        instance_id=row["instance_id"],
        repo=row["base_repo"],
        task=row["problem_description"],
        patch=row["clean_pr_patch"],
        docker_image=row["docker_image"],
        commit=row["base_sha"],
        setup_commands=row["setup_commands"],
        repo_test_commands=row["repo_test_commands"],
        repo_test_runner=row["repo_test_runner"],
        test_file_names=row["test_file_names"],
        test_file_contents=row["test_file_contents"],
        test_file_runner=row["test_file_runner"],
        test_commands=row["test_commands"],
    )

def stream_env_command(
    env: Any,
    command: str,
    log: Callable[[str], None],
    *,
    timeout: bool = True,
) -> dict[str, Any]:
    log(f"$ {command}\n")
    if hasattr(env, "execute_stream"):
        result = env.execute_stream(command, timeout=timeout, on_output=log)
    else:
        result = env.execute(command, timeout=timeout)
        output = result.get("output", "")
        if output:
            log(output)
    return result


def summarize_test_results(payload: dict[str, Any]) -> str:
    if not payload:
        return "No test results found.\n"
    passed = sum(1 for value in payload.values() if value)
    total = len(payload)
    return f"Test summary: {passed}/{total} passed.\n"


@dataclass
class Job:
    job_id: str
    action: str
    instance_id: str | None
    status: str = "running"
    chunks: list[str] = field(default_factory=list)
    error: str | None = None
    returncode: int | None = None
    created_at: float = field(default_factory=time.time)


@dataclass
class AppState:
    dataset_name: str
    split: str
    filter_spec: str = ""
    slice_spec: str = ""
    shuffle: bool = False
    dataset_rows: list[dict[str, Any]] = field(default_factory=list)
    row_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    instances: list[AgentbenchInstance] = field(default_factory=list)
    instance_map: dict[str, AgentbenchInstance] = field(default_factory=dict)
    env: Any | None = None
    env_instance_id: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    data_lock: threading.Lock = field(default_factory=threading.Lock)
    job_lock: threading.Lock = field(default_factory=threading.Lock)
    jobs: dict[str, Job] = field(default_factory=dict)

    def load(self) -> None:
        dataset = load_dataset(self.dataset_name, split=self.split)
        rows = [dict(row) for row in list(dataset)]
        rows = filter_instances(
            rows,
            filter_spec=self.filter_spec,
            slice_spec=self.slice_spec,
            shuffle=self.shuffle,
        )
        self.dataset_rows = rows
        self.row_map = {row.get("instance_id"): row for row in rows if row.get("instance_id")}
        self.instances = [instance_from_row(row) for row in rows]
        self.instance_map = {inst.instance_id: inst for inst in self.instances}

    def update_statement(self, instance_id: str, statement: str) -> bool:
        with self.data_lock:
            row = self.row_map.get(instance_id)
            if not row:
                return False
            row["problem_description"] = statement
            inst = self.instance_map.get(instance_id)
            if inst:
                inst.task = statement
            return True

    def update_tests(self, instance_id: str, test_files: list[dict[str, Any]]) -> tuple[bool, str]:
        with self.data_lock:
            row = self.row_map.get(instance_id)
            if not row:
                return False, "Instance not found."
            names = list(row.get("test_file_names") or [])
            if names and len(test_files) != len(names):
                return False, "Test file count mismatch."
            if names:
                for idx, test_file in enumerate(test_files):
                    if test_file.get("name") != names[idx]:
                        return False, "Test file name mismatch."
            else:
                names = [test_file.get("name", f"test_{idx}") for idx, test_file in enumerate(test_files)]
                row["test_file_names"] = names

            contents = [test_file.get("content", "") for test_file in test_files]
            row["test_file_contents"] = contents
            inst = self.instance_map.get(instance_id)
            if inst:
                inst.test_file_names = names
                inst.test_file_contents = contents
            return True, ""

    def snapshot_rows(self) -> list[dict[str, Any]]:
        with self.data_lock:
            return [row.copy() for row in self.dataset_rows]

    def _prune_jobs_locked(self, keep: int = 50) -> None:
        if len(self.jobs) <= keep:
            return
        completed = [job for job in self.jobs.values() if job.status != "running"]
        completed.sort(key=lambda job: job.created_at)
        for job in completed[: max(0, len(self.jobs) - keep)]:
            self.jobs.pop(job.job_id, None)

    def create_job(self, action: str, instance_id: str | None) -> Job:
        job_id = uuid.uuid4().hex[:10]
        job = Job(job_id=job_id, action=action, instance_id=instance_id)
        with self.job_lock:
            self.jobs[job_id] = job
            self._prune_jobs_locked()
        return job

    def append_job(self, job_id: str, text: str) -> None:
        if not text:
            return
        with self.job_lock:
            job = self.jobs.get(job_id)
            if job:
                job.chunks.append(text)

    def finish_job(
        self,
        job_id: str,
        status: str,
        *,
        error: str | None = None,
        returncode: int | None = None,
    ) -> None:
        with self.job_lock:
            job = self.jobs.get(job_id)
            if job:
                job.status = status
                job.error = error
                job.returncode = returncode

    def get_job_payload(self, job_id: str, start: int) -> dict[str, Any] | None:
        with self.job_lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if start < 0:
                start = 0
            chunks = job.chunks[start:]
            return {
                "job_id": job.job_id,
                "action": job.action,
                "instance_id": job.instance_id,
                "status": job.status,
                "log": "".join(chunks),
                "next": len(job.chunks),
                "error": job.error,
                "returncode": job.returncode,
            }

    def cleanup_env(self) -> None:
        if self.env is not None:
            try:
                self.env.cleanup()
            finally:
                self.env = None
                self.env_instance_id = None


class AgentbenchHandler(BaseHTTPRequestHandler):
    server_version = "AgentbenchWebUI/0.1"

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, payload: str, status: int = 200, content_type: str = "text/plain") -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _get_state(self) -> AppState:
        return self.server.state  # type: ignore[attr-defined]

    def _launch_job(
        self,
        action: str,
        instance_id: str | None,
        target: Callable[..., None],
        *args: Any,
    ) -> None:
        state = self._get_state()
        job = state.create_job(action, instance_id)
        thread = threading.Thread(
            target=target,
            args=(state, job.job_id, *args),
            daemon=True,
        )
        thread.start()
        self._send_json({"ok": True, "job_id": job.job_id})

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_text(INDEX_HTML, content_type="text/html")
            return
        if parsed.path == "/api/instances":
            state = self._get_state()
            payload = {
                "dataset": state.dataset_name,
                "split": state.split,
                "filter_spec": state.filter_spec,
                "slice_spec": state.slice_spec,
                "shuffle": state.shuffle,
                "instance_ids": [inst.instance_id for inst in state.instances],
            }
            self._send_json(payload)
            return
        if parsed.path.startswith("/api/instance/"):
            instance_id = unquote(parsed.path.split("/api/instance/", 1)[1])
            state = self._get_state()
            inst = state.instance_map.get(instance_id)
            if not inst:
                self._send_text("Unknown instance", status=404)
                return
            payload = {
                "instance_id": inst.instance_id,
                "repo": inst.repo,
                "problem_description": inst.task,
                "test_files": [
                    {"name": name, "content": content}
                    for name, content in zip(inst.test_file_names, inst.test_file_contents)
                ],
                "pr_patch": inst.patch,
            }
            self._send_json(payload)
            return
        if parsed.path.startswith("/api/job/"):
            job_id = unquote(parsed.path.split("/api/job/", 1)[1])
            params = parse_qs(parsed.query)
            try:
                start = int(params.get("from", ["0"])[0])
            except ValueError:
                start = 0
            state = self._get_state()
            payload = state.get_job_payload(job_id, start)
            if not payload:
                self._send_text("Unknown job", status=404)
                return
            self._send_json(payload)
            return
        if parsed.path == "/api/status":
            state = self._get_state()
            payload = {
                "active": state.env is not None,
                "instance_id": state.env_instance_id,
            }
            self._send_json(payload)
            return
        self._send_text("Not found", status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/start":
            self._handle_start()
            return
        if parsed.path == "/api/setup_tests":
            self._handle_setup_tests()
            return
        if parsed.path == "/api/remove_docs":
            self._handle_remove_docs()
            return
        if parsed.path == "/api/apply_patch":
            self._handle_apply_patch()
            return
        if parsed.path == "/api/write_file":
            self._handle_write_file()
            return
        if parsed.path == "/api/fetch_plan":
            self._handle_fetch_plan()
            return
        if parsed.path == "/api/run_repo_tests":
            self._handle_run_repo_tests()
            return
        if parsed.path == "/api/run_pr_tests":
            self._handle_run_pr_tests()
            return
        if parsed.path == "/api/update_statement":
            self._handle_update_statement()
            return
        if parsed.path == "/api/update_tests":
            self._handle_update_tests()
            return
        if parsed.path == "/api/upload_dataset":
            self._handle_upload_dataset()
            return
        if parsed.path == "/api/shell":
            self._handle_shell()
            return
        if parsed.path == "/api/stop":
            self._handle_stop()
            return
        self._send_text("Not found", status=404)

    def _handle_start(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        setup_repo = bool(data.get("setup_repo", True))
        clean_git_history = bool(data.get("clean_git_history", True))
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        self._launch_job(
            "start",
            instance_id,
            self._run_start_job,
            inst,
            setup_repo,
            clean_git_history,
        )

    def _handle_setup_tests(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        self._launch_job("setup_tests", instance_id, self._run_setup_tests_job, inst)

    def _handle_remove_docs(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        self._launch_job("remove_docs", instance_id, self._run_remove_docs_job, inst)

    def _handle_apply_patch(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        patch = data.get("patch") or inst.patch
        self._launch_job("apply_patch", instance_id, self._run_apply_patch_job, inst, patch)

    def _handle_write_file(self) -> None:
        state = self._get_state()
        data = self._read_json()
        path = str(data.get("path") or "").strip()
        content = data.get("content")
        if content is None:
            content = ""
        else:
            content = str(content)
        if not path:
            self._send_text("File path required", status=400)
            return
        self._launch_job("write_file", state.env_instance_id, self._run_write_file_job, path, content)

    def _handle_fetch_plan(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        self._launch_job("fetch_plan", instance_id, self._run_fetch_plan_job, inst)

    def _handle_run_repo_tests(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        self._launch_job("run_repo_tests", instance_id, self._run_repo_tests_job, inst)

    def _handle_run_pr_tests(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        inst = state.instance_map[instance_id]
        self._launch_job("run_pr_tests", instance_id, self._run_pr_tests_job, inst)

    def _handle_update_statement(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        statement = data.get("statement", "")
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        self._launch_job(
            "update_statement",
            instance_id,
            self._run_update_statement_job,
            instance_id,
            statement,
        )

    def _handle_update_tests(self) -> None:
        state = self._get_state()
        data = self._read_json()
        instance_id = data.get("instance_id")
        test_files = data.get("test_files", [])
        if not instance_id or instance_id not in state.instance_map:
            self._send_text("Unknown instance", status=400)
            return
        self._launch_job(
            "update_tests",
            instance_id,
            self._run_update_tests_job,
            instance_id,
            test_files,
        )

    def _handle_upload_dataset(self) -> None:
        state = self._get_state()
        data = self._read_json()
        dataset_id = data.get("dataset_id") or state.dataset_name
        if not dataset_id:
            self._send_text("Dataset id required", status=400)
            return
        self._launch_job("upload_dataset", None, self._run_upload_dataset_job, dataset_id)

    def _handle_shell(self) -> None:
        state = self._get_state()
        data = self._read_json()
        command = data.get("command", "").strip()
        if not command:
            self._send_text("No command provided", status=400)
            return
        instance_id = state.env_instance_id
        self._launch_job("shell", instance_id, self._run_shell_job, command)

    def _handle_stop(self) -> None:
        self._launch_job("stop", None, self._run_stop_job)

    def _run_start_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
        setup_repo: bool,
        clean_git_history: bool,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        env = None
        try:
            log(f"Starting environment for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                state.cleanup_env()
                env_config: dict[str, Any] = {
                    "image": inst.docker_image,
                    "cwd": "/testbed",
                    "timeout": 1800,
                }
                env = get_environment(env_config, default_type="docker")

                def run(cmd: str, *, timeout: bool = True) -> None:
                    result = stream_env_command(env, cmd, log, timeout=timeout)
                    if result["returncode"] != 0:
                        raise RuntimeError(f"Command failed: {cmd}")

                run(f"git checkout {inst.commit}")
                run("git reset --hard")
                if clean_git_history:
                    self._clean_git_history(env)
                if setup_repo:
                    for cmd in inst.setup_commands:
                      try:
                          run(cmd)
                      except Exception as exc:
                          log(f"Setup command failed: {cmd}\n")

                state.env = env
                state.env_instance_id = inst.instance_id
            log("Environment ready.\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            if env is not None:
                try:
                    env.cleanup()
                except Exception:
                    pass
            with state.lock:
                if state.env is env:
                    state.cleanup_env()
            state.finish_job(job_id, "error", error=str(exc))

    def _clean_git_history(self, env) -> None:
        # Remove remotes and any commits after the current checkout time.
        remotes_output = env.execute("git remote").get("output", "")
        remotes = [line.strip() for line in remotes_output.splitlines() if line.strip()]
        for remote in remotes:
            env.execute(f"git remote remove {shlex.quote(remote)}", timeout=False)

        head_ts_output = env.execute("git show -s --format=%ct HEAD").get("output", "").strip()
        try:
            cutoff_ts = int(head_ts_output)
        except ValueError:
            return

        branch_refs_output = env.execute(
            "git for-each-ref --format='%(refname)' refs/heads"
        ).get("output", "")
        branch_refs = [line.strip() for line in branch_refs_output.splitlines() if line.strip()]
        for ref in branch_refs:
            commit_output = env.execute(
                f"git rev-list -n 1 --before=@{cutoff_ts} {shlex.quote(ref)}"
            ).get("output", "")
            commit = commit_output.strip()
            if commit:
                env.execute(f"git update-ref {shlex.quote(ref)} {commit}", timeout=False)
            else:
                env.execute(f"git update-ref -d {shlex.quote(ref)}", timeout=False)

        tag_refs_output = env.execute(
            "git for-each-ref --format='%(refname)' refs/tags"
        ).get("output", "")
        tag_refs = [line.strip() for line in tag_refs_output.splitlines() if line.strip()]
        for ref in tag_refs:
            target_output = env.execute(
                f"git rev-parse {shlex.quote(ref)}^{{}}"
            ).get("output", "")
            target = target_output.strip()
            if not target:
                continue
            tag_ts_output = env.execute(
                f"git show -s --format=%ct {shlex.quote(target)}"
            ).get("output", "")
            tag_ts_str = tag_ts_output.strip()
            try:
                tag_ts = int(tag_ts_str)
            except ValueError:
                continue
            if tag_ts > cutoff_ts:
                env.execute(f"git update-ref -d {shlex.quote(ref)}", timeout=False)

        env.execute("git reflog expire --expire=now --all", timeout=False)
        env.execute("git gc --prune=now --quiet", timeout=False)

    def _run_setup_tests_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Setting up tests for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None or state.env_instance_id != inst.instance_id:
                    error = "Environment not started for this instance."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return

                for fname, content in zip(inst.test_file_names, inst.test_file_contents):
                    result = stream_env_command(
                        env,
                        f"rm -f {shlex.quote(fname)}",
                        log,
                        timeout=False,
                    )
                    if result["returncode"] != 0:
                        raise RuntimeError(f"Command failed: rm -f {fname}")
                    env.write_file(fname, content)
                    log(f"Wrote {fname}\n")
                stream_env_command(env, "rm -f run_pr_tests.py", log, timeout=False)
                env.write_file("run_pr_tests.py", inst.test_file_runner)
                log("Wrote run_pr_tests.py\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_remove_docs_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Removing docs for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None or state.env_instance_id != inst.instance_id:
                    error = "Environment not started for this instance."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                inst.remove_docs(env)
            log("Docs removed.\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_apply_patch_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
        patch: str,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Applying patch for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None or state.env_instance_id != inst.instance_id:
                    error = "Environment not started for this instance."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                patch_path = "/tmp/agentbench_pr_patch.diff"
                env.write_file(patch_path, patch)
                log(f"Wrote patch to {patch_path}\n")
                result = stream_env_command(
                    env,
                    f"git apply --whitespace=nowarn {shlex.quote(patch_path)}",
                    log,
                )
                if result["returncode"] != 0:
                    raise RuntimeError("Patch apply failed")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_write_file_job(
        self,
        state: AppState,
        job_id: str,
        path: str,
        content: str,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Writing file {path}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None:
                    error = "Environment not started."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                env.write_file(path, content)
                log(f"Wrote {path}\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_fetch_plan_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Fetching plan for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None or state.env_instance_id != inst.instance_id:
                    error = "Environment not started for this instance."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                planner = HumanPlanner()
                planner.plan(env, None, inst)
                log("Wrote AGENTS.md\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_shell_job(
        self,
        state: AppState,
        job_id: str,
        command: str,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log("Running shell command\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None:
                    error = "Environment not started."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                result = stream_env_command(env, command, log, timeout=False)
            if result["returncode"] != 0:
                log(f"Command exited with {result['returncode']}\n")
            state.finish_job(job_id, "done", returncode=result["returncode"])
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_stop_job(
        self,
        state: AppState,
        job_id: str,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log("Stopping environment\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                state.cleanup_env()
            log("Environment stopped.\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_update_statement_job(
        self,
        state: AppState,
        job_id: str,
        instance_id: str,
        statement: str,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Updating statement for {instance_id}\n")
            updated = state.update_statement(instance_id, statement)
            if not updated:
                error = "Instance not found for update."
                log(error + "\n")
                state.finish_job(job_id, "error", error=error)
                return
            log("Statement updated.\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_update_tests_job(
        self,
        state: AppState,
        job_id: str,
        instance_id: str,
        test_files: list[dict[str, Any]],
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Updating test files for {instance_id}\n")
            ok, error = state.update_tests(instance_id, test_files)
            if not ok:
                log(error + "\n")
                state.finish_job(job_id, "error", error=error)
                return
            log("Test files updated.\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_upload_dataset_job(
        self,
        state: AppState,
        job_id: str,
        dataset_id: str,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Preparing dataset for upload: {dataset_id}\n")
            rows = state.snapshot_rows()
            if not rows:
                error = "No rows to upload."
                log(error + "\n")
                state.finish_job(job_id, "error", error=error)
                return
            log(f"Loaded {len(rows)} instances for upload.\n")
            if state.filter_spec or state.slice_spec or state.shuffle:
                log(
                    "Upload uses current view (filter/slice/shuffle): "
                    f"filter={state.filter_spec or 'none'}, "
                    f"slice={state.slice_spec or 'none'}, "
                    f"shuffle={state.shuffle}\n"
                )

            dataset = Dataset.from_list(rows)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_name = dataset_id.replace("/", "_")
            output_dir = Path("output") / "webui_exports" / f"{safe_name}_{timestamp}"
            output_dir.mkdir(parents=True, exist_ok=True)
            dataset.save_to_disk(str(output_dir))
            log(f"Saved dataset to {output_dir}\n")

            dataset.push_to_hub(dataset_id, private=False)
            log(f"Pushed dataset to {dataset_id}\n")
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_repo_tests_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Running repo tests for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None or state.env_instance_id != inst.instance_id:
                    error = "Environment not started for this instance."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                env.execute("rm -f run_tests.py", timeout=False)
                env.write_file("run_tests.py", inst.repo_test_runner)
                log("Wrote run_tests.py\n")
                stream_env_command(env, "rm -f test_results.json", log, timeout=False)
                for cmd in inst.repo_test_commands:
                    result = stream_env_command(env, cmd, log, timeout=True)
                    if result["returncode"] != 0:
                        raise RuntimeError(f"Command failed: {cmd}")
                raw_results = env.read_file("test_results.json")
                if raw_results:
                    try:
                        results = json.loads(raw_results)
                    except json.JSONDecodeError:
                        results = {}
                        log("Failed to parse test_results.json\n")
                else:
                    results = {}
                log(summarize_test_results(results))
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))

    def _run_pr_tests_job(
        self,
        state: AppState,
        job_id: str,
        inst: AgentbenchInstance,
    ) -> None:
        def log(text: str) -> None:
            state.append_job(job_id, text)

        try:
            log(f"Running PR tests for {inst.instance_id}\n")
            log("Waiting for environment lock...\n")
            with state.lock:
                log("Environment lock acquired.\n")
                env = state.env
                if env is None or state.env_instance_id != inst.instance_id:
                    error = "Environment not started for this instance."
                    log(error + "\n")
                    state.finish_job(job_id, "error", error=error)
                    return
                for fname, content in zip(inst.test_file_names, inst.test_file_contents):
                    stream_env_command(
                        env,
                        f"rm -f {shlex.quote(fname)}",
                        log,
                        timeout=False,
                    )
                    env.write_file(fname, content)
                    log(f"Wrote {fname}\n")
                stream_env_command(env, "rm -f run_pr_tests.py", log, timeout=False)
                env.write_file("run_pr_tests.py", inst.test_file_runner)
                log("Wrote run_pr_tests.py\n")
                stream_env_command(env, "rm -f pr_test_results.json", log, timeout=False)
                for cmd in inst.test_commands:
                    result = stream_env_command(env, cmd, log, timeout=True)
                    if result["returncode"] != 0:
                        raise RuntimeError(f"Command failed: {cmd}")
                raw_results = env.read_file("pr_test_results.json")
                if raw_results:
                    try:
                        results = json.loads(raw_results)
                    except json.JSONDecodeError:
                        results = {}
                        log("Failed to parse pr_test_results.json\n")
                else:
                    results = {}
                log(summarize_test_results(results))
            state.finish_job(job_id, "done", returncode=0)
        except Exception as exc:
            log(f"Error: {exc}\n")
            log(traceback.format_exc() + "\n")
            state.finish_job(job_id, "error", error=str(exc))


def build_state(args: argparse.Namespace) -> AppState:
    state = AppState(
        dataset_name=args.dataset,
        split=args.split,
        filter_spec=args.filter,
        slice_spec=args.slice,
        shuffle=args.shuffle,
    )
    state.load()
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agentbench dataset web UI.")
    parser.add_argument("--dataset", default="eth-sri/agentbench", help="Hugging Face dataset name.")
    parser.add_argument("--split", default="train", help="Dataset split to load.")
    parser.add_argument("--filter", default="", help="Regex filter for instance_id.")
    parser.add_argument("--slice", default="", help="Python slice spec, e.g. '0:50'.")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle instances before slicing.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8899, help="Port to bind.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = build_state(args)

    def cleanup() -> None:
        state.cleanup_env()

    atexit.register(cleanup)

    server = ThreadingHTTPServer((args.host, args.port), AgentbenchHandler)
    server.state = state  # type: ignore[attr-defined]
    print(
        f"Agentbench web UI running on http://{args.host}:{args.port} "
        f"({len(state.instances)} instances)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
