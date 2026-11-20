"""
Ferry's Sandwiches
A cozy catch-the-falling-ingredients game. Build the sandwich in the right order
before the timer runs out!

Run:   pip install pygame numpy
       python main.py

Controls: Left/Right arrows or A/D, or move the mouse / touch the screen.
          P or Esc = pause.
"""
import math
import os
import random
import sys

import numpy as np
import pygame

import sound_synth as synth

# ----------------------------------------------------------------- constants
W, H = 800, 600
LANE_W = 620                  # play area width (the right column holds the order ticket)
FPS = 60

# Order of the sandwich, bottom to top.
STAGES = ["bread", "salad", "ham", "cheese", "cucumber", "tomato", "breadontop"]
RECIPE = ["bread", "salad", "ham", "cheese", "cucumber", "tomato", "bread"]   # item needed for each stage
# What is on the plate after N correct catches: PLATES[N] (sprite ferry_<plate>_<mood>.png).
PLATES = ["empty"] + STAGES
GOOD = ["bread", "salad", "ham", "cheese", "cucumber", "tomato"]
BAD = ["bad_sock", "bad_egg", "bad_coin", "bad_sponge", "bad_banana"]
LABEL = {"bread": "Bread", "salad": "Lettuce", "ham": "Ham", "cheese": "Cheese",
         "cucumber": "Cucumber", "tomato": "Tomato"}

TARGET_SANDWICHES = 6         # win condition
START_TIME = 120.0            # seconds
MAX_TIME = 180.0
BAD_PENALTY = 5.0             # seconds lost for catching a junk item
SANDWICH_BONUS = 5.0          # seconds gained for finishing a sandwich
SCORE_GOOD = 10
SCORE_BAD = -10
SCORE_SANDWICH = 50
TIME_BONUS_PER_SEC = 5        # end-of-game bonus per second left (win only)

# Ferry sprite layout (the sprites are 276x360)
FERRY_TOP = 238
PLATE_CX = 98                 # x of plate centre inside the sprite
PLATE_HALF = 86               # half width of the catch area
CATCH_Y = FERRY_TOP + 190     # reference height for popups and sparkles
# y inside the sprite of the top of whatever is on the plate: items land there
PLATE_TOP = {"empty": 210, "bread": 199, "salad": 195, "ham": 195, "cheese": 193,
             "cucumber": 193, "tomato": 190, "breadontop": 181}
FERRY_MIN_X, FERRY_MAX_X = 100, LANE_W - 100

CREAM = (255, 243, 214)
BROWN = (122, 75, 42)
DARK = (70, 42, 28)
TOMATO = (229, 83, 61)
LETTUCE = (139, 195, 74)
PINK = (255, 199, 214)
GOLD = (255, 205, 60)

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")


# ------------------------------------------------------------------- helpers
def draw_text(surf, font, s, color, pos, anchor="center", outline=DARK, ow=2):
    base = font.render(s, True, color)
    r = base.get_rect(**{anchor: pos})
    if outline:
        edge = font.render(s, True, outline)
        for dx, dy in ((-ow, 0), (ow, 0), (0, -ow), (0, ow), (-ow, -ow), (ow, ow), (-ow, ow), (ow, -ow)):
            surf.blit(edge, r.move(dx, dy))
    surf.blit(base, r)
    return r


def draw_panel(surf, rect, fill=CREAM, border=BROWN, radius=18, alpha=235, shadow=True):
    rect = pygame.Rect(rect)
    if shadow:
        sh = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 70), sh.get_rect(), border_radius=radius)
        surf.blit(sh, rect.move(4, 6))
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*fill, alpha), s.get_rect(), border_radius=radius)
    pygame.draw.rect(s, border, s.get_rect(), width=4, border_radius=radius)
    surf.blit(s, rect)


def nine_slice(img, size, border, scale=1.0):
    """Stretch a UI-pack piece to `size` while keeping its corners intact.
    `border` = (left, top, right, bottom) in source pixels; the piece is first scaled
    uniformly by `scale` so the corners and the header strip keep their proportions."""
    if scale != 1.0:
        img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * scale)),
                                                 max(1, int(img.get_height() * scale))))
        border = tuple(int(b * scale) for b in border)
    l, t, r, b = border
    sw, sh = img.get_size()
    w, h = max(int(size[0]), l + r + 1), max(int(size[1]), t + b + 1)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    cols = [(0, l, 0, l), (l, sw - l - r, l, w - l - r), (sw - r, r, w - r, r)]
    rows = [(0, t, 0, t), (t, sh - t - b, t, h - t - b), (sh - b, b, h - b, b)]
    for sx, sws, dx, dws in cols:
        for sy, shs, dy, dhs in rows:
            if min(sws, shs, dws, dhs) <= 0:
                continue
            piece = img.subsurface((sx, sy, sws, shs))
            if (sws, shs) != (dws, dhs):
                piece = pygame.transform.smoothscale(piece, (dws, dhs))
            out.blit(piece, (dx, dy))
    return out


def fmt_time(t):
    t = max(0, t)
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def make_font(size, bold=True):
    for name in ("Baloo 2", "Fredoka", "Nunito", "Quicksand", "Comic Neue", "Trebuchet MS", "Verdana"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, int(size * 1.15))


# --------------------------------------------------------------------- assets
class Assets:
    def __init__(self):
        self.bg = pygame.image.load(os.path.join(ASSETS, "bg", "diner.jpg")).convert()
        self.ferry = {}
        for st in PLATES:
            for mood in ("neutral", "happy", "confused"):
                p = os.path.join(ASSETS, "ferry", f"ferry_{st}_{mood}.png")
                self.ferry[(st, mood)] = pygame.image.load(p).convert_alpha()
        self.items = {}
        for k in GOOD + BAD:
            img = pygame.image.load(os.path.join(ASSETS, "items", f"{k}.png")).convert_alpha()
            self.items[k] = pygame.transform.smoothscale(img, (60, 60))
        # small versions for the ticket
        self.mini = {k: pygame.transform.smoothscale(self.items[k], (34, 34)) for k in GOOD}
        # UI pieces from the Cozy UI Pack (dobo_ui), see CREDITS.txt
        self.ui = {}
        for name in ("button_white", "button_red", "button_wood", "round_white", "round_wood",
                     "card_red", "card_wood", "check_on", "check_off", "arrow_left", "arrow_right",
                     "cursor", "icon_bolt", "icon_alert"):
            self.ui[name] = pygame.image.load(os.path.join(ASSETS, "ui", f"{name}.png")).convert_alpha()
        self._cache = {}

    BUTTON_BORDER = (40, 40, 40, 50)      # pill buttons: round corners + bottom lip
    CARD_BORDER = (40, 92, 40, 42)        # cards: coloured header strip on top

    def sliced(self, name, size, border, scale):
        key = (name, int(size[0]), int(size[1]), round(scale, 3))
        if key not in self._cache:
            self._cache[key] = nine_slice(self.ui[name], size, border, scale)
        return self._cache[key]

    def button(self, style, size):
        """pill button ('white', 'red' or 'wood') stretched to size"""
        return self.sliced(f"button_{style}", size, self.BUTTON_BORDER, size[1] / 160)

    def card(self, style, size, scale=0.5):
        """card with a header strip ('red' or 'wood'); header is 92*scale px tall"""
        return self.sliced(f"card_{style}", size, self.CARD_BORDER, scale)

    def icon(self, name, h):
        """any UI piece scaled uniformly to height h"""
        key = (name, h)
        if key not in self._cache:
            img = self.ui[name]
            self._cache[key] = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * h / img.get_height())), h))
        return self._cache[key]


# --------------------------------------------------------------------- audio
class Audio:
    def __init__(self):
        self.ok = True
        self.music_level = 6
        self.sfx_level = 8
        self.muted = False
        try:
            self.sfx = {k: pygame.mixer.Sound(buffer=v) for k, v in synth.build_sfx().items()}
            self.music = pygame.mixer.Sound(buffer=synth.build_music())
            self.music_ch = pygame.mixer.Channel(0)
        except Exception as e:                      # no audio device etc. - game still works
            print("Audio disabled:", e)
            self.ok = False

    def start_music(self):
        if self.ok and not self.music_ch.get_busy():
            self.music_ch.play(self.music, loops=-1)
        self.apply()

    def apply(self):
        if not self.ok:
            return
        self.music_ch.set_volume(0 if self.muted else self.music_level / 10 * 0.8)

    def play(self, name, pitch=None):
        if not self.ok or self.muted or self.sfx_level == 0:
            return
        snd = self.sfx[name if pitch is None else f"{name}{pitch}"]
        snd.set_volume(self.sfx_level / 10)
        snd.play()


# ------------------------------------------------------------------ game objs
class Item:
    def __init__(self, kind, x, speed):
        self.kind = kind
        self.bad = kind in BAD
        self.x, self.y = x, -40.0
        self.vy = speed
        self.vx = 0.0
        self.rot = random.uniform(0, 360)
        self.spin = random.uniform(-70, 70)
        self.state = "fall"          # fall | bounce | land
        self.alpha = 255
        self.age = 0.0
        self.scale = 1.0


class Popup:
    def __init__(self, text, x, y, color):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.age, self.life = 0.0, 0.9


class Spark:
    def __init__(self, x, y, color):
        a = random.uniform(0, math.tau)
        sp = random.uniform(60, 220)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp - 120
        self.age, self.life = 0.0, random.uniform(0.35, 0.7)
        self.color = color
        self.r = random.randint(3, 6)


class Button:
    def __init__(self, label, action, rect):
        self.label, self.action, self.rect = label, action, pygame.Rect(rect)


# ----------------------------------------------------------------------- game
class Game:
    def __init__(self, screen, assets, audio):
        self.screen = screen
        self.canvas = pygame.Surface((W, H))
        self.a = assets
        self.audio = audio
        self.f_big = make_font(64)
        self.f_title = make_font(54)
        self.f_end = make_font(46)
        self.f_mid = make_font(34)
        self.f_small = make_font(24)
        self.f_tiny = make_font(19)
        self.clock = pygame.time.Clock()
        self.state = "title"
        self.focus = 0
        self.best = 0
        self.t_anim = 0.0
        self.buttons = []
        self.reset_run()
        self.set_state("title")
        self.audio.start_music()

    # ------------------------------------------------------------ state mgmt
    def reset_run(self):
        self.time_left = START_TIME
        self.elapsed = 0.0
        self.score = 0
        self.stage = 0
        self.sandwiches = 0
        self.combo = 0
        self.fx = LANE_W / 2
        self.target_x = self.fx
        self.mouse_mode = False
        self.items = []
        self.popups = []
        self.sparks = []
        self.spawn_t = 0.6
        self.since_needed = 0.0
        self.mood = "neutral"
        self.mood_t = 0.0
        self.celebrate_t = 0.0
        self.finishing = None        # 'win' once the final sandwich is built
        self.shake = 0.0
        self.bounce = 0.0
        self.final = {}

    def set_state(self, state):
        self.state = state
        self.focus = 0
        cx = W // 2
        if state == "title":
            bx = 590 - 130
            self.buttons = [Button("Play", "play", (bx, 330, 260, 56)),
                            Button("How to Play", "howto", (bx, 400, 260, 56)),
                            Button("Volume", "settings", (bx, 470, 260, 56))]
        elif state == "howto":
            self.buttons = [Button("Back", "title", (cx - 100, 524, 200, 50))]
        elif state == "settings":
            self.buttons = [Button("Back", "title", (cx - 100, 470, 200, 50))]
        elif state == "pause":
            self.buttons = [Button("Resume", "resume", (cx - 220, 468, 200, 54)),
                            Button("Quit to Title", "title", (cx + 20, 468, 200, 54))]
        elif state in ("win", "lose"):
            self.buttons = [Button("Play Again" if state == "win" else "Try Again", "play", (372, 496, 170, 54)),
                            Button("Title", "title", (558, 496, 170, 54))]
        else:
            self.buttons = []

    def has_settings(self):
        return self.state in ("settings", "pause")

    def focus_count(self):
        return (3 if self.has_settings() else 0) + len(self.buttons)

    def do(self, action):
        self.audio.play("click")
        if action == "play":
            self.reset_run()
            self.audio.start_music()
            self.set_state("play")
        elif action == "title":
            self.set_state("title")
        elif action in ("howto", "settings"):
            self.set_state(action)
        elif action == "resume":
            self.set_state("play")

    # ----------------------------------------------------------- settings UI
    def settings_rects(self):
        cx = W // 2
        top = 210 if self.state == "pause" else 200
        rows = []
        for i in range(3):
            rows.append(pygame.Rect(cx - 250, top + i * 62, 500, 52))
        r = {"rows": rows}
        for i, key in enumerate(("music", "sfx")):
            row = rows[i]
            r[key + "_minus"] = pygame.Rect(row.x + 200, row.y + 6, 40, 40)
            r[key + "_plus"] = pygame.Rect(row.right - 50, row.y + 6, 40, 40)
        r["mute"] = pygame.Rect(rows[2].x + 200, rows[2].y + 6, 100, 40)
        r["panel"] = pygame.Rect(cx - 270, top - 66, 540, 3 * 62 + 76)
        return r

    def adjust(self, which, d):
        a = self.audio
        if which == 0:
            a.music_level = max(0, min(10, a.music_level + d))
            a.apply()
        elif which == 1:
            a.sfx_level = max(0, min(10, a.sfx_level + d))
            a.play("click")
        elif which == 2 and d != 0:
            a.muted = not a.muted
            a.apply()

    # ---------------------------------------------------------------- events
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.WINDOWFOCUSLOST and self.state == "play":
            self.set_state("pause")
        if self.state == "play":
            return self.handle_play(ev)
        return self.handle_menu(ev)

    def handle_play(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_p):
                self.set_state("pause")
            elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                self.mouse_mode = False
        elif ev.type == pygame.MOUSEMOTION:
            self.mouse_mode = True
            self.target_x = ev.pos[0]
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if self.pause_rect().collidepoint(ev.pos):
                self.set_state("pause")
            else:
                self.mouse_mode = True
                self.target_x = ev.pos[0]
        elif ev.type in (pygame.FINGERDOWN, pygame.FINGERMOTION):
            self.mouse_mode = True
            self.target_x = ev.x * W
        return True

    def handle_menu(self, ev):
        n = self.focus_count()
        sr = self.settings_rects() if self.has_settings() else None
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_DOWN, pygame.K_s):
                self.focus = (self.focus + 1) % n
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.focus = (self.focus - 1) % n
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                if sr and self.focus < 3:
                    self.adjust(self.focus, -1)
                elif not sr or self.focus >= 3:
                    self.focus = (self.focus - 1) % n if len(self.buttons) > 1 else self.focus
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                if sr and self.focus < 3:
                    self.adjust(self.focus, +1)
                elif not sr or self.focus >= 3:
                    self.focus = (self.focus + 1) % n if len(self.buttons) > 1 else self.focus
            elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.activate(self.focus)
            elif ev.key == pygame.K_ESCAPE:
                if self.state == "pause":
                    self.do("resume")
                elif self.state != "title":
                    self.do("title")
        elif ev.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self.buttons):
                if b.rect.collidepoint(ev.pos):
                    self.focus = i + (3 if sr else 0)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if sr:
                for i, key in enumerate(("music", "sfx")):
                    if sr[key + "_minus"].collidepoint(ev.pos):
                        self.adjust(i, -1)
                    if sr[key + "_plus"].collidepoint(ev.pos):
                        self.adjust(i, +1)
                if sr["mute"].collidepoint(ev.pos):
                    self.adjust(2, 1)
            for i, b in enumerate(self.buttons):
                if b.rect.collidepoint(ev.pos):
                    self.activate(i + (3 if sr else 0))
        return True

    def activate(self, idx):
        off = 3 if self.has_settings() else 0
        if idx < off:
            if idx == 2:
                self.adjust(2, 1)
            return
        self.do(self.buttons[idx - off].action)

    def pause_rect(self):
        return pygame.Rect(W - 92, 514, 72, 72)

    # ---------------------------------------------------------------- update
    def speed(self):
        base = 150 * (1.1 ** self.sandwiches) * (1 + 0.0015 * self.elapsed)
        return min(base, 420)

    def bad_prob(self):
        if self.sandwiches == 0:
            return 0.0
        return min(0.33, 0.25 + 0.016 * (self.sandwiches - 1))

    def spawn(self):
        needed = self.needed()
        r = random.random()
        pb = self.bad_prob()
        if self.since_needed > 1.6:
            kind = needed
        elif r < pb:
            kind = random.choice(BAD)
        elif r < pb + 0.5:
            kind = needed
        else:
            kind = random.choice([g for g in GOOD if g != needed])
        if kind == needed:
            self.since_needed = 0.0
        x = random.uniform(45, LANE_W - 45)
        self.items.append(Item(kind, x, self.speed() * random.uniform(0.92, 1.08)))

    def set_mood(self, mood, t):
        self.mood, self.mood_t = mood, t

    def needed(self):
        """the item wanted next (bread again once an order is complete)"""
        return RECIPE[self.stage % len(RECIPE)]

    def plate(self, stage=None):
        """what is on the plate: PLATES[number of correct catches]"""
        stage = self.stage if stage is None else stage
        return PLATES[min(stage, len(PLATES) - 1)]

    def land_y(self):
        """screen y where a falling item meets the top of the sandwich"""
        return FERRY_TOP + PLATE_TOP[self.plate()]

    def burst(self, x, y, color, n=10):
        for _ in range(n):
            self.sparks.append(Spark(x, y, color))

    def update(self, dt):
        self.t_anim += dt
        if self.state != "play":
            return
        self.elapsed += dt
        keys = pygame.key.get_pressed()
        dirx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        if dirx:
            self.mouse_mode = False
            self.fx += dirx * 520 * dt
        elif self.mouse_mode:
            diff = self.target_x - self.fx
            step = 1000 * dt
            self.fx += max(-step, min(step, diff))
        self.fx = max(FERRY_MIN_X, min(FERRY_MAX_X, self.fx))

        if self.finishing is None:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.end_game(False)
                return

        self.mood_t -= dt
        if self.mood_t <= 0:
            self.mood = "neutral"
        if self.celebrate_t > 0:
            self.celebrate_t -= dt
            if self.celebrate_t <= 0:
                if self.finishing == "win":
                    self.end_game(True)
                    return
                self.stage = 0                       # fresh plate for the next order
        self.bounce = max(0.0, self.bounce - dt * 40)
        self.shake = max(0.0, self.shake - dt * 30)

        # spawning
        self.since_needed += dt
        if self.finishing is None:
            self.spawn_t -= dt
            if self.spawn_t <= 0:
                self.spawn()
                self.spawn_t = max(0.5, 0.8 - 0.05 * self.sandwiches) + random.uniform(-0.12, 0.12)

        # items
        for it in self.items[:]:
            if it.state == "fall":
                prev_bottom = it.y + 26
                it.y += it.vy * dt
                it.rot += it.spin * dt
                bottom = it.y + 26
                land = self.land_y()
                if (self.celebrate_t <= 0 and prev_bottom <= land <= bottom
                        and abs(it.x - self.fx) <= PLATE_HALF):
                    self.on_catch(it)
                    if it in self.items and it.state == "fall":
                        self.items.remove(it)
                    continue
                if it.y > H + 40:
                    if it.kind == self.needed() and self.combo:
                        self.combo = 0
                        self.popups.append(Popup("Missed!", it.x, H - 70, (255, 255, 255)))
                    self.items.remove(it)
            elif it.state == "land":  # settle onto the plate and melt into the sandwich
                it.age += dt
                k = min(1.0, it.age / 0.22)
                ease = min(1.0, 14 * dt)
                it.x += (self.fx - it.x) * ease
                it.y += (self.land_y() - 16 - it.y) * ease
                it.scale = 1 - 0.4 * k
                it.alpha = 255 * (1 - k * k)
                if k >= 1:
                    self.items.remove(it)
            else:  # bounce away
                it.vy += 900 * dt
                it.x += it.vx * dt
                it.y += it.vy * dt
                it.rot += it.spin * 3 * dt
                it.alpha = max(0, it.alpha - 380 * dt)
                if it.alpha <= 0 or it.y > H + 60:
                    self.items.remove(it)

        for p in self.popups[:]:
            p.age += dt
            p.y -= 40 * dt
            if p.age >= p.life:
                self.popups.remove(p)
        for s in self.sparks[:]:
            s.age += dt
            s.vy += 500 * dt
            s.x += s.vx * dt
            s.y += s.vy * dt
            if s.age >= s.life:
                self.sparks.remove(s)

    # --------------------------------------------------------------- catching
    def multiplier(self):
        return 3 if self.combo >= 6 else 2 if self.combo >= 3 else 1

    def on_catch(self, it):
        x, y = it.x, CATCH_Y
        if it.bad:
            self.combo = 0
            self.time_left = max(0, self.time_left - BAD_PENALTY)
            self.score = max(0, self.score + SCORE_BAD)
            self.set_mood("confused", 0.8)
            self.shake = 8
            self.audio.play("bad")
            self.popups.append(Popup(f"-{int(BAD_PENALTY)}s", x, y - 40, TOMATO))
            self.burst(x, y, (120, 120, 120), 6)
            it.state = "bounce"
            it.vx = random.choice((-1, 1)) * random.uniform(150, 260)
            it.vy = -280
            return
        if it.kind != self.needed():
            self.combo = 0
            self.set_mood("confused", 0.7)
            self.audio.play("wrong")
            self.popups.append(Popup(f"Need {LABEL[self.needed()].lower()}!", x, y - 40, (255, 255, 255)))
            it.state = "bounce"
            it.vx = random.choice((-1, 1)) * random.uniform(120, 220)
            it.vy = -300
            return
        # correct ingredient: it lands on the plate and the sandwich grows by one layer
        it.state = "land"
        it.vx, it.spin = 0.0, 0.0
        self.combo += 1
        gained = SCORE_GOOD * self.multiplier()
        self.score += gained
        self.stage += 1
        self.bounce = 6
        self.set_mood("happy", 0.7)
        self.audio.play("catch", min(self.combo, 6))
        self.popups.append(Popup(f"+{gained}", x, y - 40, GOLD))
        self.burst(x, y, GOLD, 8)
        if self.combo % 6 == 0:
            self.time_left = min(MAX_TIME, self.time_left + 3)
            self.popups.append(Popup("COMBO +3s!", self.fx, CATCH_Y - 110, LETTUCE))
            self.audio.play("combo")
        elif self.combo % 3 == 0:
            self.time_left = min(MAX_TIME, self.time_left + 2)
            self.popups.append(Popup("Combo +2s!", self.fx, CATCH_Y - 110, LETTUCE))
            self.audio.play("combo")
        if self.stage >= len(STAGES):
            self.complete_sandwich()

    def complete_sandwich(self):
        self.sandwiches += 1
        self.score += SCORE_SANDWICH
        self.time_left = min(MAX_TIME, self.time_left + SANDWICH_BONUS)
        self.popups.append(Popup(f"Sandwich {self.sandwiches}! +{SCORE_SANDWICH}", self.fx, CATCH_Y - 150, PINK))
        self.burst(self.fx, CATCH_Y - 40, PINK, 24)
        self.audio.play("sandwich")
        self.stage = len(STAGES)                # plate shows the finished sandwich while celebrating
        self.celebrate_t = 1.0
        self.set_mood("happy", 1.0)
        if self.sandwiches >= TARGET_SANDWICHES:
            self.finishing = "win"

    def end_game(self, won):
        bonus = int(self.time_left) * TIME_BONUS_PER_SEC if won else 0
        self.final = {"won": won, "score": self.score + bonus, "bonus": bonus,
                      "sandwiches": self.sandwiches, "time_left": self.time_left, "stage": self.stage}
        self.best = max(self.best, self.final["score"])
        self.audio.play("win" if won else "lose")
        self.set_state("win" if won else "lose")

    # ------------------------------------------------------------------ draw
    def ferry_img(self, stage, mood):
        return self.a.ferry[(self.plate(stage), mood)]

    def draw_world(self, s, shake=True):
        s.blit(self.a.bg, (0, 0))
        # soft dark gradient at top for HUD readability
        veil = pygame.Surface((W, 70), pygame.SRCALPHA)
        for y in range(70):
            veil.fill((30, 18, 10, int(120 * (1 - y / 70))), (0, y, W, 1))
        s.blit(veil, (0, 0))
        # right column backdrop
        col = pygame.Surface((W - LANE_W, H), pygame.SRCALPHA)
        col.fill((60, 36, 24, 150))
        s.blit(col, (LANE_W, 0))

    def draw_ferry(self, s, x, y_off=0, stage=None, mood=None, scale=1.0, top=None):
        stage = self.stage if stage is None else stage
        mood = self.mood if mood is None else mood
        img = self.ferry_img(stage, mood)
        if scale != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
        bob = math.sin(self.t_anim * 3.0) * 2
        px = x - PLATE_CX * scale
        py = (FERRY_TOP if top is None else top) + y_off + bob
        s.blit(img, (px, py))

    def draw_items(self, s, states):
        for it in self.items:
            if it.state not in states:
                continue
            rot = pygame.transform.rotozoom(self.a.items[it.kind], it.rot, it.scale)
            if it.state != "fall":
                rot.set_alpha(int(it.alpha))
            s.blit(rot, rot.get_rect(center=(it.x, it.y)))

    def draw_play(self, s):
        self.draw_world(s)
        # plate catch indicator (soft glow under the plate when an item is near)
        self.draw_items(s, ("fall", "bounce"))
        stage = self.stage
        mood = self.mood
        if self.celebrate_t > 0:
            stage = len(STAGES)
        self.draw_ferry(s, self.fx, y_off=self.bounce * 0.6, stage=stage, mood=mood)
        self.draw_items(s, ("land",))               # landing items sit on top of the sandwich
        for sp in self.sparks:
            a = max(0, 1 - sp.age / sp.life)
            pygame.draw.circle(s, sp.color, (int(sp.x), int(sp.y)), max(1, int(sp.r * a)))
        for p in self.popups:
            a = 1 - p.age / p.life
            draw_text(s, self.f_small, p.text, p.color, (p.x, p.y), ow=2)
        self.draw_hud(s)

    def draw_hud(self, s):
        low = self.time_left <= 15
        col = TOMATO if low and int(self.t_anim * 4) % 2 == 0 else (255, 255, 255)
        draw_text(s, self.f_mid, fmt_time(self.time_left), col, (16, 12), anchor="topleft")
        draw_text(s, self.f_small, "TIME", CREAM, (18, 46), anchor="topleft", ow=1)
        draw_text(s, self.f_mid, f"{self.score}", (255, 255, 255), (LANE_W // 2, 12), anchor="midtop")
        draw_text(s, self.f_tiny, "SCORE", CREAM, (LANE_W // 2, 46), anchor="midtop", ow=1)
        if self.combo >= 2:
            m = self.multiplier()
            txt = f"Combo x{self.combo}" + (f"  (score x{m})" if m > 1 else "")
            draw_text(s, self.f_small, txt, LETTUCE, (LANE_W - 14, 16), anchor="topright")
            bolt = self.a.icon("icon_bolt", 28)
            s.blit(bolt, (LANE_W - 14 - self.f_small.size(txt)[0] - 32, 12))
        self.draw_ticket(s)
        # pause button
        pr = self.pause_rect()
        btn = self.a.icon("round_white", pr.h)
        s.blit(btn, btn.get_rect(center=pr.center))
        draw_text(s, self.f_mid, "II", BROWN, (pr.centerx, pr.centery - 3), outline=None)

    def draw_ticket(self, s):
        r = pygame.Rect(LANE_W + 8, 8, W - LANE_W - 16, 372)
        s.blit(self.a.card("red", r.size, 0.45), r.topleft)
        draw_text(s, self.f_small, "ORDER", (255, 255, 255), (r.centerx, r.y + 21), outline=None)
        row_h = 42
        y0 = r.y + 52
        for i in range(len(STAGES)):
            stage_idx = len(STAGES) - 1 - i          # top of list = top of sandwich
            ry = y0 + i * row_h
            kind = RECIPE[stage_idx]
            done = stage_idx < self.stage or self.celebrate_t > 0
            cur = stage_idx == self.stage and self.celebrate_t <= 0
            rr = pygame.Rect(r.x + 10, ry, r.w - 20, row_h - 4)
            if cur:
                glow = 3 + int(2 * math.sin(self.t_anim * 8))
                pygame.draw.rect(s, GOLD, rr.inflate(glow, glow), width=4, border_radius=10)
                pygame.draw.rect(s, (255, 250, 230), rr, border_radius=10)
            elif done:
                pygame.draw.rect(s, (205, 225, 170), rr, border_radius=10)
            img = self.a.mini[kind].copy()
            if done:
                img.set_alpha(110)
            s.blit(img, (rr.x + 4, rr.y + 1))
            label = LABEL[kind] if stage_idx != 6 else "Top bread"
            draw_text(s, self.f_tiny, label, BROWN if not done else (120, 140, 90),
                      (rr.x + 42, rr.centery), anchor="midleft", outline=None)
            if done:
                s.blit(self.a.icon("check_on", 22), (rr.right - 26, rr.centery - 11))
        draw_text(s, self.f_small, f"Sandwiches", CREAM, (LANE_W + (W - LANE_W) // 2, 398), ow=2)
        draw_text(s, self.f_mid, f"{self.sandwiches} / {TARGET_SANDWICHES}", (255, 255, 255),
                  (LANE_W + (W - LANE_W) // 2, 430))
        draw_text(s, self.f_tiny, "Best", CREAM, (LANE_W + (W - LANE_W) // 2, 472), ow=1)
        draw_text(s, self.f_small, f"{self.best}", (255, 255, 255), (LANE_W + (W - LANE_W) // 2, 494), ow=2)

    # --- menus
    def draw_buttons(self, s):
        off = 3 if self.has_settings() else 0
        for i, b in enumerate(self.buttons):
            sel = (self.focus == i + off)
            r = b.rect.inflate(10, 6) if sel else b.rect
            s.blit(self.a.button("red" if sel else "white", r.size), r.topleft)
            font = self.f_mid if self.f_mid.size(b.label)[0] < r.w - 36 else self.f_small
            draw_text(s, font, b.label, (255, 255, 255) if sel else BROWN, (r.centerx, r.centery - 3), outline=None)

    def draw_settings(self, s):
        sr = self.settings_rects()
        names = ["Music", "Sound FX", "Mute all"]
        panel = sr["panel"]
        s.blit(self.a.card("wood", panel.size), panel.topleft)
        draw_text(s, self.f_small, "Volume", (255, 255, 255), (panel.centerx, panel.y + 24), outline=None)
        for i, row in enumerate(sr["rows"]):
            if self.focus == i:
                pygame.draw.rect(s, GOLD, row.inflate(6, 2), width=3, border_radius=12)
            draw_text(s, self.f_small, names[i], BROWN, (row.x + 14, row.centery), anchor="midleft", outline=None)
            if i < 2:
                key = ("music", "sfx")[i]
                lvl = self.audio.music_level if i == 0 else self.audio.sfx_level
                for k in ("_minus", "_plus"):
                    br = sr[key + k]
                    s.blit(self.a.icon("round_white", br.h), br.topleft)
                    arrow = self.a.icon("arrow_left" if k == "_minus" else "arrow_right", 18)
                    s.blit(arrow, arrow.get_rect(center=(br.centerx, br.centery - 2)))
                for b in range(10):
                    bx = sr[key + "_minus"].right + 10 + b * 20 + 0
                    on = b < lvl and not self.audio.muted
                    pygame.draw.rect(s, LETTUCE if on else (220, 205, 170),
                                     (bx, row.y + 12, 14, 28), border_radius=5)
            else:
                mr = sr["mute"]
                s.blit(self.a.button("red" if self.audio.muted else "white", mr.size), mr.topleft)
                draw_text(s, self.f_small, "ON" if self.audio.muted else "OFF", (255, 255, 255) if self.audio.muted else BROWN,
                          (mr.centerx, mr.centery - 2), outline=None)

    def draw_title(self, s):
        s.blit(self.a.bg, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((40, 24, 14, 110))
        s.blit(dim, (0, 0))
        bob = math.sin(self.t_anim * 2.2) * 6
        img = self.ferry_img(len(STAGES), "happy")
        img = pygame.transform.smoothscale(img, (int(img.get_width() * 0.9), int(img.get_height() * 0.9)))
        s.blit(img, (30, 262 + bob))
        draw_text(s, self.f_title, "Ferry's", (255, 255, 255), (W // 2 + 120, 100))
        draw_text(s, self.f_big, "Sandwiches", PINK, (W // 2 + 120, 170))
        draw_text(s, self.f_small, "Catch the ingredients. Build the order!", CREAM, (W // 2 + 120, 240), ow=2)
        self.draw_buttons(s)
        draw_text(s, self.f_tiny, f"Best score: {self.best}", CREAM, (590, 556), ow=1)

    def draw_howto(self, s):
        s.blit(self.a.bg, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((40, 24, 14, 150))
        s.blit(dim, (0, 0))
        s.blit(self.a.card("wood", (W - 120, 470)), (60, 36))
        draw_text(s, self.f_small, "How to Play", (255, 255, 255), (W // 2, 60), outline=None)
        lines = [
            "Move Ferry with the arrow keys / A-D, or the mouse / touch.",
            "Catch the ingredient highlighted on the ORDER ticket.",
            "Wrong ingredient? It bounces off and breaks your combo.",
            "Junk (sock, rotten egg, coin, sponge, banana) costs 5 seconds!",
            "3 catches in a row = +2s.  6 in a row = +3s and triple points.",
            f"Finish a sandwich for +5s. Build {TARGET_SANDWICHES} sandwiches to win!",
            "P or Esc pauses the game.",
        ]
        for i, ln in enumerate(lines):
            draw_text(s, self.f_tiny, ln, BROWN, (W // 2, 118 + i * 30), outline=None)
        # recipe strip
        x0 = W // 2 - (7 * 74) // 2 + 37
        for i, kind in enumerate(RECIPE):
            s.blit(self.a.items[kind], self.a.items[kind].get_rect(center=(x0 + i * 74, 372)))
            if i < 6:
                draw_text(s, self.f_small, ">", BROWN, (x0 + i * 74 + 37, 372), outline=None)
        draw_text(s, self.f_tiny, "Recipe: bread, lettuce, ham, cheese, cucumber, tomato, bread on top",
                  BROWN, (W // 2, 424), outline=None)
        self.draw_buttons(s)

    def draw_pause(self, s):
        self.draw_play(s)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((30, 18, 10, 170))
        s.blit(dim, (0, 0))
        draw_text(s, self.f_big, "Paused", (255, 255, 255), (W // 2, 84))
        self.draw_settings(s)
        self.draw_buttons(s)

    def draw_settings_screen(self, s):
        s.blit(self.a.bg, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((40, 24, 14, 150))
        s.blit(dim, (0, 0))
        draw_text(s, self.f_big, "Settings", (255, 255, 255), (W // 2, 90))
        self.draw_settings(s)
        self.draw_buttons(s)

    def draw_end(self, s):
        won = self.final["won"]
        s.blit(self.a.bg, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((40, 24, 14, 140))
        s.blit(dim, (0, 0))
        if won:
            img = self.ferry_img(len(STAGES), "happy")
            title, col = "Sandwich master!", PINK
        else:
            img = self.ferry_img(self.final["stage"], "confused")
            title, col = "Out of time!", (255, 170, 150)
        bob = math.sin(self.t_anim * 2.5) * 5
        s.blit(img, (40, 215 + bob))
        draw_text(s, self.f_end, title, col, (W // 2 + 150, 88))
        panel = pygame.Rect(W // 2 - 20, 150, 340, 300)
        s.blit(self.a.card("wood", panel.size), panel.topleft)
        draw_text(s, self.f_small, "Results", (255, 255, 255), (panel.centerx, panel.y + 24), outline=None)
        rows = [("Sandwiches", f"{self.final['sandwiches']} / {TARGET_SANDWICHES}")]
        if won:
            rows.append(("Time bonus", f"+{self.final['bonus']}"))
        rows.append(("Score", f"{self.final['score']}"))
        rows.append(("Best", f"{self.best}"))
        for i, (a, b) in enumerate(rows):
            y = 222 + i * 58
            draw_text(s, self.f_small, a, BROWN, (panel.x + 28, y), anchor="midleft", outline=None)
            draw_text(s, self.f_mid, b, BROWN if a != "Score" else TOMATO, (panel.right - 28, y), anchor="midright", outline=None)
        msg = ("Delicious! Ferry is very proud." if won else "So close! Try again?")
        draw_text(s, self.f_small, msg, CREAM, (W // 2 + 150, 478), ow=2)
        self.draw_buttons(s)

    def draw(self):
        c = self.canvas
        if self.state == "title":
            self.draw_title(c)
        elif self.state == "howto":
            self.draw_howto(c)
        elif self.state == "settings":
            self.draw_settings_screen(c)
        elif self.state == "play":
            self.draw_play(c)
        elif self.state == "pause":
            self.draw_pause(c)
        else:
            self.draw_end(c)
        off = (0, 0)
        if self.state == "play" and self.shake > 0:
            off = (random.randint(-int(self.shake), int(self.shake)), random.randint(-int(self.shake), int(self.shake)))
        self.screen.blit(c, off)

    # ------------------------------------------------------------------- run
    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for ev in pygame.event.get():
                if self.handle(ev) is False:
                    running = False
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


def main():
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("Ferry's Sandwiches")
    screen = pygame.display.set_mode((W, H), pygame.SCALED)
    try:                                            # cute cursor from the UI pack
        cur = pygame.image.load(os.path.join(ASSETS, "ui", "cursor.png")).convert_alpha()
        cur = pygame.transform.smoothscale(cur, (26, 30))
        pygame.mouse.set_cursor(pygame.cursors.Cursor((3, 2), cur))
    except Exception:
        pass
    assets = Assets()
    audio = Audio()
    game = Game(screen, assets, audio)
    game.run()


if __name__ == "__main__":
    main()
