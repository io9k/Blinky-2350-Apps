# =============================================================================
# Rocket Ticker — Blinky 2350 / Badgeware 3.0.2
# =============================================================================

import wifi
import time
import random
import requests
import network
wlan = network.WLAN(network.STA_IF)



# -----------------------------------------------------------------------------
# Tickers + Yahoo
# -----------------------------------------------------------------------------
TICKERS = ["GME", "EBAY", "SPCX", "SPY"]
ticker_index = 0
TICKER = TICKERS[ticker_index]
REFRESH_MS = 15000
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def make_url(sym):
    return "https://query1.finance.yahoo.com/v8/finance/chart/" + sym + "?range=1d&interval=1d"


URL = make_url(TICKER)

NETWORKS = [
    ("Kilo-Guest-1", "KiloClub"),
    ("Air42", "3049kilo"),
    ("io9k", "3049kilo"),
    ("Stone4K.com Starlink", "populous"),
]
net_index = 0
net_try_at = 0
NET_DWELL_MS = 12000
wifi_note = ""


# -----------------------------------------------------------------------------
# Price text + scatter
# -----------------------------------------------------------------------------
ANIM = "scatter"
ANIM_MS = 3000
PARTICLE_COUNT = 1
SCAT_GRAV = 0.02
TICKER_Y = 0
PRICE_Y = 12
TICKER_FONT = font.sins
PRICE_FONT = font.sins
FADE_MAX = 255
FADE_MIN = 60
REVEAL_DELAY = 1000


# -----------------------------------------------------------------------------
# Ship + flame
# -----------------------------------------------------------------------------
SHIP_X = 22
SHIP_Y = 1
FLAME_X = 23
FLAME_Y = 11
FLAME_W = 2
FLAME_H = 3


# -----------------------------------------------------------------------------
# Starfield
# -----------------------------------------------------------------------------
STAR_SIZE = 34
STAR_COUNT = 6
STAR_X0 = 5
STAR_Y0 = 0
FX_FADE_OUT_MS = 3000
FX_FADE_IN_MS = 1000


# -----------------------------------------------------------------------------
# Battery icon
# -----------------------------------------------------------------------------
BAT_X = 35
BAT_Y = 18
BATT_BRI = 150


# -----------------------------------------------------------------------------
# Assets
# -----------------------------------------------------------------------------
def load_png(*paths):
    for p in paths:
        try:
            return image.load(p)
        except Exception:
            pass
    return None


ship_up = load_png("shipUp.png", "/apps/kittyTicker/shipUp.png")
ship_down = load_png("shipDown.png", "/apps/kittyTicker/shipDown.png")


# -----------------------------------------------------------------------------
# Runtime state
# -----------------------------------------------------------------------------
price_text = "--"
shown_text = ""
last_fetch = 0
price_val = None
prev_close = None
pending_price = None
pending_val = None
pending_close = None
reveal_at = 0
matrix_bri = 0.4
star_spd = 0.08
last_pressed = []
last_ticker_pressed = []
slots = []
stars = []
rear_alert_armed = True
rear_anim_left = 0
rear_anim_step = 0
rear_anim_t = 0


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def ship_is_down():
    return (
        price_val is not None
        and prev_close is not None
        and price_val < prev_close
    )


def plot(x, y, bri):
    if bri < 20:
        return
    screen.pen = color.rgb(bri, bri, bri)
    try:
        screen.rectangle(int(x), int(y), 1, 1)
    except Exception:
        try:
            screen.put(int(x), int(y))
        except Exception:
            pass


def text_size(msg):
    try:
        return screen.measure_text(msg)
    except Exception:
        return (len(msg) * 5, 8)


def fx_level():
    if last_fetch == 0:
        return 0.0
    age = time.ticks_diff(time.ticks_ms(), last_fetch)
    if age < 0:
        age = 0
    if age < FX_FADE_IN_MS:
        return age / FX_FADE_IN_MS
    left = REFRESH_MS - age
    if left <= 0:
        return 0.0
    if left < FX_FADE_OUT_MS:
        return left / FX_FADE_OUT_MS
    return 1.0


# -----------------------------------------------------------------------------
# Ticker label + price digits
# -----------------------------------------------------------------------------
def draw_str(msg, x, y, face=None):
    if last_fetch == 0:
        bri = FADE_MIN
    else:
        age = time.ticks_diff(time.ticks_ms(), last_fetch)
        if age < 0:
            age = 0
        if age > REFRESH_MS:
            age = REFRESH_MS
        t = age / REFRESH_MS
        bri = int(FADE_MAX + (FADE_MIN - FADE_MAX) * t)
    screen.pen = color.rgb(bri, bri, bri)
    screen.font = face or PRICE_FONT
    screen.text(msg, int(x), int(y))


def center_str(msg, y, face=None):
    screen.font = face or TICKER_FONT
    w, h = text_size(msg)
    screen.pen = color.rgb(142, 142, 142)
    gap = -1
    x = 0
    for ch in msg:
        screen.text(ch, x, int(y))
        cw, chh = text_size(ch)
        x += cw + gap
    return w, h


def layout_price(text):
    screen.font = PRICE_FONT
    gap = 0
    digit_w = 5
    dot_w = 2
    out = []
    cx = 0
    for ch in text:
        w = dot_w if ch == "." else digit_w
        px = cx
        py = PRICE_Y
        if ch == ".":
            px -= 1
        out.append((ch, px, py, w, 8))
        cx += w + gap
    return out


def spawn_particles(ch, x, y, w, h, kind):
    parts = []
    for i in range(PARTICLE_COUNT):
        if kind == "slice":
            speed = 0.4 + random.random() * 0.6
            vx = -speed if i % 2 == 0 else speed
            vy = (random.random() - 0.5) * 0.3
        else:
            vx = (random.random() - 0.5) * 0.25
            vy = -0.6 - random.random() * 0.3
        parts.append({
            "ch": ch,
            "x": float(x),
            "y": float(y),
            "vx": vx,
            "vy": vy,
            "t": time.ticks_ms(),
        })
    return parts


def sync_slots(new_text):
    global slots, shown_text
    laid = layout_price(new_text)
    old = shown_text
    if len(old) < len(new_text):
        old = (" " * (len(new_text) - len(old))) + old
    elif len(old) > len(new_text) and new_text:
        old = old[-len(new_text):]
    new_slots = []
    for i, (ch, x, y, w, h) in enumerate(laid):
        old_ch = old[i] if i < len(old) else ""
        slot = {
            "ch": ch,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "parts": [],
        }
        if old_ch and old_ch not in (" ",) and ch != old_ch:
            slot["parts"] = spawn_particles(old_ch, x, y, w, h, ANIM)
        new_slots.append(slot)
    slots = new_slots
    shown_text = new_text


def tick_slots():
    now = time.ticks_ms()
    for s in slots:
        draw_str(s["ch"], s["x"], s["y"], PRICE_FONT)
        keep = []
        for p in s["parts"]:
            age = time.ticks_diff(now, p["t"])
            if age > ANIM_MS:
                continue
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if ANIM == "scatter":
                p["vy"] += SCAT_GRAV
            if -8 < p["x"] < screen.width and -8 < p["y"] < screen.height:
                draw_str(p["ch"], p["x"], p["y"], PRICE_FONT)
                keep.append(p)
        s["parts"] = keep


# -----------------------------------------------------------------------------
# Rear lights
# -----------------------------------------------------------------------------
def arm_rear_alert():
    global rear_alert_armed, rear_anim_left, rear_anim_step, rear_anim_t
    mag = 0.0
    if price_val is not None and prev_close is not None:
        mag = price_val - prev_close
        if mag < 0:
            mag = -mag
    if mag > 1.0:
        if rear_alert_armed:
            rear_anim_left = 40
            rear_anim_step = 0
            rear_anim_t = time.ticks_ms()
            rear_alert_armed = False
    else:
        rear_alert_armed = True


def tick_rear_lights():
    global rear_anim_left, rear_anim_step, rear_anim_t
    if rear_anim_left > 0:
        if time.ticks_diff(time.ticks_ms(), rear_anim_t) > 80:
            rear_anim_t = time.ticks_ms()
            rear_anim_step = (rear_anim_step + 1) % 4
            rear_anim_left -= 1
        lv = [0.0, 0.0, 0.0, 0.0]
        lv[rear_anim_step] = 1.0
        try:
            badge.caselights(lv[0], lv[1], lv[2], lv[3])
        except Exception:
            pass
        if rear_anim_left <= 0:
            try:
                badge.caselights(0, 0, 0, 0)
            except Exception:
                pass
    else:
        try:
            badge.caselights(0, 0, 0, 0)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Starfield
# -----------------------------------------------------------------------------
def update_star_speed():
    global star_spd
    mag = 0.0
    if price_val is not None and prev_close is not None:
        mag = price_val - prev_close
        if mag < 0:
            mag = -mag
    t = mag / 1.00 
    if t > 1:
        t = 1
    t = t * t
    #fade = 1.0 - (1.0 / (1.0 + t + t * t * 0.5))
    star_spd = 0.10 + 1.0 * t
    arm_rear_alert()


def reset_star():
    if ship_is_down():
        if random.random() < 0.5:
            x = STAR_X0 + random.random() * STAR_SIZE
            y = STAR_Y0 + STAR_SIZE - 1
        else:
            x = STAR_X0 + STAR_SIZE - 1
            y = STAR_Y0 + random.random() * STAR_SIZE
    else:
        if random.random() < 0.5:
            x = STAR_X0 + random.random() * STAR_SIZE
            y = STAR_Y0
        else:
            x = STAR_X0 + STAR_SIZE - 1
            y = STAR_Y0 + random.random() * STAR_SIZE
    return {"x": x, "y": y, "dist": 0.0, "spd": star_spd}


def init_stars():
    global stars
    stars = [reset_star() for _ in range(STAR_COUNT)]


def draw_stars():
    if not stars:
        init_stars()
    going_down = ship_is_down()
    for s in stars:
        s["spd"] = star_spd
        if going_down:
            s["x"] -= s["spd"]
            s["y"] -= s["spd"]
        else:
            s["x"] -= s["spd"]
            s["y"] += s["spd"]
        s["dist"] += s["spd"]
        off = (
            s["dist"] >= STAR_SIZE
            or s["x"] < STAR_X0
            or (going_down and s["y"] < STAR_Y0)
            or ((not going_down) and s["y"] >= STAR_Y0 + STAR_SIZE)
        )
        if off:
            ns = reset_star()
            s["x"] = ns["x"]
            s["y"] = ns["y"]
            s["dist"] = 0.0
            s["spd"] = ns["spd"]
            continue
        t = s["dist"] / STAR_SIZE
        bri = int(220 * (1.0 - t) * fx_level())
        if bri < 8:
            continue
        screen.pen = color.rgb(bri, bri, bri)
        try:
            screen.put(int(s["x"]), int(s["y"]))
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Fetch + ticker switch
# -----------------------------------------------------------------------------
def pull_price():
    global price_text, price_val, prev_close
    r = None
    try:
        r = requests.get(URL, headers={"User-Agent": UA})
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("fulldayPrice")
        if price is None:
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            price = [c for c in closes if c is not None][-1]
        price_text = "$%.2f" % float(price)
        price_val = float(price)
        pc = meta.get("chartPreviousClose")
        prev_close = float(pc) if pc is not None else None
        update_star_speed()
    except Exception as e:
        print("price error:", e)
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:
                pass


def set_ticker(i):
    global ticker_index, TICKER, URL, price_text, shown_text, slots
    global last_fetch, price_val, prev_close
    global rear_alert_armed, rear_anim_left, reveal_at
    n = len(TICKERS)
    if n <= 0:
        return
    ticker_index = i % n
    TICKER = TICKERS[ticker_index]
    URL = make_url(TICKER)
    price_text = "--"
    shown_text = ""
    slots = []
    last_fetch = 0
    price_val = None
    prev_close = None
    rear_alert_armed = True
    rear_anim_left = 0
    reveal_at = 0
    print("ticker", TICKER)


# -----------------------------------------------------------------------------
# Ship, flame, battery
# -----------------------------------------------------------------------------
def draw_ship():
    img = ship_down if ship_is_down() else ship_up
    if img is None:
        img = ship_up or ship_down
    if img is None:
        return
    screen.blit(img, SHIP_X, SHIP_Y)


def draw_flame():
    if ship_is_down():
        return
    dx, dy = -1, 1
    tick = int(badge.ticks) // 50
    step = 0
    while step < FLAME_H:
        w = 0
        while w < FLAME_W:
            x = FLAME_X + dx * step + (w - 1)
            y = FLAME_Y + dy * step
            flicker = (tick + step * 3 + w * 7) % 4
            if flicker != 0:
                falloff = 1.0 - (step / 4.0)
                bri = int((50 + flicker * 70) * falloff * fx_level())
                plot(x, y, bri)
            w += 1
        step += 1


def draw_battery(pct):
    dots = (
        (1, 0), (2, 0),
        (3, 1), (3, 2),
        (2, 3), (1, 3),
        (0, 2), (0, 1),
    )
    n = len(dots)
    lit = int(pct * n + 0.499)
    if pct > 0.02 and lit < 1:
        lit = 1
    if lit > n:
        lit = n
    if pct <= 0.15:
        lit = 1 if (int(badge.ticks) // 300) % 2 == 0 else 0
    i = 0
    while i < lit:
        px, py = dots[i]
        plot(BAT_X + px, BAT_Y + py, BATT_BRI)
        i += 1


def read_battery_pct():
    raw = 0
    try:
        raw = badge.battery_level
        if callable(raw):
            raw = raw()
    except Exception as e:
        print("battery:", e)
        raw = 0
    try:
        pct = float(raw)
        if pct > 1.0:
            pct = pct / 100.0
        return pct
    except Exception:
        return 0.0


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------
def update():
    global last_fetch, matrix_bri, last_pressed, last_ticker_pressed
    global rear_anim_left, rear_anim_step, rear_anim_t
    global pending_price, pending_val, pending_close, reveal_at
    global price_text, price_val, prev_close
    global net_index, net_try_at, wifi_note

    now = time.ticks_ms()

    pressed = []
    try:
        pressed = list(badge.pressed())
    except Exception:
        try:
            pressed = list(badge.pressed)
        except Exception:
            pressed = []

    def is_down(btn):
        try:
            return btn in pressed
        except Exception:
            return False

    def was_down(btn, old):
        try:
            return btn in old
        except Exception:
            return False

    if is_down(BUTTON_UP) and not was_down(BUTTON_UP, last_pressed):
        matrix_bri += 0.1
    if is_down(BUTTON_DOWN) and not was_down(BUTTON_DOWN, last_pressed):
        matrix_bri -= 0.1
    if is_down(BUTTON_C) and not was_down(BUTTON_C, last_ticker_pressed):
        set_ticker(ticker_index + 1)
    if is_down(BUTTON_A) and not was_down(BUTTON_A, last_ticker_pressed):
        set_ticker(ticker_index - 1)
    last_pressed = pressed
    last_ticker_pressed = pressed

    if matrix_bri < 0.1:
        matrix_bri = 0.1
    if matrix_bri > 1.0:
        matrix_bri = 1.0
    try:
        badge.brightness = matrix_bri
    except Exception:
        pass
    try:
        set_brightness(matrix_bri)
    except Exception:
        pass
    try:
        screen.alpha = int(matrix_bri * 255)
    except Exception:
        pass

    online = False
    try:
        online = wlan.isconnected()
    except Exception:
        online = False

    if (not online) and NETWORKS:
        ssid, psk = NETWORKS[net_index % len(NETWORKS)]
        if net_try_at == 0:
            net_try_at = now
            print("wifi try", net_index, ssid)
            try:
                wlan.disconnect()
            except Exception:
                pass
            try:
                wlan.active(False)
            except Exception:
                pass
            try:
                wlan.active(True)
            except Exception:
                pass
            try:
                wlan.connect(ssid, psk)
            except Exception as e:
                print("wlan.connect", e)
        else:
            try:
                online = wlan.isconnected()
            except Exception:
                online = False

        if (not online) and time.ticks_diff(now, net_try_at) > NET_DWELL_MS:
            print("wifi fail", net_index, ssid)
            try:
                wlan.disconnect()
            except Exception:
                pass
            try:
                wlan.active(False)
            except Exception:
                pass
            net_index += 1
            net_try_at = 0
            if (net_index % len(NETWORKS)) == 0:
                wifi_note = "NoWifi"

    if online:
        wifi_note = ""
        if last_fetch == 0 or time.ticks_diff(now, last_fetch) > REFRESH_MS:
            old_txt = price_text
            old_val = price_val
            old_close = prev_close
            pull_price()
            last_fetch = now
            if price_text != old_txt:
                pending_price = price_text
                pending_val = price_val
                pending_close = prev_close
                price_text = old_txt
                price_val = old_val
                prev_close = old_close
                update_star_speed()
                reveal_at = now + REVEAL_DELAY

    if not slots and price_text:
        sync_slots(price_text)
    if reveal_at and time.ticks_diff(now, reveal_at) >= 0:
        price_text = pending_price
        price_val = pending_val
        prev_close = pending_close
        update_star_speed()
        sync_slots(price_text)
        reveal_at = 0

    screen.pen = color.black
    screen.clear()
    draw_stars()
    draw_ship()
    draw_flame()
    center_str(TICKER, TICKER_Y, TICKER_FONT)
    tick_slots()
    draw_battery(read_battery_pct())
    tick_rear_lights()
    if wifi_note:
        screen.pen = color.white
        screen.font = PRICE_FONT
        screen.text(wifi_note, 0, PRICE_Y)


run(update)

