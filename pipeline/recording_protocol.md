# Baseline Drift: recording protocol

Every session is the same three tasks in the same order. Changing the tasks
changes the features and corrupts the baseline, so this does not vary.

Three sessions build the baseline. Everything after that is scored against it.

---

## Task 1: sustained vowel (about 5 seconds)

Take a normal breath and hold "ah" at a comfortable, steady pitch and volume
until you run out of comfortable breath. Do not push for volume or try to hold
it longer than feels natural.

This task carries jitter, shimmer and harmonic-to-noise ratio. Those three
features need steady phonation to measure cleanly, and connected speech is too
variable to give them reliably.

Save as `<session>_vowel.wav`.

## Task 2: the fixed passage (about 30 seconds)

Read this aloud at your normal speaking pace. Same passage every session.

> The quiet harbor fills with morning light before the first boats move. A low
> fog rests over the water, and the air holds the smell of salt and old rope.
> Someone is singing on the far dock, though the words are hard to catch. Three
> gulls argue above a crate of fish, then scatter when the engine coughs awake.
> By seven the channel is busy, the fog is thinning, and the long gray shape of
> the bridge begins to show against the sky.

This passage is original and written for this task. It is 84 words, about 33
seconds at a normal pace, and it is built for three properties:

- **Broad phonetic coverage.** All vowel classes, voiced and voiceless stops,
  the main fricatives, nasals, liquids and affricates. Narrow coverage would
  make the features sensitive to which sounds happened to appear.
- **Emotionally neutral content.** Prosody follows meaning. A passage about
  anything charged would move pitch and rate on its own and contaminate the
  measurement.
- **No proper nouns, no tongue twisters.** It has to read identically on a
  tired day, or the reading itself becomes the variable.

This task carries speech rate, pause ratio and F0 range.

Save as `<session>_passage.wav`.

## Task 3: free speech (about 60 seconds)

Answer the same prompt every session:

> Describe what you have done since your last check-in.

Talk continuously for roughly a minute. Content does not matter; continuity
does. This is the ecological sample, and it is where the check-in conversation
sits once the agent is wired in.

Save as `<session>_free.wav`.

---

## Recording settings

Mono, 16 kHz or higher, WAV. Same device, same microphone, same room, same
approximate distance from the mic every time. Changing hardware mid-study
shifts every acoustic feature and looks exactly like drift.

Record at a consistent time of day if you can. This one is a sensible control
rather than something we verified: treat it as hygiene, not as a finding.

**Posture matters, but not the way you would guess.** Sitting versus standing
does not measurably change a healthy voice, so either is fine as long as you
pick one. Reclined, lying down and floating are different: they change vocal
tract geometry and respiratory kinematics, and they do move the numbers. The
check-in records posture and only lets the non-upright ones account for drift.

**And in flight, the baseline itself moves.** About 75% of ISS astronauts get
nasal congestion from the microgravity fluid shift, most of it in the first
week. That changes resonance and voice quality for everyone, not as an
illness but as adaptation. An Earth pre-flight baseline compared against
in-flight recordings would show every crew member permanently drifted on day
one. **The baseline has to be re-established in orbit after the adaptation
period settles.** This is the single most important operational consequence of
the whole design.

### macOS, with ffmpeg

    # list input devices once, note the number for your mic
    ffmpeg -f avfoundation -list_devices true -i ""

    # then, per task (replace :0 with your device number)
    ffmpeg -f avfoundation -i ":0" -ar 16000 -ac 1 -t 6  day1_vowel.wav
    ffmpeg -f avfoundation -i ":0" -ar 16000 -ac 1 -t 40 day1_passage.wav
    ffmpeg -f avfoundation -i ":0" -ar 16000 -ac 1 -t 70 day1_free.wav

### macOS, no ffmpeg

QuickTime Player, File, New Audio Recording. Save each task separately, then
convert:

    ffmpeg -i day1_passage.m4a -ar 16000 -ac 1 day1_passage.wav

If you have no converter at all, `voice_features.py` will still read most
formats parselmouth supports, but WAV is the safe path.

---

## Running a session

    python3 voice_features.py AMANDA day1 day1_vowel.wav day1_passage.wav day1_free.wav
    python3 checkin_agent.py  AMANDA day1 --backend none

After three sessions:

    python3 voice_drift.py sessions.jsonl --context context.jsonl

---

## Before you trust any output: calibrate

Record the passage three times in a single sitting, minutes apart, with
nothing changed. Whatever spread you see across those three is your noise
floor. Set each `MIN_CHANGE` threshold in `voice_drift.py` above it.

Skipping this is how you end up with the OSD-575 false-positive problem: a
detector that fires on a quarter of everything it looks at.
