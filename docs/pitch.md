Ok looked it over. Honestly I think health monitoring is the move

One flag, it says software specifically, so idk if we can get circuits into a suit by Sunday with you not here. Could we design the suit and build the software that reads from it? Suit in the pitch, software is the demo

My idea is voice check ins. And I looked it up, NASA already funded this exact thing, they ran speech AI on HERA (4 people locked in a habitat 45 days) and got 80-90% predicting crew cohesion off tone of voice. So we'd be building the astronaut facing version of something already validated

But we should NOT claim we detect mood, that's a real research problem and we have 2 days. Just compare each person to their own baseline and flag drift. "Vocal energy down, third day in a row," let them decide what it means. Easier to build, harder to poke holes in

I do audio to clinical report stuff in my lab so the pipeline I've done before, just for a different thing. We can record ourselves for demo data?

bridge2AI is a good find but we can't use it this weekend, credentialed access \+ DUA, takes days. Worth citing as related work though. It's also our answer if someone asks why we didn't: it's cross sectional and supervised, mostly one session per person, so it can't train a per person baseline. Different question than ours

Two gotchas: MediaRecorder gives Opus not WAV and Praat needs WAV, and the Python needs a little flask server on localhost. Both are in the spec

Build for laptop not phone, and absolutely no network calls, not even a font CDN. The whole pitch is that it runs offline

