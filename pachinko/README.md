# Pachinko (Blinky 2350)

Four-pocket pachinko that uses the badge's bottom LED cutouts as the slots.

## Controls

| Input | Action |
|---|---|
| **A** | Bet pocket 1 (left triangle) |
| **A + B** | Bet pocket 2 (bay between A and B) |
| **B + C** | Bet pocket 3 (bay between B and C) |
| **C** | Bet pocket 4 (right triangle) |
| **UP** | Launch (needs a bet and at least 1 credit) |

B alone does nothing. Combos replace the current bet. Bet is locked while the ball is in play.

Payout: pockets 2 and 3 pay **+1**, triangle pockets 1 and 4 pay **+2**. A miss costs **1**. You start with 12 credits (top-row ticks).

## Install

1. Plug Blinky in over USB-C.
2. Double-tap **RESET** on the back so a `Blinky2350` drive appears.
3. Copy this whole folder into `apps/` so you have:

```
apps/pachinko/__init__.py
apps/pachinko/icon.png
```

4. Eject the drive safely. The badge reboots into the menu.
5. Open **Pachinko**.

## Tuning

Pocket and island rectangles live at the top of `__init__.py` (`POCKETS`, `ISLANDS`, triangle helpers). If a ball falls through the wrong hole or hits a phantom wall, nudge those x/y values to match your cutouts.
