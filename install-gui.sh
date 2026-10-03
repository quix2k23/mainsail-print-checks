#!/bin/bash
# One-click installer: asks for the Mainsail machine's IP, login and password, then
# installs the print checks (install.py, same folder) over ssh.
# The password is typed into a dialog and handed straight to ssh; it is never stored.
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

if command -v kdialog >/dev/null; then
  ask()    { kdialog --title "Mainsail nozzle check" --inputbox "$1" "$2"; }
  askpw()  { kdialog --title "Mainsail nozzle check" --password "$1"; }
  show()   { kdialog --title "Mainsail nozzle check" --msgbox "$1"; }
  err()    { kdialog --title "Mainsail nozzle check" --error "$1"; }
elif command -v zenity >/dev/null; then
  ask()    { zenity --entry --title "Mainsail nozzle check" --text "$1" --entry-text "$2"; }
  askpw()  { zenity --entry --hide-text --title "Mainsail nozzle check" --text "$1"; }
  show()   { zenity --info --title "Mainsail nozzle check" --text "$1"; }
  err()    { zenity --error --title "Mainsail nozzle check" --text "$1"; }
else
  echo "Needs kdialog or zenity" >&2; exit 1
fi

IP=$(ask "Mainsail IP address or hostname:" "") || exit 0
USER_=$(ask "Login name on that machine (e.g. pi):" "pi") || exit 0
[ -n "$IP" ] && [ -n "$USER_" ] || { err "IP and login name are required."; exit 1; }
PW=$(askpw "Password for $USER_@$IP\n(leave empty if ssh key login is set up):") || exit 0

# ssh reads the password from this helper instead of a terminal
ASK=$(mktemp); trap 'rm -f "$ASK"' EXIT
printf '#!/bin/sh\nprintf "%%s\\n" "$NZ_PW"\n' > "$ASK"; chmod 700 "$ASK"
export NZ_PW="$PW" SSH_ASKPASS="$ASK" SSH_ASKPASS_REQUIRE=force DISPLAY="${DISPLAY:-:0}"

OUT=$(python3 "$HERE/install.py" --host "$USER_@$IP" 2>&1)
RC=$?
unset NZ_PW
if [ $RC -eq 0 ]; then
  show "Done.\n\n$OUT"
else
  err "Install failed (is the IP/login/password right, and does that login own the Mainsail folder?)\n\n$OUT"
  exit 1
fi
