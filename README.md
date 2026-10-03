# Mainsail Print Checks

Pre-print safety prompts for the **Start Print** dialog in [Mainsail](https://docs.mainsail.xyz/), the Klipper web interface.

It stops the classic "oops" prints: the wrong nozzle fitted, the previous filament still loaded, or an abrasive carbon/glass-fibre filament going through a brass nozzle.

## What it adds

When you start a print from the file list (or **History → Reprint**), the dialog gains a small panel, and pressing **Print** can raise warning popups.

```
┌ Start print ─────────────────────────────────────┐
│ Do you want to start "bracket-PA12-CF.gcode"?    │
│                                                  │
│ Current nozzle diameter [ 0.4 ] mm               │
│ This file was sliced for a 0.6 mm nozzle - does  │
│   not match                                      │
│ This file is PA12-CF. Use a hardened nozzle for  │
│   CF and GF (carbon / glass fibre) filaments...  │
│ Reminder: check the Z-offset height before       │
│   printing                                       │
│                                   [Cancel] [Print]│
└──────────────────────────────────────────────────┘
```

| Check | When it appears |
|---|---|
| **Current nozzle box** | Always. Type your nozzle size once; it is saved on the printer's Moonraker database, so every browser and device shares it. |
| **Nozzle size mismatch** popup | The file was sliced for a different nozzle diameter than the one you entered (or you haven't entered one). Buttons: *Cancel* / *Print anyway*. |
| **Hardened nozzle** popup | The file's filament name or type looks like CF / GF / carbon fibre / glass fibre (e.g. `PA12-CF`, `PETG CF`, `PA-GF30`). Shown every time, even if the size matches. Button: *Hardened nozzle fitted*. |
| **"Have you definitely changed filament?"** popup | The file's filament type differs from the type used by your most recent print in Mainsail's history. A separate popup, shown after the nozzle one. |
| **Z-offset reminder** | Always shown as a line in the dialog. |

The popups never block you permanently: you can always choose to print anyway. They are a reminder, not a safety interlock.

## Requirements

- Mainsail with Moonraker (tested on **Mainsail v2.19.0**; other 2.x versions will probably work, see [Limitations](#limitations)).
- Python 3 on the machine that serves Mainsail (MainsailOS / any Raspberry Pi image has it).
- G-code files carrying slicer metadata. Moonraker reads `nozzle_diameter`, `filament_type` and `filament_name` from the slicer's comments (PrusaSlicer and OrcaSlicer fill these in). If a file has none, that check is simply skipped.
- Write access to Mainsail's web folder (usually the `pi` user, which owns `~/mainsail`).

## Install

**New to ssh?** Follow the [step-by-step install tutorial](INSTALL.md). The short version is below.

Log in to the machine that runs Mainsail (for example `ssh pi@your-printer.local`) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/quix2k23/mainsail-print-checks/main/install.py | python3 -
```

Prefer to read it first? Download it, look at it, then run it:

```bash
curl -fsSLO https://raw.githubusercontent.com/quix2k23/mainsail-print-checks/main/install.py
less install.py
python3 install.py
```

Then **hard-refresh Mainsail** (Ctrl+Shift+R), possibly twice. Mainsail caches itself aggressively with a service worker, so the first reload may still show the old page.

### Other ways to run it

```bash
python3 install.py                      # on the Mainsail machine; folder is auto-detected
python3 install.py --dir /path/to/mainsail    # unusual install location
python3 install.py --host pi@printer.local    # run from your PC over ssh, nothing to copy
python3 install.py --remove             # uninstall
```

`install-gui.sh` (needs `kdialog` or `zenity`) is a point-and-click wrapper for Linux desktops: it asks for the printer's address, login and password, then runs the installer over ssh. The password goes straight to ssh and is never stored.

### Updating and removing

- **Update:** run the installer again. It replaces the previous copy cleanly.
- **After a Mainsail update:** Mainsail overwrites the two files this tool edits, so just run the installer again.
- **Remove:** `python3 install.py --remove`. Your original `index.html` and `sw.js` are also kept next to the originals as `*.pre-nozzle-check`.

## How it works

Mainsail is a compiled Vue app whose files are cached for a year, so patching its bundle never reaches browsers reliably. Instead the installer:

1. Copies one small JavaScript file into Mainsail's web folder. Its filename contains a content hash, so a new version always has a new URL.
2. Adds one `<script defer>` tag to `index.html` (which is never cached).
3. Updates the revision of `index.html` in Mainsail's service worker (`sw.js`) so browsers re-fetch it.

The script finds the Start Print dialog while it is open, then wraps its `startPrint` function. Your nozzle size is stored through Moonraker's database API (namespace `nozzle_check`). The "last print" comes from Moonraker's job history. Nothing leaves your network.

## Limitations

- It hooks Mainsail internals (the dialog's Vue instance). A future Mainsail release could change that and silently disable the popups; nothing breaks, you just lose the checks. Re-run the installer after updates, and open an issue if it stops working.
- Only the Start Print dialog is covered: starting a job from the **job queue** and the separate mobile layouts are not.
- The "changed filament" check compares *types* (PLA, PETG, ...), and only against the last job Mainsail recorded. It can't know if you swapped spools without printing.
- The CF/GF detection is a name match on the slicer's filament name/type. Name your filament profiles with `CF` / `GF` and it works.
- English text only.

## Development

```
src/nozzle-check.js        the in-browser script
src/install.template.py    the installer, with a placeholder for the script
build.py                   embeds the script into install.py
install.py                 generated, self-contained installer (what users run)
install-gui.sh             optional desktop prompt wrapper
```

After editing `src/`, run `python3 build.py` and commit the regenerated `install.py`.

## Disclaimer

These prompts are an aid, not a guarantee. You are still responsible for what is fitted to your printer. Provided as-is, without warranty; see [LICENSE](LICENSE).
