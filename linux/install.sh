#!/usr/bin/env bash
# Per-user launcher installation. Full-device tunnel setup prompts separately through polkit.
set -euo pipefail
[ "$(id -u)" != 0 ] || { echo 'Run this installer as your desktop user.' >&2; exit 1; }
SOURCE="$(cd -- "$(dirname -- "$0")/.." && pwd)"
python3 -c 'import PySide6' || { echo 'Install the Qt bindings first: Arch: sudo pacman -S python-pyside6 qt6-wayland; Debian/Ubuntu: install python3-pyside6.qtwidgets and qt6-wayland.' >&2; exit 1; }
TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/culvert-app"
mkdir -p "$TARGET" "$HOME/.local/bin" "${XDG_DATA_HOME:-$HOME/.local/share}/applications" "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
if [ "$SOURCE" != "$TARGET" ]; then
  mkdir -p "$TARGET/linux" "$TARGET/configs" "$TARGET/assets" "$TARGET/cores/linux" "$TARGET/licenses"
  for file in "$SOURCE"/linux/*.py "$SOURCE"/linux/*.sh "$SOURCE"/linux/*.json "$SOURCE"/linux/*.pem "$SOURCE"/linux/*.service "$SOURCE"/linux/README.md; do cp "$file" "$TARGET/linux/"; done
  cp "$SOURCE/configs/singbox-tun.json" "$TARGET/configs/"
  cp "$SOURCE/assets/Culvert.ico" "$SOURCE/assets/Culvert.png" "$SOURCE/assets/Culvert-mark.png" "$SOURCE/assets/Culvert.svg" "$SOURCE/assets/Culvert-mark.svg" "$TARGET/assets/"
  if [ -f "$SOURCE/cores/linux/xray" ]; then cp "$SOURCE/cores/linux/xray" "$SOURCE/cores/linux/sing-box" "$TARGET/cores/linux/"; fi
  cp "$SOURCE/licenses/Xray.txt" "$SOURCE/licenses/sing-box.txt" "$SOURCE/licenses/Linux-engines.md" "$TARGET/licenses/"
fi
printf '#!/usr/bin/env bash\nexec /usr/bin/python3 %q "$@"\n' "$TARGET/linux/app.py" > "$HOME/.local/bin/culvert"
chmod 755 "$HOME/.local/bin/culvert" "$TARGET/linux/"*.sh
cp "$TARGET/assets/Culvert.png" "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps/culvert.png"
python3 - "$HOME/.local/bin/culvert" "${XDG_DATA_HOME:-$HOME/.local/share}/applications/culvert.desktop" <<'PY'
import sys
from pathlib import Path
launcher=sys.argv[1].replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')
Path(sys.argv[2]).write_text('[Desktop Entry]\nType=Application\nName=Culvert\nComment=Personal tunnel with a black and crimson dashboard\nExec="'+launcher+'"\nIcon=culvert\nTerminal=false\nCategories=Network;Utility;\nStartupWMClass=culvert\n')
PY
printf 'Culvert installed in your app launcher. Open it and choose Settings → Finish system setup once.\n'
