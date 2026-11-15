"use strict";

const state = {
  subject: "AMANDA",
  session: "day1",
  takes: {},
  recording: false, // true while the microphone is in use
  saved: [],        // takes stored by the last save, until a new take is recorded
};

const TAKES = [
  { key: "vowel", label: "sustained \"ah\"", seconds: 5 },
  { key: "passage", label: "fixed passage", seconds: 30 },
  // Free speech always runs its full length: the take needs the whole sample.
  { key: "free", label: "free speech", seconds: 30, fixedLength: true },
];

const COUNTDOWN_SECONDS = 3;
const SUBJECT_RE = /^[A-Z0-9][A-Z0-9-]{1,15}$/;
const SESSION_RE = /^[a-z0-9][a-z0-9-]{1,15}$/;

// One place for recovery copy so static contract tests can pin every path.
const ERROR_COPY = {
  microphone: "Microphone access was blocked or no microphone was found. "
    + "Allow microphone access in the browser, then press Record on the take again.",
  validation: "The local pipeline rejected these takes (422 validation error). "
    + "The takes are still here; press Retry upload.",
  duplicate: "This session already exists on this machine. Press Replace saved "
    + "session to overwrite it with these takes, or continue to check-in or open "
    + "the report.",
  server: "The local pipeline could not store this session. "
    + "The takes are still here; press Retry upload.",
  context: "Check-in save failed. Press Retry save.",
  report: "Could not build the report. Press Refresh to try again.",
};

function showState(name) {
  for (const id of ["record", "checkin", "report"]) {
    document.getElementById(id).hidden = id !== name;
  }
  // Check-in belongs to a recording session, so it sits under the Record tab.
  const current = name === "report" ? "nav-report" : "nav-record";
  for (const id of ["nav-record", "nav-report"]) {
    const tab = document.getElementById(id);
    if (id === current) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
}

// While the microphone is in use nothing else may start or navigate away.
// While the microphone or an upload is in use nothing else may start.
function setBusy(busy) {
  for (const id of ["save-session", "nav-record", "nav-report", "replace-session",
                    "retry-upload"]) {
    document.getElementById(id).disabled = busy;
  }
  for (const button of document.querySelectorAll(".take-button")) button.disabled = busy;
  if (!busy) refreshSteps();
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const detail = await response.text();
    const error = new Error(`${response.status} ${detail}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function encodeWav(channels, sampleRate) {
  const numFrames = channels[0].length;
  const bytesPerSample = 2;
  const blockAlign = channels.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + numFrames * blockAlign);
  const view = new DataView(buffer);
  const writeStr = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + numFrames * blockAlign, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels.length, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, numFrames * blockAlign, true);
  let offset = 44;
  for (let frame = 0; frame < numFrames; frame += 1) {
    for (let channel = 0; channel < channels.length; channel += 1) {
      const sample = Math.max(-1, Math.min(1, channels[channel][frame]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([view], { type: "audio/wav" });
}

function showRecordError(text) {
  const error = document.getElementById("record-error");
  error.textContent = text;
  error.hidden = false;
}

function clearRecordError() {
  const error = document.getElementById("record-error");
  error.textContent = "";
  error.hidden = true;
}

function readIds() {
  const subjectInput = document.getElementById("subject");
  const sessionInput = document.getElementById("session-label");
  const subject = subjectInput.value.trim().toUpperCase();
  const session = sessionInput.value.trim().toLowerCase();
  clearRecordError();
  if (!SUBJECT_RE.test(subject)) {
    showRecordError("Crew member must be 2-16 characters: uppercase letters, digits, "
      + "or hyphens, starting with a letter or digit (for example AMANDA or CDR-01).");
    subjectInput.focus();
    return null;
  }
  if (!SESSION_RE.test(session)) {
    showRecordError("Mission day must be 2-16 characters: lowercase letters, digits, "
      + "or hyphens, starting with a letter or digit (for example day1).");
    sessionInput.focus();
    return null;
  }
  return { subject, session };
}

async function runCountdown(seconds, label) {
  const countdown = document.getElementById("take-countdown");
  const status = document.getElementById("take-status");
  countdown.hidden = false;
  for (let remaining = seconds; remaining > 0; remaining -= 1) {
    countdown.textContent = String(remaining);
    status.textContent = `Starting ${label} in ${remaining}...`;
    await sleep(1000);
  }
  countdown.textContent = "Recording";
  await sleep(250);
  countdown.hidden = true;
}

function setPassageVisible(visible) {
  document.getElementById("passage-text").hidden = !visible;
}

const STEP_TEXT = { idle: "Not recorded", active: "Recording now", done: "Captured",
                    saved: "Saved" };

function takeButton(key) {
  return document.querySelector(`.take-button[data-take="${key}"]`);
}

function setStep(key, stepState) {
  const step = document.querySelector(`.step[data-take="${key}"]`);
  if (!step) return;
  step.classList.toggle("active", stepState === "active");
  step.classList.toggle("done", stepState === "done" || stepState === "saved");
  step.querySelector(".step-state").textContent = STEP_TEXT[stepState] || STEP_TEXT.idle;
}

// Each card shows its own state and its own Record or Retake button. Saving
// needs the two takes the measures come from; free speech is optional.
function refreshSteps() {
  for (const take of TAKES) {
    const captured = Boolean(state.takes[take.key]);
    const stored = state.saved.includes(take.key);
    setStep(take.key, captured ? "done" : (stored ? "saved" : "idle"));
    takeButton(take.key).textContent = captured ? "Retake" : "Record";
  }
  document.getElementById("save-session").disabled =
    !(state.takes.vowel && state.takes.passage);
}

async function recordTake(task, maxSeconds, onTick, stopButton) {
  let stream = null;
  let context = null;
  let recorder = null;
  let raf = 0;
  try {
    // Request an unprocessed mono signal: the measured features are sensitive
    // to browser speech cleanup. Browsers may ignore these constraints, so the
    // report records that limitation rather than claiming compliance.
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        channelCount: 1,
      },
    });
    context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    const meter = document.querySelector("#level-meter span");
    const meterRoot = document.getElementById("level-meter");
    const data = new Uint8Array(analyser.fftSize);
    const draw = () => {
      analyser.getByteTimeDomainData(data);
      let peak = 0;
      for (const value of data) peak = Math.max(peak, Math.abs(value - 128) / 128);
      const pct = Math.round(peak * 100);
      meter.style.width = `${pct}%`;
      meterRoot.setAttribute("aria-valuenow", String(pct));
      raf = requestAnimationFrame(draw);
    };
    draw();

    recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    const stopped = new Promise((resolve) => { recorder.onstop = resolve; });
    recorder.start();

    // The take ends when the time runs out or the crew member presses the
    // card's button (now reading Finish take), whichever comes first.
    await new Promise((resolve) => {
      const started = Date.now();
      let timer = 0;
      const finish = () => {
        clearInterval(timer);
        if (stopButton) {
          stopButton.removeEventListener("click", finish);
          stopButton.disabled = true;
        }
        resolve();
      };
      timer = setInterval(() => {
        const left = Math.max(0, maxSeconds - Math.floor((Date.now() - started) / 1000));
        if (onTick) onTick(left);
        if (left <= 0) finish();
      }, 250);
      if (stopButton) {
        stopButton.textContent = "Finish take";
        stopButton.disabled = false;
        stopButton.addEventListener("click", finish);
      }
    });
    recorder.stop();
    await stopped;

    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    const audio = await context.decodeAudioData(await blob.arrayBuffer());
    return encodeWav([audio.getChannelData(0)], audio.sampleRate);
  } finally {
    // Every exit path must release the microphone and decode context, or a
    // failed take leaves the browser holding the device.
    if (raf) cancelAnimationFrame(raf);
    document.querySelector("#level-meter span").style.width = "0%";
    if (recorder && recorder.state !== "inactive") recorder.stop();
    if (stream) stream.getTracks().forEach((track) => track.stop());
    if (context && context.state !== "closed") await context.close();
  }
}

function clearTakes() {
  state.takes = {};
}

async function uploadTakes(replace) {
  const form = new FormData();
  form.append("subject", state.subject);
  form.append("session", state.session);
  if (replace) form.append("replace", "true");
  for (const take of TAKES) {
    if (!state.takes[take.key]) {
      if (take.key === "free") continue;            // free speech is optional
      throw new Error(`missing ${take.key} take`);
    }
    form.append(take.key, state.takes[take.key], `${state.session}_${take.key}.wav`);
  }
  return api("/api/session", { method: "POST", body: form });
}

function handleUploadError(error) {
  const retry = document.getElementById("retry-upload");
  const checkinButton = document.getElementById("to-checkin");
  const status = document.getElementById("take-status");
  if (error.status === 409) {
    retry.hidden = true;
    document.getElementById("replace-session").hidden = false;
    checkinButton.disabled = false;
    document.getElementById("to-report").disabled = false;
    status.textContent = ERROR_COPY.duplicate;
    return;
  }
  retry.hidden = false;
  if (error.status === 422) {
    status.textContent = ERROR_COPY.validation;
  } else {
    status.textContent = `${ERROR_COPY.server} (${error.status || "network error"})`;
  }
}

function handleRecordingError(error) {
  const status = document.getElementById("take-status");
  const name = error && error.name;
  if (name === "NotAllowedError" || name === "SecurityError"
      || name === "NotFoundError" || name === "NotReadableError") {
    status.textContent = ERROR_COPY.microphone;
    return;
  }
  status.textContent = `Recording failed: ${error.message}. Check the microphone and `
    + "press Record on the take to try again.";
}

// Records one take with a countdown, a live time-left readout, and the step
// card marked as active, so it is never unclear which take is being captured.
// Records one take: countdown, live time-left readout, the card marked active,
// and the card's own button acting as Finish take.
async function captureTake(take, button) {
  const status = document.getElementById("take-status");
  const number = TAKES.indexOf(take) + 1;
  const name = `take ${number}: ${take.label}`;
  setStep(take.key, "active");
  setPassageVisible(take.key === "passage");
  button.textContent = "Starting...";
  try {
    await runCountdown(COUNTDOWN_SECONDS, name);
    if (take.fixedLength) button.textContent = "Recording...";
    state.takes[take.key] = await recordTake(take.key, take.seconds, (left) => {
      status.textContent = take.fixedLength
        ? `Recording ${name}. ${left}s left. Keep talking until the time runs out.`
        : `Recording ${name}. ${left}s left. Press Finish take when done.`;
    }, take.fixedLength ? null : button);
  } finally {
    setPassageVisible(false);
  }
}

// A card's button records (or re-records) only that take. Other takes are
// left exactly as they are, and nothing is stored until Save session.
async function startTake(key) {
  if (state.recording) return;            // the same button is Finish take
  const take = TAKES.find((item) => item.key === key);
  if (!take || !readIds()) return;
  const status = document.getElementById("take-status");
  state.recording = true;
  state.saved = [];
  setBusy(true);
  try {
    await captureTake(take, takeButton(key));
    const ready = state.takes.vowel && state.takes.passage;
    status.textContent = `Take ${TAKES.indexOf(take) + 1} captured.`
      + (ready ? " Save the session when you are ready, or retake any take."
               : " Record the remaining takes.");
  } catch (error) {
    handleRecordingError(error);
  } finally {
    state.recording = false;
    setBusy(false);
  }
}

async function saveSession(replace) {
  const ids = readIds();
  if (!ids) return;
  state.subject = ids.subject;
  state.session = ids.session;
  const status = document.getElementById("take-status");
  setBusy(true);
  status.textContent = "Saving to this machine...";
  try {
    await uploadTakes(replace);
    status.textContent = replace
      ? `Session ${state.session} replaced on this machine. Continue to check-in.`
      : `Session ${state.session} saved on this machine. Continue to check-in.`;
    state.saved = Object.keys(state.takes);
    clearTakes();
    document.getElementById("replace-session").hidden = true;
    document.getElementById("retry-upload").hidden = true;
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    handleUploadError(error);
  } finally {
    setBusy(false);
  }
}

function openReport() {
  const input = document.getElementById("subject");
  const subject = input.value.trim().toUpperCase();
  if (!SUBJECT_RE.test(subject)) {
    showState("record");
    showRecordError("Enter a crew member to open their report (for example AMANDA).");
    input.focus();
    return;
  }
  clearRecordError();
  state.subject = subject;
  showState("report");
  loadReport();
}

async function retryUpload() {
  if (!state.takes.vowel || !state.takes.passage) {
    document.getElementById("take-status").textContent =
      "No captured takes to upload. Record the takes first.";
    return;
  }
  const retry = document.getElementById("retry-upload");
  const status = document.getElementById("take-status");
  retry.disabled = true;
  status.textContent = "Retrying upload...";
  try {
    await uploadTakes();
    retry.hidden = true;
    state.saved = Object.keys(state.takes);
    clearTakes();
    refreshSteps();
    status.textContent = "Session saved on this machine.";
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    handleUploadError(error);
  } finally {
    retry.disabled = false;
  }
}

// The check-in is one form: tick anything that applies, or nothing at all.
// It is sent as the same raw text the scripted check-in produces, so the
// server parses it with the CLI's rules and the two paths cannot drift.
function buildRaw() {
  const form = document.getElementById("checkin-form");
  const ticked = (field) => Array.from(
    form.querySelectorAll(`input[type="checkbox"][data-field="${field}"]`))
    .filter((box) => box.checked).map((box) => box.value);
  const text = (id) => document.getElementById(id).value.trim() || null;
  const cold = ticked("cold_or_congestion");
  const pain = ticked("unusual_pain").length > 0;
  const posture = form.querySelector('input[name="posture"]:checked');
  return {
    cold_or_congestion: cold.length ? `yes: ${cold.join(", ")}` : "no",
    cough: ticked("cough").length ? "yes" : "no",
    sleep_hours: text("sleep-hours"),
    unusual_pain: pain ? (text("pain-where") || "yes") : "no",
    posture: posture ? posture.value : null,
    // The question behind this field is "same setup as usual?", so a ticked
    // "different" box is a no.
    setup_changed: ticked("setup_changed").length
      ? "no, different microphone or room" : "yes",
    anything_else: text("anything-else"),
  };
}

function resetCheckin() {
  document.getElementById("checkin-form").reset();
  document.getElementById("pain-where-field").hidden = true;
  document.getElementById("checkin-save").textContent = "Save check-in";
  document.getElementById("to-report").disabled = true;
  setStatus("");
}

async function submitCheckin() {
  const save = document.getElementById("checkin-save");
  save.disabled = true;
  setStatus("Saving check-in...");
  try {
    await api("/api/context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: state.subject, session: state.session, raw: buildRaw(),
      }),
    });
    save.textContent = "Save check-in";
    document.getElementById("to-report").disabled = false;
    setStatus("Check-in saved. Open the report when ready.");
  } catch (error) {
    save.textContent = "Retry save";
    setStatus(`${ERROR_COPY.context} (${error.message})`);
  } finally {
    save.disabled = false;
  }
}

function sparkline(values, mean, sd, flagged) {
  const width = 220;
  const height = 44;
  const pad = 6;
  const clean = values.filter((value) => value !== null);
  if (clean.length < 2) return document.createElement("span");
  const lo = Math.min(...clean, mean - 2.5 * sd);
  const hi = Math.max(...clean, mean + 2.5 * sd);
  const span = hi - lo || 1;
  const x = (index) => pad + index * (width - 2 * pad) / Math.max(values.length - 1, 1);
  const y = (value) => height - pad - (value - lo) * (height - 2 * pad) / span;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "trend across sessions with the baseline band");

  const band = document.createElementNS(ns, "rect");
  band.setAttribute("x", "0");
  band.setAttribute("y", String(Math.min(y(mean + sd), y(mean - sd))));
  band.setAttribute("width", String(width));
  band.setAttribute("height", String(Math.max(Math.abs(y(mean - sd) - y(mean + sd)), 1)));
  band.setAttribute("class", "band");
  svg.appendChild(band);

  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1", "0");
  line.setAttribute("x2", String(width));
  line.setAttribute("y1", String(y(mean)));
  line.setAttribute("y2", String(y(mean)));
  line.setAttribute("class", "meanline");
  svg.appendChild(line);

  const points = [];
  values.forEach((value, index) => {
    if (value === null) return;
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", String(x(index)));
    dot.setAttribute("cy", String(y(value)));
    dot.setAttribute("r", flagged.includes(index) ? "4" : "2.5");
    dot.setAttribute("class", flagged.includes(index) ? "dot flag" : "dot");
    svg.appendChild(dot);
    points.push(`${x(index).toFixed(1)},${y(value).toFixed(1)}`);
  });

  const polyline = document.createElementNS(ns, "polyline");
  polyline.setAttribute("points", points.join(" "));
  polyline.setAttribute("class", "series");
  svg.appendChild(polyline);
  return svg;
}

function findingRow(finding) {
  const row = document.createElement("div");
  row.className = finding.explained.length ? "row" : "row open-row";

  const meta = document.createElement("div");
  meta.className = "meta";
  const label = document.createElement("div");
  label.className = "label";
  label.textContent = finding.label;
  const phrase = document.createElement("div");
  phrase.className = "phrase";
  phrase.textContent = finding.phrase;
  const detail = document.createElement("div");
  detail.className = "detail";
  detail.textContent = `${finding.value_text} against your baseline of `
    + `${finding.baseline_text} · ${finding.run_length} `
    + `session${finding.run_length === 1 ? "" : "s"} running`
    + ` · baseline band ±${finding.spread_text}`;
  const tag = document.createElement("span");
  tag.className = finding.explained.length ? "tag explained" : "tag open";
  tag.textContent = finding.explained.length
    ? `accounted for: ${finding.explained.join(", ").replaceAll("_", " ")}`
    : "no reported explanation";

  meta.append(label, phrase, detail, tag);
  const spark = document.createElement("div");
  spark.className = "spark";
  spark.appendChild(sparkline(finding.series, finding.baseline_mean,
                              finding.baseline_sd, finding.flagged_indices));
  row.append(meta, spark);
  return row;
}

// One row per measure with its numbers and trend, so a quiet report still
// shows the data. Flagged measures are skipped here: they have a finding row.
function measureRow(measure) {
  const row = document.createElement("div");
  row.className = "row";
  const meta = document.createElement("div");
  meta.className = "meta";
  const label = document.createElement("div");
  label.className = "label";
  label.textContent = measure.label;
  const phrase = document.createElement("div");
  phrase.className = "phrase";
  phrase.textContent = measure.latest_text;
  const detail = document.createElement("div");
  detail.className = "detail";
  const parts = [];
  if (measure.baseline_text) {
    parts.push(measure.baseline_complete
      ? `your baseline ${measure.baseline_text}`
      : `average so far ${measure.baseline_text}`);
  }
  if (measure.spread_text) parts.push(`usual spread ±${measure.spread_text}`);
  if (measure.baseline_complete && measure.change_text) parts.push(measure.change_text);
  detail.textContent = parts.join(" · ");
  const hint = document.createElement("div");
  hint.className = "detail hint";
  hint.textContent = measure.hint;
  meta.append(label, phrase, detail, hint);
  const spark = document.createElement("div");
  spark.className = "spark";
  if (measure.baseline_mean !== null) {
    spark.appendChild(sparkline(measure.series, measure.baseline_mean,
                                measure.baseline_sd || 0, []));
  }
  row.append(meta, spark);
  return row;
}

function measuresSection(data, title) {
  const rows = (data.measures || []).filter((measure) => !measure.flagged);
  if (!rows.length) return null;
  const box = document.createElement("div");
  box.className = "stable-list";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const note = document.createElement("p");
  note.className = "sub";
  note.textContent = `Latest session${data.sessions && data.sessions.length
    ? ` (${data.sessions[data.sessions.length - 1]})` : ""} of ${data.session_count}. `
    + "The big number is your latest reading. Each dot on the chart is one session.";
  box.append(heading, note);
  for (const measure of rows) box.appendChild(measureRow(measure));
  return box;
}

function renderReport(data) {
  document.getElementById("report-headline").textContent = data.headline;
  document.getElementById("baseline-note").textContent = data.state === "baseline"
    ? `Your baseline is built from your first ${data.n_baseline} sessions.`
    : "Measured against your own baseline. Shaded band is one standard deviation; "
      + "the dashed line is your baseline average.";
  const list = document.getElementById("report-list");
  list.replaceChildren();
  if (data.state === "empty") {
    const empty = document.createElement("p");
    empty.textContent = "No sessions yet. Record your first check-in to begin.";
    list.appendChild(empty);
    return;
  }
  if (data.state === "baseline") {
    const pending = document.createElement("p");
    pending.textContent = "No findings are reported yet.";
    list.appendChild(pending);
    const soFar = measuresSection(data, "Your measures so far");
    if (soFar) list.appendChild(soFar);
    return;
  }
  for (const finding of data.findings) {
    list.appendChild(findingRow(finding));
  }
  const within = measuresSection(data, "Within your baseline");
  if (within) list.appendChild(within);
  const footer = document.createElement("p");
  footer.className = "sub";
  footer.textContent = "This describes what changed, not why. Ordinary causes are the "
    + "common ones: a head cold, a different microphone, the time of day, the room. "
    + "Nothing here is a diagnosis.";
  list.appendChild(footer);
}

async function loadReport() {
  const refresh = document.getElementById("report-refresh");
  refresh.disabled = true;
  setStatus("Building your report...");
  try {
    const data = await api(`/api/report?subject=${encodeURIComponent(state.subject)}`);
    renderReport(data);
    setStatus("");
  } catch (error) {
    setStatus(`${ERROR_COPY.report} (${error.message})`);
  } finally {
    refresh.disabled = false;
  }
}

document.getElementById("report-refresh").addEventListener("click", loadReport);
document.getElementById("to-report").addEventListener("click", () => {
  showState("report");
  loadReport();
});
document.getElementById("save-session").addEventListener("click", () => saveSession(false));
document.getElementById("replace-session").addEventListener("click", () => saveSession(true));
for (const button of document.querySelectorAll(".take-button")) {
  button.addEventListener("click", () => startTake(button.dataset.take));
}
document.getElementById("nav-record").addEventListener("click", () => showState("record"));
document.getElementById("nav-report").addEventListener("click", openReport);
document.getElementById("retry-upload").addEventListener("click", retryUpload);
document.getElementById("subject").addEventListener("input", clearRecordError);
document.getElementById("session-label").addEventListener("input", clearRecordError);
document.getElementById("checkin-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheckin();
});
document.getElementById("pain-check").addEventListener("change", (event) => {
  document.getElementById("pain-where-field").hidden = !event.target.checked;
});
document.getElementById("to-checkin").addEventListener("click", () => {
  resetCheckin();
  showState("checkin");
});
showState("record");
refreshSteps();
