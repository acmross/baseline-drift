"use strict";

const state = {
  subject: "AMANDA",
  session: "day1",
  takes: {},
  recording: false, // true while the microphone is in use
  saved: [],        // takes stored by the last save, until a new take is recorded
  sample: false,    // true while a read-only dataset is on screen
  dataset: "sample", // which read-only dataset: "sample" or "real"
};

// The online preview is the same page with no local pipeline behind it. A
// visitor can go through recording and the check-in, which stay in their
// browser and are not measured, and explore the read-only datasets.
const STATIC_PREVIEW = Boolean(window.BASELINE_DRIFT_STATIC);

// The hosted demo runs the real pipeline on a demo server so it can be tried
// without installing anything. That is the one place a recording leaves the
// device, so the privacy notice is replaced with exactly what happens to it.
const HOSTED_MINUTES = Number(window.BASELINE_DRIFT_HOSTED) || 0;
const WHERE = HOSTED_MINUTES
  ? `in your private demo space (deleted within ${HOSTED_MINUTES / 60} hours)` : "on this machine";
if (HOSTED_MINUTES) {
  const hours = HOSTED_MINUTES / 60;
  document.getElementById("masthead-sub").textContent =
    "Daily voice check-in · hosted demo";
  document.getElementById("subject").value = "GUEST";
  document.getElementById("privacy").classList.add("sample");
  document.getElementById("privacy-title").textContent =
    `Hosted demo. Everything you record here is deleted within ${hours} hours.`;
  document.getElementById("privacy-body").textContent =
    "This is the one version that sends your recording off your device: to measure "
    + "your voice it goes to our demo server. Your recordings, numbers and check-in "
    + "answers are kept under a random ID that only this browser has, so you can play "
    + "them back and delete them yourself. No one else can see or hear them, and all of "
    + `it is deleted automatically within ${hours} hours of when you started. The real `
    + "Baseline Drift runs on "
    + "your own computer and never sends anything anywhere.";
}

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
  if (STATIC_PREVIEW) {
    // In the preview the dataset banner belongs to the Report and Trends views.
    document.getElementById("sample-banner").hidden =
      !(name === "report" || name === "trends");
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
  if (STATIC_PREVIEW) {
    document.getElementById("session-label").value = "1";
    return;
  }
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
    await sleep(1000);
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
    const scope = document.getElementById("scope");
    const pen = scope.getContext("2d");
    const draw = () => {
      analyser.getByteTimeDomainData(data);
      let peak = 0;
      for (const value of data) peak = Math.max(peak, Math.abs(value - 128) / 128);
      const pct = Math.round(peak * 100);
      meter.style.width = `${pct}%`;
      meterRoot.setAttribute("aria-valuenow", String(pct));
      // Live trace of the voice, so it is obvious the microphone is hearing you.
      const { width, height } = scope;
      pen.clearRect(0, 0, width, height);
      pen.strokeStyle = "rgba(57, 135, 229, 0.25)";
      pen.lineWidth = 1;
      pen.beginPath();
      pen.moveTo(0, height / 2);
      pen.lineTo(width, height / 2);
      pen.stroke();
      pen.strokeStyle = "#5aa2f5";
      pen.lineWidth = 2;
      pen.beginPath();
      const step = Math.floor(data.length / width) || 1;
      for (let x = 0; x < width; x += 1) {
        const y = height / 2 + ((data[x * step] - 128) / 128) * (height / 2 - 4) * 1.6;
        if (x === 0) pen.moveTo(x, y); else pen.lineTo(x, y);
      }
      pen.stroke();
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
    const scope = document.getElementById("scope");
    scope.getContext("2d").clearRect(0, 0, scope.width, scope.height);
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
  status.textContent = HOSTED_MINUTES ? "Measuring your voice..." : "Saving to this machine...";
  try {
    if (STATIC_PREVIEW) await sleep(400);     // nothing is uploaded or measured
    else await uploadTakes(replace);
    status.textContent = STATIC_PREVIEW
      ? "In the full app your voice would be measured now, on your own computer. "
        + "In this preview your recording stayed in this browser tab and has been "
        + "discarded. Continue to check-in."
      : replace
      ? `${sessionName(state.session)} replaced ${WHERE}. Continue to check-in.`
      : `${sessionName(state.session)} saved ${WHERE}. Continue to check-in.`;
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
const readOnly = {};
async function fetchReport() {
  if (state.sample) {
    // Kept in memory so a preview deletion lasts until the page is reloaded.
    if (!readOnly[state.dataset]) {
      readOnly[state.dataset] = await api(
        state.dataset === "real" ? "real_report.json" : "sample_report.json");
    }
    return readOnly[state.dataset];
  }
  return api(`/api/report?subject=${encodeURIComponent(state.subject)}`);
}

const BANNER_COPY = {
  sample: ["Sample data. Not a real person.",
    "You are looking at a simulated crew member with made-up readings: 36 check-ins "
    + "across ten weeks, steady at first, then slower and more halting speech alongside "
    + "a reported cold. It is here so you can explore the Report and Trends views."],
  real: ["Real recordings from a team member.",
    "These are real check-ins recorded by a team member on her own laptop, measured "
    + "by the same pipeline. The numbers and dates are real; dates are published "
    + "without clock times. Her recordings and check-in answers are not published."],
};

function setDataset(name) {
  state.dataset = name;
  const [title, body] = BANNER_COPY[name];
  document.getElementById("sample-title").textContent = title;
  document.getElementById("sample-body").textContent = body;
  for (const button of document.querySelectorAll(".dataset")) {
    button.setAttribute("aria-pressed", String(button.dataset.dataset === name));
  }
}

function setSample(on) {
  state.sample = on;
  if (on && !STATIC_PREVIEW) setDataset("sample");
  document.getElementById("dataset-switch").hidden = !STATIC_PREVIEW;
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
    status.textContent = `Session saved ${WHERE}.`;
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
    if (STATIC_PREVIEW) {
      await sleep(300);
      save.textContent = "Save check-in";
      document.getElementById("to-report").disabled = false;
      setStatus("Check-in noted. In this preview nothing is stored or sent anywhere. "
        + "Open the report to see what a crew member gets back.");
      return;
    }
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
  const raw = last >= 0 && data.recorded_at && data.recorded_at[last];
  const stamp = raw
    ? `, recorded ${shortDate(parseStamp(raw), !dateOnly(raw))}` : "";
  note.textContent = `Latest session${last >= 0
    ? ` (${sessionName(data.sessions[last])}${stamp})` : ""} of ${data.session_count}. `
    + "The big number is your latest reading. Each dot on the chart is one session.";
  box.append(heading, note);
  for (const measure of rows) box.appendChild(measureRow(measure));
  return box;
}

// Every saved session with its date and a delete control. Deleting is
// permanent, so it takes two presses: Delete, then Confirm delete.
// Read-only data has no pipeline behind it, so a deletion only removes the
// session from what is on screen: its row and its point on every chart.
function dropFromReadOnly(data, index) {
  const [session] = data.sessions.splice(index, 1);
  if (data.recorded_at) data.recorded_at.splice(index, 1);
  if (data.details) delete data.details[session];
  const shift = (list) => list.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i));
  for (const measure of data.measures || []) measure.series.splice(index, 1);
  for (const finding of data.findings || []) {
    if (finding.series) finding.series.splice(index, 1);
    if (finding.flagged_indices) finding.flagged_indices = shift(finding.flagged_indices);
  }
  data.session_count = data.sessions.length;
}

// Sets the session the baseline begins at (or clears the choice with null) and
// redraws the report. Nothing is deleted: earlier sessions stay saved and listed.
async function moveBaseline(subject, session) {
  try {
    await api("/api/baseline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject, session }),
    });
    await loadReport();
    setStatus(session
      ? `Your baseline now starts at ${sessionName(session)}. Earlier sessions are kept `
        + "but are no longer part of it."
      : "Your baseline is your first sessions again.");
  } catch (error) {
    setStatus(`Could not change the baseline. (${error.message})`);
  }
}

// Which month groups are open, so the list keeps its shape when it is redrawn
// after a deletion or a refresh.
const openMonths = new Set();

// Asks before a session is deleted. Resolves true only on "Delete session";
// Cancel, Escape and closing the box all keep the session.
function confirmDelete(name) {
  const box = document.getElementById("confirm-delete");
  document.getElementById("confirm-delete-text").textContent =
    state.sample
      ? `Are you sure you want to delete ${name}? In the full app this removes its `
        + "recording, measurements and check-in for good. Here it only lasts until "
        + "you reload the page."
      : `Are you sure you want to delete ${name}? Its recording, measurements and `
        + `check-in will be removed ${HOSTED_MINUTES ? "from the demo server" : "from this computer"} for good.`;
  return new Promise((resolve) => {
    box.returnValue = "";
    box.addEventListener("close", () => resolve(box.returnValue === "delete"), { once: true });
    box.showModal();
  });
}

// One saved session opened in place: its takes to listen to, the numbers
// measured from it, and the check-in answers given with it.
const TAKE_TITLES = { vowel: 'Sustained "ah"', passage: "Fixed passage", free: "Free speech" };
function sessionDetail(info, query) {
  const wrap = document.createElement("div");
  const part = (title) => {
    const h = document.createElement("h4");
    h.textContent = title;
    wrap.appendChild(h);
  };
  const pair = (label, value) => {
    const line = document.createElement("div");
    line.className = "detail-line";
    const k = document.createElement("span");
    k.className = "k";
    k.textContent = label;
    const v = document.createElement("span");
    v.className = "v";
    if (typeof value === "string") v.textContent = value; else v.appendChild(value);
    line.append(k, v);
    wrap.appendChild(line);
  };
  part("Listen");
  if (!info.takes.length) pair("Audio", info.audio_note || "No audio saved for this session.");
  for (const take of info.takes) {
    const audio = document.createElement("audio");
    audio.className = "take-audio";
    audio.controls = true;
    audio.preload = "none";
    audio.src = `/api/audio?${query}&take=${take}`;
    pair(TAKE_TITLES[take] || take, audio);
  }
  part("Measurements");
  for (const measure of info.measures) pair(measure.label, measure.value_text);
  part("Check-in");
  if (!info.checkin) pair("Check-in", info.checkin_note || "No check-in saved for this session.");
  else for (const item of info.checkin) pair(item.ask, item.answer);
  return wrap;
}

function sessionsSection(data) {
  if (!data.sessions || !data.sessions.length) return null;
  const box = document.createElement("div");
  box.className = "stable-list";
  const heading = document.createElement("h3");
  heading.textContent = "Your sessions";
  const note = document.createElement("p");
  note.className = "sub";
  note.textContent = (data.baseline_moved
    ? `Your baseline is the ${data.n_baseline} sessions starting at ${sessionName(data.baseline_start)}. `
    : `The first ${data.n_baseline} sessions are your baseline. `)
    + "Sessions are grouped by month, newest first. Select a session to listen to it, "
    + "see its measurements and check-in, or start your baseline from it.";
  box.append(heading, note);
  if (data.baseline_moved && !state.sample) {
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "secondary small";
    reset.textContent = "Use my first sessions as the baseline again";
    reset.addEventListener("click", () => moveBaseline(data.subject, null));
    box.appendChild(reset);
  }
  // Newest first. index is the session's place among the scored sessions, or
  // -1 for one recorded before the chosen baseline.
  const stamps = data.recorded_at || [];
  const newestFirst = (data.earlier || [])
    .map((e) => ({ session: e.session, stamp: e.recorded_at, index: -1 }))
    .concat(data.sessions.map((session, index) => ({ session, stamp: stamps[index], index })))
    .reverse();
  // A long mission means hundreds of sessions, so they sit in one folding
  // group per month, under a year heading once there is more than one year.
  const groups = new Map();
  const years = new Set();
  for (const { stamp } of newestFirst) {
    if (stamp) years.add(parseStamp(stamp).getFullYear());
  }
  let lastYear = null;
  const groupFor = (stamp) => {
    const date = stamp ? parseStamp(stamp) : null;
    const key = date ? `${date.getFullYear()}-${date.getMonth()}` : "undated";
    if (groups.has(key)) return groups.get(key);
    if (date && years.size > 1 && date.getFullYear() !== lastYear) {
      lastYear = date.getFullYear();
      const year = document.createElement("h4");
      year.className = "year";
      year.textContent = String(lastYear);
      box.appendChild(year);
    }
    const group = document.createElement("details");
    group.className = "month";
    group.open = groups.size === 0 && openMonths.size === 0 ? true : openMonths.has(key);
    group.addEventListener("toggle", () => {
      if (group.open) openMonths.add(key); else openMonths.delete(key);
    });
    if (group.open) openMonths.add(key);
    const summary = document.createElement("summary");
    const title = document.createElement("span");
    title.className = "month-name";
    title.textContent = date
      ? date.toLocaleString([], years.size > 1 ? { month: "long" } : { month: "long", year: "numeric" })
      : "No saved date";
    const count = document.createElement("span");
    count.className = "month-count";
    summary.append(title, count);
    group.appendChild(summary);
    box.appendChild(group);
    const entry = { group, count, n: 0 };
    groups.set(key, entry);
    return entry;
  };
  newestFirst.forEach(({ session, index, stamp }) => {
    const row = document.createElement("div");
    row.className = "session-row";
    // The whole left side of the row opens the session; Delete sits alone.
    const view = document.createElement("button");
    view.type = "button";
    view.className = "session-open";
    view.setAttribute("aria-expanded", "false");
    const arrow = document.createElement("span");
    arrow.className = "session-arrow";
    arrow.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.className = "session-name";
    name.textContent = sessionName(session);
    const when = document.createElement("span");
    when.className = "session-when";
    when.textContent = stamp ? shortDate(parseStamp(stamp), !dateOnly(stamp)) : "no saved date";
    view.append(arrow, name, when);
    // Baseline sessions are marked in blue; ones before the baseline are dimmed.
    const isBaseline = index >= 0 && index < data.n_baseline;
    if (isBaseline || index < 0) {
      const badge = document.createElement("span");
      badge.className = isBaseline ? "badge baseline" : "badge earlier";
      badge.textContent = isBaseline ? "Baseline" : "Before your baseline";
      view.appendChild(badge);
      row.classList.add(isBaseline ? "is-baseline" : "is-earlier");
    }
    const detail = document.createElement("div");
    detail.className = "session-detail";
    detail.hidden = true;
    view.addEventListener("click", async () => {
      if (!detail.hidden) {
        detail.hidden = true;
        detail.replaceChildren();          // also stops any audio playing
        view.setAttribute("aria-expanded", "false");
        return;
      }
      view.disabled = true;
      try {
        const query = `subject=${encodeURIComponent(data.subject)}`
          + `&session=${encodeURIComponent(session)}`;
        const info = state.sample
          ? { ...data.details[session], audio_note: data.audio_note,
              checkin_note: data.checkin_note }
          : await api(`/api/session-detail?${query}`);
        detail.replaceChildren(sessionDetail(info, query));
        if (!state.sample && index !== 0) {
          // Re-setting the baseline deletes nothing; earlier sessions stay saved.
          const move = document.createElement("button");
          move.type = "button";
          move.className = "secondary small baseline-move";
          move.textContent = "Start my baseline from this session";
          move.addEventListener("click", () => moveBaseline(data.subject, session));
          detail.appendChild(move);
        }
        detail.hidden = false;
        view.setAttribute("aria-expanded", "true");
      } catch (error) {
        setStatus(`Could not open ${sessionName(session)}. (${error.message})`);
      } finally {
        view.disabled = false;
      }
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary small";
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      if (!(await confirmDelete(sessionName(session)))) return;
      if (state.sample) {
        dropFromReadOnly(data, index);
        renderReport(data);
        setStatus(`${sessionName(session)} removed from this view. In the full app the `
          + "report is rebuilt after a deletion; here it comes back when you reload.");
        return;
      }
      remove.disabled = true;
      try {
        await api(`/api/session?subject=${encodeURIComponent(data.subject)}`
          + `&session=${encodeURIComponent(session)}`, { method: "DELETE" });
        await loadReport();
        setStatus(`${sessionName(session)} deleted.`);
        suggestFlightDay();
      } catch (error) {
        setStatus(`Could not delete ${sessionName(session)}. (${error.message})`);
        remove.disabled = false;
      }
    });
    row.append(view, remove);
    const entry = groupFor(stamp);
    entry.group.append(row, detail);
    entry.n += 1;
    entry.count.textContent = entry.n === 1 ? "1 session" : `${entry.n} sessions`;
    if (isBaseline && !entry.marked) {
      // A folded month still shows that the baseline is inside it.
      entry.marked = true;
      const mark = document.createElement("span");
      mark.className = "badge baseline";
      mark.textContent = "Baseline";
      entry.count.before(mark);
    }
  });
  return box;
}

// Three numbers at the top of the report: how much there is to go on, and
// how many changes it found. Counts only, never an interpretation.
function renderStats(data) {
  const box = document.getElementById("report-stats");
  box.replaceChildren();
  box.hidden = data.state === "empty";
  if (box.hidden) return;
  const findings = data.findings || [];
  const open = findings.filter((f) => !(f.explained_by && f.explained_by.length)).length;
  const progress = data.baseline_progress || { have: 0, need: data.n_baseline };
  const tiles = [
    [String(data.total_sessions || data.session_count),
      (data.total_sessions || data.session_count) === 1 ? "check-in recorded" : "check-ins recorded", ""],
    [`${Math.min(progress.have, progress.need)} of ${progress.need}`,
      progress.have >= progress.need ? "baseline sessions, complete" : "baseline sessions so far", ""],
    [String(open), open === 1 ? "change without a reported explanation" : "changes without a reported explanation",
      open ? "flag" : ""],
    [String(findings.length - open), "explained by your check-in", ""],
  ];
  for (const [value, label, tone] of tiles) {
    const tile = document.createElement("div");
    tile.className = `stat ${tone}`.trim();
    const v = document.createElement("div");
    v.className = "stat-value";
    v.textContent = value;
    const l = document.createElement("div");
    l.className = "stat-label";
    l.textContent = label;
    tile.append(v, l);
    box.appendChild(tile);
  }
}

function renderReport(data) {
  renderStats(data);
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

// Published reports carry dates, not clock times. A bare "YYYY-MM-DD" parsed
// by Date() is UTC midnight and can render as the previous day west of
// Greenwich, so build those as local dates and leave the time off.
function dateOnly(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function parseStamp(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
  return match ? new Date(+match[1], +match[2] - 1, +match[3]) : new Date(value);
}

// Turn one measure's readings into chart points for the chosen grouping.
// Weekly and monthly points are averages; sessions without a date cannot be
// placed on a calendar, so they are left out of those two and counted.
function trendPoints(measure, data, group) {
  // Sessions the report flagged for this measure are drawn in the flag colour.
  const finding = (data.findings || []).find((item) => item.feature === measure.feature);
  const flaggedSessions = new Set(finding
    ? finding.flagged_indices.map((index) => data.sessions[index]) : []);
  const readings = measure.series.map((value, index) => {
    const raw = data.recorded_at && data.recorded_at[index];
    return {
      value,
      session: data.sessions[index],
      when: raw ? parseStamp(raw) : null,
      hasTime: raw ? !dateOnly(raw) : false,
    };
  }).filter((reading) => reading.value !== null);
  if (group === "session") {
    return {
      undated: 0,
      points: readings.map((reading) => ({
        value: reading.value,
        flagged: flaggedSessions.has(reading.session),
        label: sessionName(reading.session),
        tip: `${sessionName(reading.session)}${reading.when
          ? `, ${shortDate(reading.when, reading.hasTime)}` : ""}`,
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
  if (STATIC_PREVIEW) setDataset("sample");   // the walkthrough ends on the sample
  showState("report");
  loadReport();
});
document.getElementById("save-session").addEventListener("click", () => saveSession(false));
document.getElementById("replace-session").addEventListener("click", () => saveSession(true));

for (const button of document.querySelectorAll(".take-button")) {
  button.addEventListener("click", () => startTake(button.dataset.take));
}
document.getElementById("nav-record").addEventListener("click", () => {
  // Recording is always about your own data, so leaving the sample is implied.
  if (state.sample && !STATIC_PREVIEW) setSample(false);
  showState("record");
});
document.getElementById("sample-on").addEventListener("click", () => {
  setSample(true);
  openReport();
});
document.getElementById("sample-off").addEventListener("click", () => {
  // Stay on the tab you were reading; only the data behind it changes.
  const onTrends = !document.getElementById("trends").hidden;
  const onReport = !document.getElementById("report").hidden;
  setSample(false);
  if (onTrends) openTrends();
  else if (onReport) openReport();
  else showState("record");
});
for (const button of document.querySelectorAll(".dataset")) {
  button.addEventListener("click", () => {
    setDataset(button.dataset.dataset);
    if (document.getElementById("trends").hidden) openReport(); else openTrends();
  });
}
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
  // No local pipeline here: open on the sample report. Recording and the
  // check-in can still be tried; they stay in this browser tab.
  document.getElementById("subject").value = "GUEST";
  suggestFlightDay();
  setDataset("sample");
  setSample(true);
  openReport();
} else {
  suggestFlightDay();
}
