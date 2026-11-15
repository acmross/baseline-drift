"use strict";

const state = {
  subject: "AMANDA",
  session: "day1",
  takes: {},
};

const TAKES = [
  { key: "vowel", label: "sustained \"ah\"", seconds: 5 },
  { key: "passage", label: "fixed passage", seconds: 45 },
  { key: "free", label: "free speech", seconds: 60 },
];

const COUNTDOWN_SECONDS = 3;
const SUBJECT_RE = /^[A-Z0-9][A-Z0-9-]{1,15}$/;
const SESSION_RE = /^[a-z0-9][a-z0-9-]{1,15}$/;

// One place for recovery copy so static contract tests can pin every path.
const ERROR_COPY = {
  microphone: "Microphone access was blocked or no microphone was found. "
    + "Allow microphone access in the browser, then press Start recording again.",
  validation: "The local pipeline rejected these takes (422 validation error). "
    + "The takes are still here; press Retry upload.",
  duplicate: "This session already exists on this machine. Continue to check-in "
    + "or open the report.",
  server: "The local pipeline could not store this session. "
    + "The takes are still here; press Retry upload.",
  questions: "Could not load check-in questions. Check that the local server is "
    + "running, then press Next or Skip to retry.",
  context: "Check-in save failed. Press Retry save.",
  report: "Could not build the report. Press Refresh to try again.",
};

function showState(name) {
  for (const id of ["record", "checkin", "report"]) {
    document.getElementById(id).hidden = id !== name;
  }
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

async function recordTake(task, maxSeconds) {
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

    await sleep(maxSeconds * 1000);
    recorder.stop();
    await stopped;

    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    const audio = await context.decodeAudioData(await blob.arrayBuffer());
    return encodeWav([audio.getChannelData(0)], audio.sampleRate);
  } finally {
    // Every exit path must release the microphone and decode context, or a
    // failed take leaves the browser holding the device.
    if (raf) cancelAnimationFrame(raf);
    if (recorder && recorder.state !== "inactive") recorder.stop();
    if (stream) stream.getTracks().forEach((track) => track.stop());
    if (context && context.state !== "closed") await context.close();
  }
}

function clearTakes() {
  state.takes = {};
}

async function uploadTakes() {
  const form = new FormData();
  form.append("subject", state.subject);
  form.append("session", state.session);
  for (const take of TAKES) {
    if (!state.takes[take.key]) throw new Error(`missing ${take.key} take`);
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
    + "press Start recording to try again.";
}

async function runSession() {
  const ids = readIds();
  if (!ids) return;
  state.subject = ids.subject;
  state.session = ids.session;
  clearTakes();
  const status = document.getElementById("take-status");
  const button = document.getElementById("record-start");
  const retry = document.getElementById("retry-upload");
  button.disabled = true;
  retry.hidden = true;
  status.textContent = "Get ready. You will record three takes.";
  try {
    for (const take of TAKES) {
      setPassageVisible(take.key === "passage");
      await runCountdown(COUNTDOWN_SECONDS, take.label);
      status.textContent = `Recording ${take.label} (${take.seconds}s)...`;
      state.takes[take.key] = await recordTake(take.key, take.seconds);
      status.textContent = `Captured ${take.label}.`;
    }
  } catch (error) {
    setPassageVisible(false);
    handleRecordingError(error);
    button.disabled = false;
    return;
  }
  setPassageVisible(false);
  status.textContent = "Uploading to the local pipeline...";
  try {
    await uploadTakes();
    status.textContent = "Session stored on this machine.";
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    handleUploadError(error);
  } finally {
    button.disabled = false;
  }
}

async function retryUpload() {
  if (!state.takes.vowel || !state.takes.passage) {
    document.getElementById("take-status").textContent =
      "No captured takes to upload. Press Start recording.";
    return;
  }
  const retry = document.getElementById("retry-upload");
  const status = document.getElementById("take-status");
  retry.disabled = true;
  status.textContent = "Retrying upload...";
  try {
    await uploadTakes();
    retry.hidden = true;
    status.textContent = "Session stored on this machine.";
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    handleUploadError(error);
  } finally {
    retry.disabled = false;
  }
}

const checkin = {
  questions: [],
  index: 0,
  answers: {},
  saveFailed: false,
};

function buildRaw() {
  const raw = {};
  for (const question of checkin.questions) {
    raw[question.field] = Object.prototype.hasOwnProperty.call(checkin.answers,
                                                               question.field)
      ? checkin.answers[question.field]
      : null;
  }
  return raw;
}

async function loadQuestions() {
  const next = document.getElementById("checkin-next");
  const skip = document.getElementById("checkin-skip");
  setStatus("Loading check-in questions...");
  try {
    checkin.questions = await api("/api/questions");
    checkin.index = 0;
    checkin.answers = {};
    checkin.saveFailed = false;
    next.textContent = "Next";
    skip.disabled = false;
    renderQuestion();
    setStatus("");
  } catch (error) {
    checkin.questions = [];
    checkin.index = 0;
    document.getElementById("question-label").textContent = "Questions did not load.";
    next.textContent = "Retry load";
    next.disabled = false;
    skip.disabled = false;
    setStatus(`${ERROR_COPY.questions} (${error.message})`);
  }
}

function renderQuestion() {
  const next = document.getElementById("checkin-next");
  const skip = document.getElementById("checkin-skip");
  const answer = document.getElementById("answer");
  const question = checkin.questions[checkin.index];
  next.textContent = "Next";
  next.disabled = false;
  skip.disabled = false;
  answer.disabled = false;
  if (!question) {
    document.getElementById("question-label").textContent = "All questions answered.";
    answer.disabled = true;
    next.disabled = true;
    skip.disabled = true;
    return;
  }
  document.getElementById("question-label").textContent = question.ask;
  answer.value = "";
  answer.type = "text";
  answer.focus();
}

function advanceCheckin(value) {
  const question = checkin.questions[checkin.index];
  if (question) checkin.answers[question.field] = value;
  checkin.index += 1;
  renderQuestion();
  return checkin.index >= checkin.questions.length;
}

async function finishCheckin() {
  const next = document.getElementById("checkin-next");
  const skip = document.getElementById("checkin-skip");
  next.disabled = true;
  setStatus("Saving check-in...");
  try {
    await api("/api/context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: state.subject, session: state.session, raw: buildRaw(),
      }),
    });
    checkin.saveFailed = false;
    next.textContent = "Next";
    next.disabled = true;
    skip.disabled = true;
    document.getElementById("question-label").textContent = "All questions answered.";
    document.getElementById("to-report").disabled = false;
    setStatus("Check-in stored. Open the report when ready.");
  } catch (error) {
    checkin.saveFailed = true;
    next.textContent = "Retry save";
    next.disabled = false;
    skip.disabled = true;
    document.getElementById("question-label").textContent = "Check-in not saved yet.";
    setStatus(`${ERROR_COPY.context} (${error.message})`);
  }
}

async function submitCheckin() {
  if (!checkin.questions.length) {
    await loadQuestions();
    return;
  }
  if (checkin.saveFailed) {
    await finishCheckin();
    return;
  }
  const question = checkin.questions[checkin.index];
  if (!question) return;
  const raw = document.getElementById("answer").value;
  const done = advanceCheckin(raw);
  if (done) await finishCheckin();
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
  detail.textContent = `${finding.value}${finding.unit} against your baseline of `
    + `${finding.baseline_mean}${finding.unit} · ${finding.run_length} `
    + `session${finding.run_length === 1 ? "" : "s"} running`
    + ` · baseline band ±${finding.baseline_sd}${finding.unit}`;
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

function stableFeatures(data) {
  if (!data.stable_features || !data.stable_features.length) return null;
  const box = document.createElement("div");
  box.className = "stable-list";
  const heading = document.createElement("h3");
  heading.textContent = "Stable this session";
  const list = document.createElement("p");
  list.className = "sub";
  list.textContent = data.stable_features.map((item) => item.label).join(" · ");
  box.append(heading, list);
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
    pending.textContent = `${data.headline} No findings are reported yet.`;
    list.appendChild(pending);
    return;
  }
  if (!data.findings.length) {
    const stable = document.createElement("p");
    stable.textContent = "Nothing moved far enough from your baseline to report.";
    list.appendChild(stable);
    const stableBox = stableFeatures(data);
    if (stableBox) list.appendChild(stableBox);
    return;
  }
  for (const finding of data.findings) {
    list.appendChild(findingRow(finding));
  }
  const stableBox = stableFeatures(data);
  if (stableBox) list.appendChild(stableBox);
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
document.getElementById("record-start").addEventListener("click", runSession);
document.getElementById("retry-upload").addEventListener("click", retryUpload);
document.getElementById("subject").addEventListener("input", clearRecordError);
document.getElementById("session-label").addEventListener("input", clearRecordError);
document.getElementById("checkin-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheckin();
});
document.getElementById("checkin-skip").addEventListener("click", async () => {
  if (!checkin.questions.length) {
    await loadQuestions();
    return;
  }
  if (checkin.saveFailed) return;
  const done = advanceCheckin(null);
  if (done) await finishCheckin();
});
document.getElementById("to-checkin").addEventListener("click", () => {
  showState("checkin");
  if (!checkin.questions.length) loadQuestions();
});
showState("record");
