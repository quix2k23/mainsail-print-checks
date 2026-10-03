# Install tutorial

A step-by-step guide, no Linux experience needed. It takes about two minutes.

## Before you start

You need:

- The **IP address or hostname** of the machine that runs Mainsail (the address you type in your browser to open Mainsail, for example `192.168.1.50` or `mainsailos.local`).
- Its **login name and password**. On MainsailOS / most Raspberry Pi images the login name is `pi`, and the password is whatever you set when you flashed the SD card.
- A computer on the same network as the printer.

## Step 1: Open a terminal and log in

- **Windows 10/11:** open *Windows Terminal* or *PowerShell* from the Start menu.
- **macOS / Linux:** open *Terminal*.

Type this, replacing the address with yours, and press Enter:

```bash
ssh pi@192.168.1.50
```

The first time, it asks *"Are you sure you want to continue connecting?"*. Type `yes` and press Enter. Then type your password (nothing shows on screen while you type; that's normal) and press Enter.

You're in when you see a prompt like `pi@mainsailos:~ $`.

> No `ssh` command? Windows can use [PuTTY](https://www.putty.org/) instead: enter the address, click Open, then log in.

## Step 2: Run the installer

Copy and paste this one line, then press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/quix2k23/mainsail-print-checks/main/install.py | python3 -
```

You should see:

```
installed nozzle-check-xxxxxxxx.js into /home/pi/mainsail
Hard-refresh Mainsail (Ctrl+Shift+R), possibly twice, to pick it up.
```

**Want to read it before running it?** That's sensible with any script from the internet:

```bash
curl -fsSLO https://raw.githubusercontent.com/quix2k23/mainsail-print-checks/main/install.py
less install.py        # read it; press q to quit
python3 install.py
```

## Step 3: Refresh Mainsail

Open Mainsail in your browser and press **Ctrl+Shift+R** (**Cmd+Shift+R** on a Mac). If you don't see the new panel in step 4, press it a second time. Mainsail caches itself heavily, so the first reload can still show the old version.

## Step 4: Try it

1. Go to the **G-Code Files** tab and click a file, then **Print**.
2. In the dialog you'll see **Current nozzle diameter**. Type your nozzle size (for example `0.4`) and click out of the box. It's saved on the printer.
3. To test the warning safely, enter a size that *doesn't* match the file (for example `0.8` for a file sliced for `0.4`), press **Print**, and click **Cancel** on the popup. No print starts.

Set your real nozzle size once, and change it whenever you swap nozzles.

## Updating, removing

Log in over ssh again (step 1) and run:

```bash
python3 install.py            # update (re-run the curl line from step 2 to fetch the newest first)
python3 install.py --remove   # uninstall
```

After a **Mainsail update**, run the install line again: updates overwrite the files this tool edits.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied` / `no write access` | Log in as the user that owns Mainsail (normally `pi`), or put `sudo` in front: `curl ... \| sudo python3 -` |
| `could not find a Mainsail folder` | Tell it where Mainsail lives: `python3 install.py --dir /path/to/mainsail` (the folder containing `index.html` and `sw.js`) |
| `python3: command not found` | Install Python 3: `sudo apt install python3` |
| Installed but nothing changed in the dialog | Hard-refresh again. If it still doesn't show, try a private/incognito window to rule out caching, then open an issue with your Mainsail version. |
| Nozzle popup never appears | Your slicer may not write the nozzle diameter into the G-code. Check **G-Code Files**, click a file, and look for a "Nozzle diameter" value in its details. No value, no check. |

## Installing from your own PC instead

If you'd rather not log in to the printer, run this on your PC (needs Python 3 and ssh), after downloading `install.py` from this repo:

```bash
python3 install.py --host pi@192.168.1.50
```

Linux desktops can also use `install-gui.sh`, which asks for the address, login and password in pop-up boxes.
