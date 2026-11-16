# Better Item Printer

A phone-friendly forecaster for the Item Printer in Pokémon Scarlet and Violet
(Indigo Disk). It predicts what a print job will give you at a given console
time, and searches upcoming times for the item or bonus you want.

**Open it here: https://timothy-hegglund.github.io/better-item-printer/**

Nothing to install; it runs in your browser and works on a phone. It is a web
interface for the calculation from
[kwsch/ItemPrinterDeGacha](https://github.com/kwsch/ItemPrinterDeGacha).

## How it works

The game picks a print job's rewards from your Switch's date and time, to the
second, at the moment you **first enter the printer**. Enter the printer at a
known second and you know the rewards.

1. **Line up the clocks.** In *Console ahead / behind PC*, enter how many seconds
   your Switch's clock is ahead (positive) or behind (negative) the clock shown
   in the app.
2. **Pick a job.** Choose the mode (Regular, Item bonus, Ball bonus) and 1, 5 or
   10 prints. The forecast shows the rewards for entering the printer right now.
3. **Find a good time.** Choose a desired item or bonus and a time frame
   (10 minutes to 24 hours):
   - **Soonest first** lists the first eight matching times.
   - **Most of item** lists the eight times with the most of that item in the
     job (ties go to the earliest), e.g. the most Master Balls in Ball bonus
     mode within the next hour.

   Matches count any reward in the job. Bonus searches need Regular mode;
   searching with 1 print is a quick way to trigger a bonus first.
4. **Hit the second.** Pick a result to get a countdown, and enter the printer
   when it reaches zero.
5. **Keep printing (optional).** Start a session from the forecast. After each
   job, stay in the printer, press **Next job in session**, and choose the next
   mode and quantity. End the session when you leave the printer.

Your mode, quantity and clock difference are remembered in that browser. Targets
and sessions are not shared between devices.

## Limitations

- Assumes both bonus modes and Stellar Tera Shards are unlocked (as the
  original tool does).
- It can't see your Switch: clock offset, input delay and timing are up to you.
- Phones may pause timers while locked; keep the page open and in front while
  timing. The clock resyncs when you come back.
- The online version uses your device's own clock and time zone. Long searches
  (24 hours) can take a few seconds on a phone.

## Run it on your PC instead (optional)

Use this if you want your phone to follow your PC's clock instead of its own.
It needs Python 3.10 or newer; no packages.

- **Windows:** double-click **Start Item Printer.bat**. It opens
  http://localhost:8080. Leave the window open.
- **Linux/macOS:** `python3 server.py` (stop with Ctrl+C). Other port:
  `python3 server.py --port 8081`.

To use it from a phone on the same Wi-Fi, click **Open on your phone** and open
the address it shows. If Windows Firewall asks, allow Python on **Private
networks**. Guest Wi-Fi, VPNs and client isolation can block the connection.
The server is meant for your home network only; don't forward its port to the
internet.

## Artwork

Item and Poké Ball images for all 156 printable rewards are included in
`web/art`. They come from the ItemPrinterDeGacha repository, with missing
sprites from [PKHeX](https://github.com/kwsch/PKHeX). The gallery also shows
every image from the original program. Tap an image to enlarge it or pick that
item. If any images are missing, `python3 artwork.py` downloads them again.

## Development

- `web/` is the whole site. `web/printer.js` does the calculation in the browser.
  `printer.py` and `server.py` are the Python version used by the PC server.
- Tests: `python3 -m unittest discover -s tests -v`. They include a check that
  the browser and Python calculations give the same results (needs Node.js).
- Every push to `main` runs the tests and publishes `web/` to GitHub Pages.

## Credits and license

Calculation and reward tables from
[kwsch/ItemPrinterDeGacha](https://github.com/kwsch/ItemPrinterDeGacha), which
credits PKHeX. Details in [THIRD_PARTY.md](THIRD_PARTY.md). Licensed under
GPL-3.0 ([LICENSE](LICENSE)).

Pokémon and all related names and artwork are owned by Nintendo, Creatures and
GAME FREAK. This is an unofficial fan project.
