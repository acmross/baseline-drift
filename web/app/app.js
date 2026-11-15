"use strict";

const state = {
  subject: "AMANDA",
  session: "day1",
  takes: {},
};

const TAKES = [
  { key: "vowel", label: "sustained \"ah\"", seconds: 5 },
  { key: "passage", label: "fixed passage", seconds: 30 },
  { key: "free", label: "free speech", seconds: 60 },
];

function showState(name) {
  for (const id of ["record", "checkin", "report"]) {
    document.getElementById(id).hidden = id !== name;
  }
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
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

async function recordTake(task, maxSeconds) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  analyser.fftSize = 2048;
  source.connect(analyser);

  const meter = document.querySelector("#level-meter span");
  const meterRoot = document.getElementById("level-meter");
  const data = new Uint8Array(analyser.fftSize);
  let raf = 0;
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

  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
  const stopped = new Promise((resolve) => { recorder.onstop = resolve; });
  recorder.start();

  await new Promise((resolve) => setTimeout(resolve, maxSeconds * 1000));
  recorder.stop();
  await stopped;
  cancelAnimationFrame(raf);
  stream.getTracks().forEach((track) => track.stop());

  const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
  const audio = await context.decodeAudioData(await blob.arrayBuffer());
  await context.close();
  return encodeWav([audio.getChannelData(0)], audio.sampleRate);
}

async function runSession() {
  state.subject = document.getElementById("subject").value.trim().toUpperCase();
  state.session = document.getElementById("session-label").value.trim().toLowerCase();
  const status = document.getElementById("take-status");
  const button = document.getElementById("record-start");
  button.disabled = true;
  try {
    for (const take of TAKES) {
      status.textContent = `Recording ${take.label} (${take.seconds}s)…`;
      state.takes[take.key] = await recordTake(take.key, take.seconds);
      status.textContent = `Captured ${take.label}.`;
    }
    status.textContent = "Uploading to the local pipeline…";
    const form = new FormData();
    form.append("subject", state.subject);
    form.append("session", state.session);
    for (const take of TAKES) {
      form.append(take.key, state.takes[take.key], `${state.session}_${take.key}.wav`);
    }
    await api("/api/session", { method: "POST", body: form });
    status.textContent = "Session stored on this machine.";
    document.getElementById("to-checkin").disabled = false;
  } catch (error) {
    status.textContent = `Recording failed: ${error.message}. Check microphone permission and try again.`;
    button.disabled = false;
  }
}

const checkin = { questions: [], index: 0, answers: {} };

function parseAnswer(type, raw) {
  const text = raw.trim();
  if (type === "yesno" || type === "yesno_inverted") {
    let value = null;
    if (/^(yes|yeah|yep|yup|true)/i.test(text)) value = true;
    else if (/^(no|nope|nah|false|none)/i.test(text)) value = false;
    if (type === "yesno_inverted" && value !== null) value = !value;
    return value;
  }
  if (type === "number") {
    const match = text.match(/-?\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }
  return text || null;
}

function buildAnswers() {
  return checkin.answers;
}

async function loadQuestions() {
  checkin.questions = await api("/api/questions");
  renderQuestion();
}

function renderQuestion() {
  const question = checkin.questions[checkin.index];
  if (!question) {
    document.getElementById("question-label").textContent = "All questions answered.";
    document.getElementById("answer").disabled = true;
    document.getElementById("checkin-next").disabled = true;
    document.getElementById("checkin-skip").disabled = true;
    return;
  }
  document.getElementById("question-label").textContent = question.ask;
  const answer = document.getElementById("answer");
  answer.value = "";
  answer.type = question.type === "number" ? "text" : "text";
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
  await api("/api/context", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject: state.subject, session: state.session, answers: buildAnswers(),
    }),
  });
  document.getElementById("to-report").disabled = false;
  setStatus("Check-in stored. Open the report when ready.");
}

async function submitCheckin() {
  const question = checkin.questions[checkin.index];
  if (!question) return;
  const raw = document.getElementById("answer").value;
  const done = advanceCheckin(parseAnswer(question.type, raw));
  if (done) await finishCheckin();
}

document.getElementById("record-start").addEventListener("click", runSession);
document.getElementById("checkin-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheckin();
});
document.getElementById("checkin-skip").addEventListener("click", async () => {
  if (!checkin.questions.length) return;
  const done = advanceCheckin(null);
  if (done) await finishCheckin();
});
document.getElementById("to-report").addEventListener("click", () => showState("report"));
document.getElementById("to-checkin").addEventListener("click", () => {
  showState("checkin");
  if (!checkin.questions.length) loadQuestions();
});
showState("record");
