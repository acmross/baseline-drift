"""
Baseline Drift: the daily check-in conversation.

Runs entirely on the habitat machine. Two backends:

  --backend none    scripted prompts, keyword extraction. No model, no network,
                    no dependencies. Always works. Use this as the fallback.
  --backend ollama  a small local model (default llama3.2:3b) phrases the
                    questions and extracts structured answers. Still offline.

The model is deliberately given two narrow jobs: ask the questions in a
natural way, and turn free-text answers into fixed fields. It is never asked
to interpret symptoms, give advice, or say what anything means. A 3B model is
reliable at slot-filling and unreliable at clinical reasoning, so the
constraint is both a safety choice and an engineering one.

Writes one JSON record per session to context.jsonl, which voice_drift.py
reads to decide whether a detected drift already has a mundane explanation.

Usage:
    python3 checkin_agent.py <subject> <session_label> [--backend none|ollama]
"""
import sys, json, argparse, subprocess, re

# Each question maps to a field. `explains` lists the acoustic features that a
# yes could plausibly account for. Empty means: record it, but never let it
# suppress a finding. Upper-respiratory effects on voice quality are well
# established; sleep effects on rate and pausing are reasonably supported;
# pain has no established acoustic signature, so it is recorded in the crew
# member's own words and explains nothing.
QUESTIONS = [
    {"field": "cold_or_congestion",
     "ask": "Do you have a cold, congestion, or a sore throat today?",
     "type": "yesno",
     "explains": ["f0_mean_hz", "f0_sd_hz", "hnr_db", "jitter_local",
                  "shimmer_local", "intensity_db"]},
    {"field": "cough",
     "ask": "Any coughing?",
     "type": "yesno",
     "explains": ["hnr_db", "jitter_local", "shimmer_local"]},
    {"field": "sleep_hours",
     "ask": "Roughly how many hours did you sleep?",
     "type": "number",
     "explains": ["voiced_rate_hz", "pause_ratio", "intensity_db"]},
    # Tiredness is not only about last night: time of day, a meal, or a long
    # shift can do it. Asked separately so a full night's sleep does not hide it.
    {"field": "feeling_tired",
     "ask": "Do you feel tired or sleepy right now?",
     "type": "yesno",
     "explains": ["voiced_rate_hz", "pause_ratio", "intensity_db"]},
    {"field": "unusual_pain",
     "ask": "Any unusual pain or discomfort today? If so, where?",
     "type": "free",
     "explains": []},
    {"field": "posture",
     "ask": "Were you sitting, standing, reclined, or floating?",
     "type": "free",
     "explains": [],
     "note": "Sitting versus standing does not measurably change a healthy "
             "voice, so neither explains anything. Reclined and floating do: "
             "they change vocal tract geometry and respiratory kinematics. "
             "The parser below only licenses those two."},
    {"field": "setup_changed",
     "ask": "Are you using the same microphone and the same place as usual?",
     "type": "yesno_inverted",
     "explains": ["f0_mean_hz", "f0_sd_hz", "intensity_db", "hnr_db",
                  "jitter_local", "shimmer_local", "pause_ratio",
                  "voiced_rate_hz"]},
    {"field": "anything_else",
     "ask": "Anything else about how you're doing today that's worth recording?",
     "type": "free",
     "explains": []},
]

YES = re.compile(r"\b(yes|yeah|yep|yup|kinda|sort of|a little|slightly|some|bit)\b", re.I)
NO  = re.compile(r"\b(no|nope|nah|none|nothing|negative|all good|fine)\b", re.I)


def parse_plain(answer, qtype):
    a = (answer or "").strip()
    if qtype == "number":
        m = re.search(r"(\d+(?:\.\d+)?)", a)
        return float(m.group(1)) if m else None
    if qtype in ("yesno", "yesno_inverted"):
        # check NO first: "no cough" contains no clear yes token
        if NO.search(a) and not YES.search(a): val = False
        elif YES.search(a): val = True
        else: val = None
        if qtype == "yesno_inverted" and val is not None:
            val = not val      # "same setup? yes" means setup_changed = False
        return val
    return a or None


def ollama(prompt, model):
    """One-shot local generation. Returns None if Ollama is not reachable."""
    try:
        r = subprocess.run(["ollama", "run", model, prompt],
                           capture_output=True, text=True, timeout=90)
        return r.stdout.strip() if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def parse_with_model(answer, q, model):
    schema = {"yesno": "true, false, or null",
              "yesno_inverted": "true, false, or null",
              "number": "a number or null",
              "free": "a short string or null"}[q["type"]]
    prompt = (
        "Extract one field from a reply. Output ONLY raw JSON, no prose.\n"
        f'Question asked: "{q["ask"]}"\n'
        f'Their reply: "{answer}"\n'
        f'Return {{"value": <{schema}>}}. '
        "If the reply does not answer the question, value is null. "
        "Do not infer anything beyond what they said."
    )
    out = ollama(prompt, model)
    if not out: return parse_plain(answer, q["type"])
    m = re.search(r"\{.*\}", out, re.S)
    if not m: return parse_plain(answer, q["type"])
    try:
        val = json.loads(m.group(0)).get("value")
    except json.JSONDecodeError:
        return parse_plain(answer, q["type"])
    if q["type"] == "yesno_inverted" and isinstance(val, bool):
        val = not val
    return val


def phrase(q, model):
    """Let the local model vary the wording so six sessions do not feel identical."""
    out = ollama(
        "Rewrite this check-in question in one short, warm, natural sentence. "
        "Keep the exact same meaning. Ask nothing extra. Output only the question.\n"
        f"Question: {q['ask']}", model)
    return out.split("\n")[0].strip() if out else q["ask"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject"); ap.add_argument("session")
    ap.add_argument("--backend", choices=["none", "ollama"], default="none")
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--out", default="context.jsonl")
    args = ap.parse_args()

    use_model = args.backend == "ollama"
    if use_model and ollama("Reply with the single word: ok", args.model) is None:
        print("[Ollama unreachable, falling back to scripted prompts]\n")
        use_model = False

    print(f"Check-in for {args.subject}, session {args.session}.")
    print("Answer in your own words. Press enter to skip any question.\n")

    answers, explains = {}, {}
    for q in QUESTIONS:
        text = phrase(q, args.model) if use_model else q["ask"]
        try:
            reply = input(f"  {text}\n  > ")
        except EOFError:
            reply = ""
        val = parse_with_model(reply, q, args.model) if use_model else parse_plain(reply, q["type"])
        answers[q["field"]] = val
        answers[q["field"] + "_raw"] = reply.strip() or None
        # a true yes/no, or short sleep, licenses the features it can explain
        triggered = (val is True) or (q["type"] == "number" and val is not None and val < 6)
        if q["field"] == "posture" and isinstance(val, str):
            # only non-upright postures are licensed; sitting vs standing is not
            if re.search(r"reclin|lying|lie|supine|lay|float|微|weightless", val, re.I):
                triggered = True
                q = dict(q, explains=["f0_mean_hz", "f0_sd_hz", "intensity_db",
                                      "hnr_db", "pause_ratio"])
        if triggered and q["explains"]:
            for f in q["explains"]:
                explains.setdefault(f, []).append(q["field"])

    rec = {"subject": args.subject, "session": args.session,
           "answers": answers, "explains": explains,
           "backend": "ollama" if use_model else "none"}
    with open(args.out, "a") as fh:
        fh.write(json.dumps(rec) + "\n")

    print(f"\nRecorded to {args.out}.")
    if explains:
        print("Context that may account for voice changes this session:")
        for feat, reasons in explains.items():
            print(f"   {feat}: {', '.join(reasons)}")
    print("\nNothing here is a diagnosis. It is context for your own review.")


if __name__ == "__main__":
    main()
