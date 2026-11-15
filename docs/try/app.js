"use strict";

const state = {
  subject: "AMANDA",
  session: "day1",
  takes: {},
  recording: false, // true while the microphone is in use
  saved: [],        // takes stored by the last save, until a new take is recorded
  sample: false,    // true while the simulated crew member is on screen
};

// The online preview is the same page with no local pipeline behind it: it can
// show the sample report but cannot record.
const STATIC_PREVIEW = Boolean(window.BASELINE_DRIFT_STATIC);

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
  for (const id of ["record", "checkin", "report", "trends"]) {
    document.getElementById(id).hidden = id !== name;
  }
  // Check-in belongs to a recording session, so it sits under the Record tab.
  const current = name === "report" ? "nav-report"
    : name === "trends" ? "nav-trends" : "nav-record";
  for (const id of ["nav-record", "nav-report", "nav-trends"]) {
    const tab = document.getElementById(id);
    if (id === current) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
}

// While the microphone is in use nothing else may start or navigate away.
// While the microphone or an upload is in use nothing else may start.
function setBusy(busy) {
  for (const id of ["save-session", "nav-record", "nav-report", "nav-trends",
                    "replace-session", "retry-upload"]) {
    document.getElementById(id).disabled = busy;
  }
  for (const button of document.querySelectorAll(".take-button")) button.disabled = busy;
  if (!busy) refreshSteps();
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

// Stop take abandons the take in progress. Nothing from it is kept, and a
// take recorded earlier for the same card is left as it was.
function takeStopped() {
  const error = new Error("take stopped");
  error.name = "TakeStopped";
  return error;
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

// "fd12" reads as "FD12"; older labels such as "day3" are shown as they are.
function sessionName(session) {
  const match = /^fd(\d+)$/.exec(session || "");
  return match ? `FD${match[1]}` : (session || "");
}

// Fill in the next flight day for whoever is typed in the crew member box.
async function suggestFlightDay() {
  const subject = document.getElementById("subject").value.trim().toUpperCase();
  if (!SUBJECT_RE.test(subject) || state.recording) return;
  try {
    const next = await api(`/api/next-session?subject=${encodeURIComponent(subject)}`);
    document.getElementById("session-label").value = String(next.flight_day);
  } catch (error) {
    // The field keeps whatever it shows; the crew member can still type a day.
  }
}

function readIds() {
  const subjectInput = document.getElementById("subject");
  const sessionInput = document.getElementById("session-label");
  const subject = subjectInput.value.trim().toUpperCase();
  // Flight days are counted from 1 (launch day is FD1) and stored as fd<n>.
  const day = Number(sessionInput.value);
  const session = `fd${day}`;
  clearRecordError();
  if (!SUBJECT_RE.test(subject)) {
    showRecordError("Crew member must be 2-16 characters: uppercase letters, digits, "
      + "or hyphens, starting with a letter or digit (for example AMANDA or CDR-01).");
    subjectInput.focus();
    return null;
  }
  if (!Number.isInteger(day) || day < 1 || day > 9999 || !SESSION_RE.test(session)) {
    showRecordError("Flight day must be a whole number, 1 or higher. Launch day is "
      + "flight day 1.");
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
    for (let i = 0; i < 10; i += 1) {
      await sleep(100);
      if (state.stopTake) throw takeStopped();
    }
  }
  countdown.textContent = "Go";
  await sleep(250);
}

// The countdown, time left and microphone level sit inside the card being
// recorded, so nothing about the take in progress is off screen.
function moveLive(key) {
  const live = document.getElementById("take-live");
  if (key) {
    const card = document.querySelector(`.step[data-take="${key}"]`);
    card.querySelector(".step-body").appendChild(live);
    live.classList.add("in-card");
    card.scrollIntoView({ block: "nearest", behavior: "smooth" });
  } else {
    const steps = document.getElementById("take-steps");
    const error = document.getElementById("record-error");
    (error || steps).after(live);
    live.classList.remove("in-card");
    document.getElementById("take-countdown").hidden = true;
  }
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
// Each captured take can be played back from its own card before saving.
// The player points at the audio held in this page; nothing leaves it.
const playback = {};
function showPlayback(key, blob) {
  const body = document.querySelector(`.step[data-take="${key}"] .step-body`);
  let audio = body.querySelector(".take-audio");
  const current = playback[key];
  if (current && current.blob === blob) return;
  if (current) URL.revokeObjectURL(current.url);
  delete playback[key];
  if (!blob) {
    if (audio) audio.remove();
    return;
  }
  if (!audio) {
    audio = document.createElement("audio");
    audio.className = "take-audio";
    audio.controls = true;
    audio.setAttribute("aria-label", "Play this take back");
    body.appendChild(audio);
  }
  const url = URL.createObjectURL(blob);
  playback[key] = { blob, url };
  audio.src = url;
}

function refreshSteps() {
  for (const take of TAKES) {
    const captured = Boolean(state.takes[take.key]);
    const stored = state.saved.includes(take.key);
    setStep(take.key, captured ? "done" : (stored ? "saved" : "idle"));
    takeButton(take.key).textContent = captured ? "Retake" : "Record";
    showPlayback(take.key, state.takes[take.key]);
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
        if (left <= 0 || state.stopTake) finish();
      }, 250);
      if (stopButton) {
        stopButton.textContent = "Finish take";
        stopButton.disabled = false;
        stopButton.addEventListener("click", finish);
      }
    });
    recorder.stop();
    await stopped;
    if (state.stopTake) throw takeStopped();

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
  state.stopTake = false;
  moveLive(take.key);
  const countdown = document.getElementById("take-countdown");
  button.textContent = "Starting...";
  try {
    await runCountdown(COUNTDOWN_SECONDS, name);
    if (take.fixedLength) button.textContent = "Recording...";
    state.takes[take.key] = await recordTake(take.key, take.seconds, (left) => {
      countdown.textContent = `${left}s`;
      status.textContent = take.fixedLength
        ? `Recording ${name}. ${left}s left. Keep talking until the time runs out.`
        : `Recording ${name}. ${left}s left. Press Finish take when done.`;
    }, take.fixedLength ? null : button);
  } finally {
    moveLive(null);
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
    if (error && error.name === "TakeStopped") {
      status.textContent = `Take ${TAKES.indexOf(take) + 1} stopped. Nothing from it was kept.`;
    } else {
      handleRecordingError(error);
    }
  } finally {
    state.stopTake = false;
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
      ? `${sessionName(state.session)} replaced on this machine. Continue to check-in.`
      : `${sessionName(state.session)} saved on this machine. Continue to check-in.`;
    state.saved = Object.keys(state.takes);
    clearTakes();
    state.recording = false;
    suggestFlightDay();
    document.getElementById("replace-session").hidden = true;
    document.getElementById("retry-upload").hidden = true;
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    handleUploadError(error);
  } finally {
    setBusy(false);
  }
}

// One place decides where a report comes from: the sample file, or this
// machine's own sessions.
async function fetchReport() {
  if (state.sample) return api("sample_report.json");
  return api(`/api/report?subject=${encodeURIComponent(state.subject)}`);
}

function setSample(on) {
  state.sample = on;
  document.getElementById("sample-banner").hidden = !on;
  document.getElementById("sample-on").hidden = on || STATIC_PREVIEW;
  document.getElementById("sample-off").hidden = STATIC_PREVIEW;
}

function openReport() {
  if (state.sample) {
    showState("report");
    loadReport();
    return;
  }
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

// The report charts show only the most recent sessions so each reading stays
// readable; the Trends tab has the full history.
const RECENT_SESSIONS = 12;

function sparkline(allValues, mean, sd, allFlagged) {
  const offset = Math.max(0, allValues.length - RECENT_SESSIONS);
  const values = allValues.slice(offset);
  const flagged = allFlagged.map((index) => index - offset).filter((index) => index >= 0);
  const width = 300;
  const height = 76;
  const pad = 10;
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
    points.push({ index, cx: x(index), cy: y(value) });
  });
  // Line first, dots on top, so every reading stays visible.
  const polyline = document.createElementNS(ns, "polyline");
  polyline.setAttribute("points",
    points.map((point) => `${point.cx.toFixed(1)},${point.cy.toFixed(1)}`).join(" "));
  polyline.setAttribute("class", "series");
  svg.appendChild(polyline);
  points.forEach((point, order) => {
    const isFlag = flagged.includes(point.index);
    const isLatest = order === points.length - 1;
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", String(point.cx));
    dot.setAttribute("cy", String(point.cy));
    dot.setAttribute("r", isFlag ? "6.5" : (isLatest ? "6" : "5"));
    dot.setAttribute("class", isFlag ? "dot flag" : (isLatest ? "dot latest" : "dot"));
    svg.appendChild(dot);
  });
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
  const last = data.sessions && data.sessions.length ? data.sessions.length - 1 : -1;
  const stamp = last >= 0 && data.recorded_at && data.recorded_at[last]
    ? `, recorded ${new Date(data.recorded_at[last]).toLocaleString([], {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}` : "";
  note.textContent = `Latest session${last >= 0
    ? ` (${sessionName(data.sessions[last])}${stamp})` : ""} of ${data.session_count}. `
    + "The big number is your latest reading. Each dot on the chart is one session.";
  box.append(heading, note);
  for (const measure of rows) box.appendChild(measureRow(measure));
  return box;
}

// Every saved session with its date and a delete control. Deleting is
// permanent, so it takes two presses: Delete, then Confirm delete.
function sessionsSection(data) {
  if (state.sample || !data.sessions || !data.sessions.length) return null;
  const box = document.createElement("div");
  box.className = "stable-list";
  const heading = document.createElement("h3");
  heading.textContent = "Your sessions";
  const note = document.createElement("p");
  note.className = "sub";
  note.textContent = `The first ${data.n_baseline} sessions are your baseline. Deleting `
    + "a session removes its recording, measurements and check-in from this computer "
    + "for good.";
  box.append(heading, note);
  data.sessions.forEach((session, index) => {
    const row = document.createElement("div");
    row.className = "session-row";
    const name = document.createElement("span");
    name.className = "session-name";
    name.textContent = sessionName(session);
    const when = document.createElement("span");
    when.className = "session-when";
    const stamp = data.recorded_at && data.recorded_at[index];
    when.textContent = (stamp ? shortDate(new Date(stamp), true) : "no saved date")
      + (index < data.n_baseline ? " · baseline" : "");
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary small";
    remove.textContent = "Delete";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "secondary small";
    cancel.textContent = "Cancel";
    cancel.hidden = true;
    cancel.addEventListener("click", () => {
      remove.textContent = "Delete";
      remove.classList.remove("danger");
      cancel.hidden = true;
    });
    remove.addEventListener("click", async () => {
      if (cancel.hidden) {                 // first press only arms the button
        remove.textContent = "Confirm delete";
        remove.classList.add("danger");
        cancel.hidden = false;
        return;
      }
      remove.disabled = true;
      cancel.disabled = true;
      try {
        await api(`/api/session?subject=${encodeURIComponent(data.subject)}`
          + `&session=${encodeURIComponent(session)}`, { method: "DELETE" });
        await loadReport();
        setStatus(`${sessionName(session)} deleted from this computer.`);
        suggestFlightDay();
      } catch (error) {
        setStatus(`Could not delete ${sessionName(session)}. (${error.message})`);
        remove.disabled = false;
        cancel.disabled = false;
      }
    });
    row.append(name, when, remove, cancel);
    box.appendChild(row);
  });
  return box;
}

function renderReport(data) {
  document.getElementById("report-headline").textContent = data.headline;
  document.getElementById("baseline-note").textContent = data.state === "baseline"
    ? `Your baseline is built from your first ${data.n_baseline} sessions.`
    : "Measured against your own baseline. Shaded band is one standard deviation; "
      + "the dashed line is your baseline average."
      + (data.session_count > RECENT_SESSIONS
        ? ` Charts show your last ${RECENT_SESSIONS} sessions; the Trends tab has all `
          + `${data.session_count}.` : "");
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
    const sessionList = sessionsSection(data);
    if (sessionList) list.appendChild(sessionList);
    return;
  }
  for (const finding of data.findings) {
    list.appendChild(findingRow(finding));
  }
  const within = measuresSection(data, "Within your baseline");
  if (within) list.appendChild(within);
  const sessionList = sessionsSection(data);
  if (sessionList) list.appendChild(sessionList);
  const footer = document.createElement("p");
  footer.className = "sub";
  footer.textContent = "This describes what changed, not why. Ordinary causes are the "
    + "common ones: a head cold, a different microphone, the time of day, the room. "
    + "Nothing here is a diagnosis.";
  list.appendChild(footer);
}

// ---- Trends: every measure over time, by session, week or month ----------

const trends = { data: null, group: "session" };

function formatValue(format, value) {
  if (value === null || value === undefined) return "not measured";
  if (format === "percent2") return `${(value * 100).toFixed(2)}%`;
  if (format === "percent1") return `${(value * 100).toFixed(1)}%`;
  if (format === "rate") return `${value.toFixed(1)}/s`;
  return `${value.toFixed(1)} ${format === "hz" ? "Hz" : "dB"}`;
}

function shortDate(date, withTime) {
  return date.toLocaleString([], withTime
    ? { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
    : { month: "short", day: "numeric" });
}

// Turn one measure's readings into chart points for the chosen grouping.
// Weekly and monthly points are averages; sessions without a date cannot be
// placed on a calendar, so they are left out of those two and counted.
function trendPoints(measure, data, group) {
  // Sessions the report flagged for this measure are drawn in the flag colour.
  const finding = (data.findings || []).find((item) => item.feature === measure.feature);
  const flaggedSessions = new Set(finding
    ? finding.flagged_indices.map((index) => data.sessions[index]) : []);
  const readings = measure.series.map((value, index) => ({
    value,
    session: data.sessions[index],
    when: data.recorded_at && data.recorded_at[index]
      ? new Date(data.recorded_at[index]) : null,
  })).filter((reading) => reading.value !== null);
  if (group === "session") {
    return {
      undated: 0,
      points: readings.map((reading) => ({
        value: reading.value,
        flagged: flaggedSessions.has(reading.session),
        label: sessionName(reading.session),
        tip: `${sessionName(reading.session)}${reading.when
          ? `, ${shortDate(reading.when, true)}` : ""}`,
      })),
    };
  }
  const buckets = new Map();
  let undated = 0;
  for (const reading of readings) {
    if (!reading.when) { undated += 1; continue; }
    const start = new Date(reading.when);
    start.setHours(0, 0, 0, 0);
    if (group === "week") start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    else start.setDate(1);
    const key = start.getTime();
    if (!buckets.has(key)) buckets.set(key, { start, values: [] });
    buckets.get(key).values.push(reading.value);
  }
  const points = Array.from(buckets.values())
    .sort((left, right) => left.start - right.start)
    .map((bucket) => {
      const label = group === "week"
        ? `Week of ${shortDate(bucket.start, false)}`
        : bucket.start.toLocaleString([], { month: "short", year: "numeric" });
      const count = bucket.values.length;
      return {
        value: bucket.values.reduce((sum, value) => sum + value, 0) / count,
        label,
        tip: `${label}, average of ${count} session${count === 1 ? "" : "s"}`,
      };
    });
  return { undated, points };
}

function trendChart(points, measure) {
  const ns = "http://www.w3.org/2000/svg";
  const width = 640;
  const height = 156;
  const pad = { left: 14, right: 14, top: 16, bottom: 26 };
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${measure.label} over time against the baseline band`);
  const values = points.map((point) => point.value);
  const mean = measure.baseline_mean;
  const sd = measure.baseline_sd || 0;
  const hasBaseline = measure.baseline_complete && mean !== null;
  const lo = Math.min(...values, hasBaseline ? mean - 2.5 * sd : Infinity);
  const hi = Math.max(...values, hasBaseline ? mean + 2.5 * sd : -Infinity);
  const span = hi - lo || 1;
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const x = (index) => pad.left + (points.length === 1
    ? innerW / 2 : index * innerW / (points.length - 1));
  const y = (value) => pad.top + innerH - (value - lo) * innerH / span;
  const add = (name, attrs, text) => {
    const node = document.createElementNS(ns, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text) node.textContent = text;
    svg.appendChild(node);
    return node;
  };
  if (hasBaseline) {
    add("rect", { x: 0, width, y: Math.min(y(mean + sd), y(mean - sd)),
                  height: Math.max(Math.abs(y(mean - sd) - y(mean + sd)), 1),
                  class: "band" });
    add("line", { x1: 0, x2: width, y1: y(mean), y2: y(mean), class: "meanline" });
  }
  // Fewer points get bigger dots; a long history gets small ones so the
  // shape of the line stays readable.
  const radius = points.length <= 16 ? 5.5 : points.length <= 30 ? 4
    : points.length <= 60 ? 3 : 2.2;
  if (points.length > 1) {
    add("polyline", { class: "series",
                      points: points.map((point, index) =>
                        `${x(index).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ") });
  }
  points.forEach((point, index) => {
    const isLatest = index === points.length - 1;
    const dot = add("circle", {
      cx: x(index), cy: y(point.value),
      r: point.flagged || isLatest ? radius + 1 : radius,
      "stroke-width": radius < 4 ? 1 : 2,
      class: point.flagged ? "dot flag" : (isLatest ? "dot latest" : "dot"),
    });
    const title = document.createElementNS(ns, "title");
    title.textContent = `${point.tip}: ${formatValue(measure.format, point.value)}`;
    dot.appendChild(title);
  });
  add("text", { x: pad.left, y: height - 6, class: "axis" }, points[0].label);
  if (points.length > 1) {
    add("text", { x: width - pad.right, y: height - 6, class: "axis",
                  "text-anchor": "end" }, points[points.length - 1].label);
  }
  return svg;
}

function renderTrends() {
  const data = trends.data;
  const list = document.getElementById("trends-list");
  const note = document.getElementById("trends-note");
  list.replaceChildren();
  note.textContent = "";
  for (const button of document.querySelectorAll(".trend-group")) {
    button.setAttribute("aria-pressed", String(button.dataset.group === trends.group));
  }
  if (!data || !data.measures || !data.measures.length) {
    note.textContent = "No sessions yet. Record your first check-in to begin.";
    return;
  }
  let undated = 0;
  for (const measure of data.measures) {
    const result = trendPoints(measure, data, trends.group);
    undated = Math.max(undated, result.undated);
    if (!result.points.length) continue;
    const box = document.createElement("div");
    box.className = "trend";
    const head = document.createElement("div");
    head.className = "trend-head";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = measure.label;
    const latest = document.createElement("span");
    latest.className = "latest";
    latest.textContent = formatValue(measure.format,
                                     result.points[result.points.length - 1].value);
    const values = result.points.map((point) => point.value);
    const range = document.createElement("span");
    range.className = "range";
    range.textContent = `lowest ${formatValue(measure.format, Math.min(...values))}`
      + ` · highest ${formatValue(measure.format, Math.max(...values))}`
      + (measure.baseline_complete && measure.baseline_text
        ? ` · baseline ${measure.baseline_text}` : "");
    head.append(label, latest, range);
    box.append(head, trendChart(result.points, measure));
    list.appendChild(box);
  }
  const count = data.session_count;
  const parts = [`${count} session${count === 1 ? "" : "s"} for ${data.subject}.`,
                 "Hover over a point for its date and value."];
  if (undated) {
    parts.push(`${undated} earlier session${undated === 1 ? " has" : "s have"} no saved `
      + "date, so weekly and monthly averages leave "
      + `${undated === 1 ? "it" : "them"} out.`);
  }
  if (!list.children.length) parts.push("Nothing to chart for this grouping yet.");
  note.textContent = parts.join(" ");
}

async function openTrends() {
  const input = document.getElementById("subject");
  const subject = input.value.trim().toUpperCase();
  if (!state.sample && !SUBJECT_RE.test(subject)) {
    showState("record");
    showRecordError("Enter a crew member to open their trends (for example AMANDA).");
    input.focus();
    return;
  }
  clearRecordError();
  if (!state.sample) state.subject = subject;
  showState("trends");
  setStatus("Loading your trends...");
  try {
    trends.data = await fetchReport();
    renderTrends();
    setStatus("");
  } catch (error) {
    setStatus(`${ERROR_COPY.report} (${error.message})`);
  }
}

async function loadReport() {
  const refresh = document.getElementById("report-refresh");
  refresh.disabled = true;
  setStatus("Building your report...");
  try {
    const data = await fetchReport();
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
document.getElementById("take-stop").addEventListener("click", () => {
  if (state.recording) state.stopTake = true;
});

for (const button of document.querySelectorAll(".take-button")) {
  button.addEventListener("click", () => startTake(button.dataset.take));
}
document.getElementById("nav-record").addEventListener("click", () => showState("record"));
document.getElementById("sample-on").addEventListener("click", () => {
  setSample(true);
  openReport();
});
document.getElementById("sample-off").addEventListener("click", () => {
  setSample(false);
  showState("record");
});
document.getElementById("nav-report").addEventListener("click", openReport);
document.getElementById("nav-trends").addEventListener("click", openTrends);
for (const button of document.querySelectorAll(".trend-group")) {
  button.addEventListener("click", () => {
    trends.group = button.dataset.group;
    renderTrends();
  });
}
document.getElementById("retry-upload").addEventListener("click", retryUpload);
document.getElementById("subject").addEventListener("input", clearRecordError);
document.getElementById("subject").addEventListener("change", suggestFlightDay);
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
if (STATIC_PREVIEW) {
  // No local pipeline here: open straight onto the sample and lock recording.
  setSample(true);
  for (const button of document.querySelectorAll(".take-button")) button.disabled = true;
  openReport();
} else {
  suggestFlightDay();
}
