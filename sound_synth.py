"""
Procedural sound for Ferry's Sandwiches.
Every sound effect and the background music are generated from scratch with numpy,
so there are no audio files and no third-party audio licenses to worry about.
"""
import numpy as np

SR = 22050


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def _to_stereo_bytes(mono, gain=0.9):
    mono = np.clip(mono * gain, -1, 1)
    pcm = (mono * 32767).astype(np.int16)
    return np.repeat(pcm[:, None], 2, axis=1).tobytes()


def _soft(x, k=3):
    """tiny moving-average low-pass to take the edge off (keeps it cozy)"""
    ker = np.ones(k) / k
    return np.convolve(x, ker, mode="same")


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t * decay)


def pluck(freq, dur, decay=7.0, bright=0.35, glide_to=None):
    n = int(SR * dur)
    t = np.arange(n) / SR
    if glide_to:
        f = np.linspace(freq, glide_to, n)
        ph = 2 * np.pi * np.cumsum(f) / SR
    else:
        ph = 2 * np.pi * freq * t
    w = np.sin(ph) + bright * np.sin(2 * ph) + bright * 0.4 * np.sin(3 * ph)
    env = np.exp(-t * decay) * np.minimum(1, t / 0.004)
    return _soft(w * env * 0.5)


def mix(parts, length):
    out = np.zeros(length)
    for start, snd in parts:
        i = int(start * SR)
        j = min(length, i + len(snd))
        if i < length:
            out[i:j] += snd[: j - i]
    return out


# ------------------------------------------------------------------ sound fx
def build_sfx():
    fx = {}
    scale = [72, 74, 76, 79, 81, 84]          # C major pentatonic, rising with the combo
    for i, m in enumerate(scale, start=1):
        a = mix([(0, pluck(midi(m), 0.22, decay=9)), (0, 0.5 * pluck(midi(m + 12), 0.15, decay=14))], int(SR * 0.22))
        fx[f"catch{i}"] = _to_stereo_bytes(a)
    fx["wrong"] = _to_stereo_bytes(pluck(300, 0.18, decay=10, glide_to=190, bright=0.15))
    bad = pluck(220, 0.35, decay=5, glide_to=70, bright=0.9)
    tt = np.arange(len(bad)) / SR
    bad = bad + 0.25 * np.sign(np.sin(2 * np.pi * 90 * tt)) * np.exp(-tt * 9)
    fx["bad"] = _to_stereo_bytes(_soft(bad, 5))
    fx["combo"] = _to_stereo_bytes(mix([(0.0, pluck(midi(84), 0.18, 10)), (0.07, pluck(midi(88), 0.18, 10)),
                                         (0.14, pluck(midi(91), 0.28, 8))], int(SR * 0.45)))
    arp = [72, 76, 79, 84]
    fx["sandwich"] = _to_stereo_bytes(mix([(i * 0.09, pluck(midi(m), 0.4, 6)) for i, m in enumerate(arp)], int(SR * 0.8)))
    win = [72, 72, 76, 79, 84, 79, 84]
    times = [0, 0.12, 0.24, 0.36, 0.52, 0.72, 0.84]
    fx["win"] = _to_stereo_bytes(mix([(t, pluck(midi(m), 0.55, 4)) for t, m in zip(times, win)], int(SR * 1.7)))
    lose = [67, 64, 60, 55]
    fx["lose"] = _to_stereo_bytes(mix([(i * 0.22, pluck(midi(m), 0.6, 4.5, bright=0.15)) for i, m in enumerate(lose)], int(SR * 1.5)))
    fx["click"] = _to_stereo_bytes(pluck(900, 0.05, decay=40, bright=0.1))
    return fx


# ------------------------------------------------------------ lo-fi instruments
def epiano(freq, dur, vel=1.0, decay=2.2):
    """soft electric-piano-ish tone: slow attack, gentle wobble, tremolo, muffled"""
    n = int(SR * dur)
    t = np.arange(n) / SR
    wobble = 1 + 0.002 * np.sin(2 * np.pi * 4.8 * t)              # a little tape flutter
    ph = 2 * np.pi * freq * np.cumsum(wobble) / SR
    tone = np.sin(ph) + 0.35 * np.sin(2 * ph) * np.exp(-t * 6) + 0.1 * np.sin(3 * ph) * np.exp(-t * 9)
    tone += 0.4 * np.sin(2 * np.pi * freq * 1.003 * t)             # detuned second voice for width
    trem = 1 - 0.12 * (0.5 + 0.5 * np.sin(2 * np.pi * 4.2 * t))
    return _soft(tone * _env(n, 0.015, decay) * trem * 0.33 * vel, 4)


def bass(freq, dur, vel=1.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    ph = 2 * np.pi * freq * t
    w = np.sin(ph) + 0.25 * np.sin(2 * ph) * np.exp(-t * 4)
    return w * _env(n, 0.008, 2.6) * 0.55 * vel


def kick(vel=1.0):
    n = int(SR * 0.25)
    t = np.arange(n) / SR
    f = 46 + 95 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 13) * 0.9 * vel


def snare(rng, vel=1.0):
    n = int(SR * 0.18)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    body = _soft(noise, 3) - _soft(noise, 12)                      # rough band-pass
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30)
    return (body * np.exp(-t * 22) * 0.6 + tone * 0.35) * 0.6 * vel


def hat(rng, vel=1.0, dur=0.035):
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = rng.uniform(-1, 1, n)
    return (noise - _soft(noise, 6)) * np.exp(-t * 90) * 0.22 * vel


def crackle(rng, length):
    """vinyl dust: sparse soft clicks plus a whisper of hiss"""
    out = np.zeros(length)
    idx = rng.choice(length, size=length // 900, replace=False)
    out[idx] = rng.uniform(-1, 1, len(idx)) * rng.uniform(0.2, 1, len(idx))
    hiss = _soft(rng.uniform(-1, 1, length), 2) * 0.012
    return _soft(out, 3) * 0.06 + hiss


# --------------------------------------------------------------------- music
def build_music(bpm=76, bars=8):
    """A lazy lo-fi loop: swung hats, soft kick and snare, warm e-piano 7th chords,
    a round bass and a sparse melody, with a little vinyl crackle on top."""
    rng = np.random.default_rng(11)
    beat = 60.0 / bpm
    swing = 0.09 * beat                                  # off-beat eighths land a little late
    total = bars * 4 * beat
    tail = 2.5                                           # let notes ring across the loop point
    length = int(SR * (total + tail))
    parts = []
    # Cmaj7 - Am7 - Dm7 - G7 (I vi ii V), bass root + four chord tones
    prog = [(48, [60, 64, 67, 71]), (45, [57, 60, 64, 67]), (50, [62, 65, 69, 72]), (43, [59, 62, 65, 67])]
    penta = [72, 74, 76, 79, 81, 84, 86]
    for bar in range(bars):
        root, chord = prog[bar % len(prog)]
        t0 = bar * 4 * beat
        # e-piano: a full chord on beat 1, softer ones on the 'and' of 2 and on beat 4
        for tm, vel in ((0.0, 1.0), (1.5 * beat + swing, 0.6), (3.0 * beat, 0.7)):
            for k, m in enumerate(chord):
                parts.append((t0 + tm + k * 0.014, epiano(midi(m), beat * 2.2, vel * 0.8)))
        # bass: root on 1, again on the 'and' of 2, a passing fifth/fourth on the 'and' of 3
        parts.append((t0, bass(midi(root), beat * 1.2)))
        parts.append((t0 + 2.5 * beat + swing, bass(midi(root), beat * 0.9, 0.7)))
        parts.append((t0 + 3.5 * beat + swing, bass(midi(root + (7 if bar % 2 == 0 else 5)), beat * 0.6, 0.5)))
        # drums: kick on 1 and the 'and' of 2, snare on 2 and 4, swung eighth hats
        kicks = [0.0, 2.5] + ([3.75] if bar % 2 == 1 else [])
        for b in kicks:
            parts.append((t0 + b * beat + (swing if b % 1 else 0), kick(0.95 if b == 0 else 0.75)))
        for b in (1.0, 3.0):
            parts.append((t0 + b * beat, snare(rng)))
        for e in range(8):
            tm = e * beat / 2 + (swing if e % 2 else 0)
            parts.append((t0 + tm, hat(rng, 0.9 if e % 2 == 0 else 0.5, 0.06 if e == 7 else 0.035)))
        # melody: two or three lazy notes every other bar, leaning on chord tones
        if bar % 2 == 1:
            for e in sorted(rng.choice(8, size=int(rng.integers(2, 4)), replace=False)):
                pool = [n for n in penta if (n % 12) in {x % 12 for x in chord}]
                note = int(rng.choice(pool if rng.random() < 0.7 else penta))
                parts.append((t0 + e * beat / 2 + (swing if e % 2 else 0), epiano(midi(note), beat * 2.0, 0.9, decay=1.8)))
    out = _soft(mix(parts, length), 5)                   # overall muffle, the lo-fi part
    out += crackle(rng, length)
    # fold the tail back onto the start so the loop is seamless
    n_loop = int(SR * total)
    loop = out[:n_loop].copy()
    ex = out[n_loop:]
    loop[: len(ex)] += ex
    peak = np.max(np.abs(loop)) or 1
    loop = loop / peak * 0.8
    return _to_stereo_bytes(loop, 0.9)
