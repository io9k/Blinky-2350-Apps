"""
Blinky 2350 Pachinko
by @io9k
https://instagram.com/io9k
https://github.com/io9k
====================
Badgeware app for Pimoroni Blinky (39x26 greyscale LED matrix).

Bet a bottom pocket, drop a ball, hope it lands where you called.

Controls
--------
A           pocket 1  (left triangle cutout)
A + B       pocket 2  (bay between A and B)
B + C       pocket 3  (bay between B and C)
C           pocket 4  (right triangle cutout)
UP          launch

Scoring
-------
Top-left pixels  = balls remaining (start 8, max 8)
Top-right pixels = correct slots   (win at WIN_SCORE)

Hit your pocket : keep the ball and gain one extra (capped at 8)
Miss            : lose one ball
0 balls         : pegs fall, then GAME / OVER   (reset the badge)
WIN_SCORE hits  : ball shower, then WIN         (reset the badge)
"""

import math
import random


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

W = screen.width
H = screen.height


# ---------------------------------------------------------------------------
# Board geometry (tune these to match the physical cutouts)
# ---------------------------------------------------------------------------

# Pockets use the badge's bottom LED voids as mouths.
POCKETS = {
    1: {"x0": 0,  "x1": 8,  "y0": 19, "pay": 2, "name": "1"},
    2: {"x0": 9,  "x1": 18, "y0": 21, "pay": 1, "name": "2"},
    3: {"x0": 20, "x1": 28, "y0": 21, "pay": 1, "name": "3"},
    4: {"x0": 30, "x1": 38, "y0": 19, "pay": 2, "name": "4"},
}

# Missing-LED islands around the A / B / C buttons.
ISLANDS = [
    (8, 22, 10, 25),
    (18, 22, 20, 25),
    (28, 22, 30, 25),
]


# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

GRAVITY = 0.055
REST = 0.58
PEG_R = 0.72
BALL_R = 0.55
MAX_VY = 0.95

MAX_BALLS = 8
WIN_SCORE = 7
WIN_SHOWER = 50
WIN_LIMIT_MS = 10000


# ---------------------------------------------------------------------------
# Game states
# ---------------------------------------------------------------------------

STATE_PLAY = 0
STATE_DRAIN = 1
STATE_OVER = 2
STATE_SHOWER = 3
STATE_WIN = 4

state = STATE_PLAY
balls_left = MAX_BALLS
balls_scored = 0
bet = None
ball = None
trail = []
result = None
result_t = 0
peg_flash = {}
chord_wait = 0
pending_bet = None
flash_back = 0
falling_pegs = []
shower = []
shower_left = 0
shower_cd = 0
end_started = 0
drain_hold = 0

try:
    screen.font = font.nope
except Exception:
    pass


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def grey(v):
    v = 0 if v < 0 else (255 if v > 255 else int(v))
    return color.rgb(v, v, v)


def plot(x, y, v):
    if v <= 0:
        return
    xi = int(x)
    yi = int(y)
    if xi < 0 or yi < 0 or xi >= W or yi >= H:
        return
    screen.pen = grey(v)
    screen.put(xi, yi)


# ---------------------------------------------------------------------------
# Collision / pockets
# ---------------------------------------------------------------------------

def in_rect(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def in_triangle_left(x, y):
    if y < 19:
        return False
    edge = (y - 19) * 8.0 / 6.0
    return x <= edge


def in_triangle_right(x, y):
    if y < 19:
        return False
    edge = W - 1 - (y - 19) * 8.0 / 6.0
    return x >= edge


def solid_at(x, y):
    if x < 0 or x > W - 1:
        return True
    if y < 0:
        return True
    if y > H - 1:
        return False
    for isle in ISLANDS:
        if in_rect(x, y, isle):
            return True
    return False


def pocket_at(x, y):
    if y < 19:
        return None
    if in_triangle_left(x, y):
        return 1
    if in_triangle_right(x, y):
        return 4
    p2 = POCKETS[2]
    p3 = POCKETS[3]
    if p2["x0"] <= x <= p2["x1"] and y >= p2["y0"]:
        return 2
    if p3["x0"] <= x <= p3["x1"] and y >= p3["y0"]:
        return 3
    return None


# ---------------------------------------------------------------------------
# Peg field
# ---------------------------------------------------------------------------

def make_pegs():
    pegs = []
    y = 3
    row = 0
    while y <= 16:
        off = 2 if (row % 2) == 0 else 3
        x = off
        while x <= W - 3:
            if not solid_at(x, y) and pocket_at(x, y) is None:
                jx = x + random.uniform(-0.55, 0.55)
                pegs.append([jx, float(y)])
            x += 3
        y += 2
        row += 1
    return pegs


PEGS = make_pegs()


# ---------------------------------------------------------------------------
# Balls
# ---------------------------------------------------------------------------

def new_ball(x=None):
    if x is None:
        x = random.uniform(6.0, W - 7.0)
    return [x, 1.2, random.uniform(-0.45, 0.45), 0.02]


def launch():
    global ball, trail, result
    if state != STATE_PLAY:
        return
    if bet is None or ball is not None:
        return
    if balls_left <= 0:
        return
    ball = new_ball()
    trail = []
    result = None


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def chord_bet():
    """Map held A/B/C chords to a single pocket."""
    a = badge.held(BUTTON_A)
    b = badge.held(BUTTON_B)
    c = badge.held(BUTTON_C)
    if a and (not b) and (not c):
        return 1
    if a and b and (not c):
        return 2
    if b and c and (not a):
        return 3
    if c and (not a) and (not b):
        return 4
    return None


def handle_input():
    global bet, pending_bet, chord_wait
    if state != STATE_PLAY or ball is not None:
        return

    raw = chord_bet()
    if raw is not None:
        if raw != pending_bet:
            pending_bet = raw
            chord_wait = 2
        elif chord_wait > 0:
            chord_wait -= 1
        else:
            bet = raw
    else:
        pending_bet = None
        chord_wait = 0

    if badge.pressed(BUTTON_UP):
        launch()


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

def bounce_peg(bx, by, vx, vy, px, py):
    dx = bx - px
    dy = by - py
    d2 = dx * dx + dy * dy
    min_d = PEG_R + BALL_R
    if d2 < 0.0001 or d2 >= min_d * min_d:
        return bx, by, vx, vy, False

    d = math.sqrt(d2)
    nx, ny = dx / d, dy / d
    overlap = min_d - d
    bx += nx * overlap
    by += ny * overlap
    vn = vx * nx + vy * ny
    if vn < 0:
        vx -= (1 + REST) * vn * nx
        vy -= (1 + REST) * vn * ny
        vx += random.uniform(-0.35, 0.35)
        vy += random.uniform(-0.06, 0.16)
    return bx, by, vx, vy, True


def bounce_wall(bx, by, vx, vy):
    if bx < BALL_R:
        bx = BALL_R
        vx = abs(vx) * REST
    if bx > W - 1 - BALL_R:
        bx = W - 1 - BALL_R
        vx = -abs(vx) * REST
    if by < BALL_R:
        by = BALL_R
        vy = abs(vy) * REST

    for isle in ISLANDS:
        x0, y0, x1, y1 = isle
        if x0 - BALL_R <= bx <= x1 + BALL_R and y0 - BALL_R <= by <= y1 + BALL_R:
            left = bx - (x0 - BALL_R)
            right = (x1 + BALL_R) - bx
            top = by - (y0 - BALL_R)
            if top < left and top < right:
                by = y0 - BALL_R - 0.01
                vy = -abs(vy) * REST
            elif left < right:
                bx = x0 - BALL_R - 0.01
                vx = -abs(vx) * REST
            else:
                bx = x1 + BALL_R + 0.01
                vx = abs(vx) * REST
    return bx, by, vx, vy


def physics_one(b, do_pegs=True, speed=1.0):
    bx, by, vx, vy = b
    vy += GRAVITY * speed
    cap = MAX_VY * speed
    if vy > cap:
        vy = cap
    bx += vx * speed
    by += vy * speed

    if do_pegs:
        for i, peg in enumerate(PEGS):
            bx, by, vx, vy, hit = bounce_peg(bx, by, vx, vy, peg[0], peg[1])
            if hit:
                peg_flash[i] = 8

    bx, by, vx, vy = bounce_wall(bx, by, vx, vy)
    return [bx, by, vx * 0.995, vy]


# ---------------------------------------------------------------------------
# State changes
# ---------------------------------------------------------------------------

def begin_drain():
    global state, falling_pegs, ball, trail, end_started, drain_hold
    state = STATE_DRAIN
    drain_hold = 70
    ball = None
    trail = []
    falling_pegs = []
    for peg in PEGS:
        falling_pegs.append([
            peg[0],
            peg[1],
            random.uniform(-0.06, 0.06),
            random.uniform(0.02, 0.08),
        ])
    PEGS[:] = []
    end_started = badge.ticks
    badge.caselights(0.2)


def begin_shower():
    global state, shower, shower_left, shower_cd, ball, trail, end_started
    state = STATE_SHOWER
    ball = None
    trail = []
    shower = []
    shower_left = WIN_SHOWER
    shower_cd = 0
    end_started = badge.ticks
    badge.caselights(1.0)


def apply_play_result(landed):
    global balls_left, balls_scored, result, result_t, flash_back, ball
    won = landed != 0 and landed == bet
    if won:
        balls_left += 1
        if balls_left > MAX_BALLS:
            balls_left = MAX_BALLS
        balls_scored += 1
        flash_back = 10
        result = (landed, True)
    else:
        balls_left -= 1
        if balls_left < 0:
            balls_left = 0
        result = (landed, False)

    result_t = 35
    ball = None

    if balls_scored >= WIN_SCORE:
        begin_shower()
    elif balls_left <= 0:
        begin_drain()


# ---------------------------------------------------------------------------
# Per-frame simulation
# ---------------------------------------------------------------------------

def step_play_ball():
    global ball, trail
    if ball is None:
        return

    ball = physics_one(ball, True)
    bx, by, vx, vy = ball

    landed = pocket_at(bx, by)
    if landed is not None and vy >= 0 and by >= POCKETS[landed]["y0"]:
        apply_play_result(landed)
        return

    if by > H + 2:
        apply_play_result(0)
        return

    trail.append((bx, by))
    if len(trail) > 8:
        trail.pop(0)


def step_drain():
    global state, falling_pegs, drain_hold
    alive = []
    for p in falling_pegs:
        p[3] += 0.012
        if p[3] > 0.28:
            p[3] = 0.28
        p[0] += p[2]
        p[1] += p[3]
        if p[1] < H + 2:
            alive.append(p)
    falling_pegs = alive

    if len(falling_pegs) == 0:
        if drain_hold > 0:
            drain_hold -= 1
        else:
            state = STATE_OVER


def step_shower():
    global shower, shower_left, shower_cd, state

    if shower_left > 0:
        shower_cd -= 1
        if shower_cd <= 0 and len(shower) < 12:
            shower.append(new_ball())
            shower_left -= 1
            shower_cd = 2

    alive = []
    for b in shower:
        b = physics_one(b, True, 2.4)
        bx, by, vx, vy = b
        landed = pocket_at(bx, by)
        slotted = landed is not None and vy >= 0 and by >= POCKETS[landed]["y0"]
        if (not slotted) and by <= H + 2:
            alive.append(b)
    shower = alive

    timed_out = (badge.ticks - end_started) >= WIN_LIMIT_MS
    if (shower_left <= 0 and len(shower) == 0) or timed_out:
        state = STATE_WIN
        shower = []
        shower_left = 0


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def draw_pegs():
    for i, peg in enumerate(PEGS):
        flash = peg_flash.get(i, 0)
        v = 40 + flash * 26
        plot(round(peg[0]), round(peg[1]), v)
        if flash:
            peg_flash[i] = flash - 1
            if peg_flash[i] <= 0:
                peg_flash.pop(i, None)

    for p in falling_pegs:
        plot(round(p[0]), round(p[1]), 180)


def draw_pockets():
    t = badge.ticks / 180.0
    pulse = 0.55 + 0.45 * math.sin(t)

    for n, p in POCKETS.items():
        selected = (state == STATE_PLAY) and (bet == n)
        base = int(30 + 160 * pulse) if selected else 28
        y = p["y0"]

        for x in range(p["x0"], p["x1"] + 1):
            if solid_at(x, y):
                continue
            lip = base if selected else 22
            plot(x, y, lip)

        glow = selected
        if result and result[0] == n and result_t > 0:
            glow = True
            base = 80 + result_t * 3

        if glow:
            for yy in range(p["y0"] + 1, H):
                for x in range(p["x0"], p["x1"] + 1):
                    if n == 1 and not in_triangle_left(x, yy):
                        continue
                    if n == 4 and not in_triangle_right(x, yy):
                        continue
                    if solid_at(x, yy):
                        continue
                    fade = 0.35 + 0.08 * (H - yy)
                    plot(x, yy, int(base * fade))


def draw_one_ball(b, tr=None):
    if tr:
        for i, pt in enumerate(tr):
            plot(round(pt[0]), round(pt[1]), 12 + i * 10)
    ix = int(round(b[0]))
    iy = int(round(b[1]))
    plot(ix, iy, 255)
    plot(ix - 1, iy, 70)
    plot(ix + 1, iy, 70)
    plot(ix, iy - 1, 70)
    plot(ix, iy + 1, 90)


def draw_hud():
    for i in range(balls_left):
        plot(1 + i, 0, 200)
    for i in range(balls_scored):
        if i >= MAX_BALLS:
            break
        plot(W - 2 - i, 0, 200)


def draw_banner(line1, line2=None):
    screen.pen = color.white
    try:
        screen.font = font.nope
    except Exception:
        pass

    gap = 11
    try:
        w1, h1 = screen.measure_text(line1)
    except Exception:
        w1, h1 = len(line1) * 4, 6

    if line2:
        try:
            w2, h2 = screen.measure_text(line2)
        except Exception:
            w2, h2 = len(line2) * 4, 6
        y = int((H - (h1 + gap)) / 2)
        if y < 3:
            y = 3
        y -= 4
        x1 = int((W - w1) / 2)
        x2 = int((W - w2) / 2)
        if x1 < 0:
            x1 = 0
        if x2 < 0:
            x2 = 0
        screen.text(line1, x1, y)
        screen.text(line2, x2, y + gap)
    else:
        y = int((H - h1) / 2)
        x1 = int((W - w1) / 2)
        if x1 < 0:
            x1 = 0
        if y < 3:
            y = 3
        screen.text(line1, x1, y)


def lights():
    global flash_back

    if state == STATE_WIN:
        badge.caselights(0.6 + 0.4 * math.sin(badge.ticks / 80.0))
        return
    if state == STATE_OVER:
        badge.caselights(0.08)
        return
    if state == STATE_SHOWER:
        badge.caselights(0.8)
        return
    if flash_back > 0:
        badge.caselights(1.0)
        flash_back -= 1
        return

    if bet == 1:
        badge.caselights(0.35, 0.05, 0.05, 0.05)
    elif bet == 2:
        badge.caselights(0.08, 0.35, 0.08, 0.05)
    elif bet == 3:
        badge.caselights(0.05, 0.08, 0.35, 0.08)
    elif bet == 4:
        badge.caselights(0.05, 0.05, 0.08, 0.35)
    else:
        badge.caselights(0.06)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

badge.default_clear = color.black

while True:
    handle_input()

    if state == STATE_PLAY:
        step_play_ball()
    elif state == STATE_DRAIN:
        step_drain()
    elif state == STATE_SHOWER:
        step_shower()

    if result_t > 0:
        result_t -= 1

    screen.pen = color.black
    screen.clear()

    if state == STATE_OVER:
        draw_pockets()
        draw_banner("GAME", "OVER")
    elif state == STATE_WIN:
        draw_banner("WIN")
    else:
        draw_pockets()
        draw_pegs()
        if ball is not None:
            draw_one_ball(ball, trail)
        for b in shower:
            draw_one_ball(b)
        draw_hud()

    lights()
    badge.update()

