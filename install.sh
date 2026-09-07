#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${XDG_STATE_HOME:-$HOME/.local/state}/tempered-os/backups/$STAMP"
YES=false
PACKAGES=true

REPO_PACKAGES=(
    hyprland hyprpaper hypridle hyprlock xdg-desktop-portal-hyprland
    quickshell python python-gobject python-pillow gtk4 libadwaita
    kitty swaync swayosd brightnessctl ddcutil playerctl
    grim slurp wl-clipboard cliphist btop fastfetch nautilus pavucontrol
    pipewire pipewire-pulse wireplumber libnotify networkmanager
    network-manager-applet bluez bluez-utils blueman power-profiles-daemon
    mission-center polkit-gnome wdisplays hyprsunset flatseal
    gnome-disk-utility baobab archlinux-contrib
    inter-font ttf-jetbrains-mono-nerd papirus-icon-theme adw-gtk-theme
    jq desktop-file-utils imagemagick ffmpeg
)
AUR_PACKAGES=(wlogout clipse bibata-cursor-theme waypaper mpvpaper)

managed=(
    .config/hypr .config/quickshell/tempered .config/quickshell/tempered-boot
    .config/swaync .config/wlogout .config/gtk-3.0
    .config/gtk-4.0 .config/kitty .config/tempered .local/lib/tempered
    .local/bin/tempered-theme .local/bin/tempered-settings
    .local/bin/tempered-control .local/bin/tempered-capture
    .local/bin/tempered-brightness .local/bin/tempered-boot
    .local/bin/tempered-launcher .local/bin/tempered-wallpaper-apply
    .local/bin/tempered-wallpaper-picker .local/share/tempered-os
    .local/share/applications/io.github.dsksnkz.TemperedOS.Settings.desktop
    .local/share/applications/io.github.dsksnkz.TemperedOS.Boot.desktop
    .local/share/applications/io.github.dsksnkz.TemperedOS.Launcher.desktop
    .local/share/applications/io.github.dsksnkz.TemperedOS.Wallpaper.desktop
    .config/quickshell/tempered-launcher .config/waypaper/config.ini
    .local/lib/orbitos .local/state/orbitos
    .local/bin/orbitos-boot .local/bin/orbitos-game .local/bin/orbitos-launcher
    .local/bin/orbitos-settings .local/bin/orbitos-tools
)

usage() {
    printf '%s\n' 'Usage: ./install.sh [--yes] [--no-packages]' '' \
        '  --yes          accept safe defaults; monitor state is still preserved' \
        '  --no-packages  deploy the dotfiles without installing packages'
}

ask() {
    local prompt="$1" default="${2:-yes}" answer
    [[ "$YES" == true ]] && return 0
    if [[ "$default" == yes ]]; then
        read -r -p "$prompt [Y/n] " answer
        [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]
    else
        read -r -p "$prompt [y/N] " answer
        [[ "$answer" =~ ^[Yy]$ ]]
    fi
}

step() {
    local label="$1"; shift
    printf '  ◌ %s' "$label"
    if "$@"; then
        printf '\r  ● %s\n' "$label"
    else
        local status=$?
        printf '\r  × %s\n' "$label" >&2
        return "$status"
    fi
}

backup_existing() {
    local path found=false
    mkdir -p "$BACKUP"
    for path in "${managed[@]}"; do
        if [[ -e "$HOME/$path" || -L "$HOME/$path" ]]; then
            (cd "$HOME" && cp -a --parents "$path" "$BACKUP")
            found=true
        fi
    done
    [[ "$found" == true ]] || rmdir "$BACKUP"
}

install_packages() {
    local package helper
    local -a missing=() aur_missing=()
    for package in "${REPO_PACKAGES[@]}"; do
        pacman -Q "$package" >/dev/null 2>&1 || missing+=("$package")
    done
    ((${#missing[@]} == 0)) || sudo pacman -S --needed --noconfirm "${missing[@]}"

    helper="$(command -v paru 2>/dev/null || command -v yay 2>/dev/null || true)"
    if [[ -n "$helper" ]]; then
        for package in "${AUR_PACKAGES[@]}"; do
            pacman -Q "$package" >/dev/null 2>&1 || aur_missing+=("$package")
        done
        ((${#aur_missing[@]} == 0)) || "$helper" -S --needed --noconfirm "${aur_missing[@]}"
    else
        printf '\n    paru/yay not found; install the listed AUR packages manually for every surface.\n'
    fi
}

capture_monitors() {
    local destination="$HOME/.config/hypr/tempered-monitor.lua"
    command -v hyprctl >/dev/null || return 0
    command -v jq >/dev/null || return 0
    [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]] || return 0
    mkdir -p "$(dirname "$destination")"
    hyprctl monitors all -j | jq -r '
      .[] | if .disabled then
        "hl.monitor({ output = " + (.name|tojson) + ", disabled = true })"
      else
        "hl.monitor({ output = " + (.name|tojson) +
        ", mode = " + ((.width|tostring) + "x" + (.height|tostring) + "@" + (.refreshRate|tostring)|tojson) +
        ", position = " + ((.x|tostring) + "x" + (.y|tostring)|tojson) +
        ", scale = " + (.scale|tostring) + " })"
      end' > "$destination"
}

deploy() {
    local top
    for top in .config .local; do
        cp -a "$ROOT/$top/." "$HOME/$top/"
    done
    chmod +x "$HOME/.local/bin"/tempered-* "$HOME/.config/quickshell/tempered/status.py"
    chmod +x "$HOME/.local/share/tempered-os/qs-wallpaper-picker/scripts"/*.sh
    chmod +x "$HOME/.local/share/tempered-os/qs-wallpaper-picker/scripts"/*.py
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
}

configure_waypaper() {
    local config="$HOME/.config/waypaper/config.ini"
    local hook='post_command = ~/.local/bin/tempered-theme $wallpaper'
    if [[ ! -f "$config" ]]; then
        mkdir -p "$(dirname "$config")" "$HOME/.config/wallpapers"
        printf '%s\n' '[Settings]' 'backend = hyprpaper' 'folder = ~/.config/wallpapers' \
            'monitors = All' 'fill = fill' "$hook" > "$config"
        return
    fi
    if grep -q '^post_command[[:space:]]*=' "$config"; then
        sed -i "s|^post_command[[:space:]]*=.*|$hook|" "$config"
    else
        printf '%s\n' "$hook" >> "$config"
    fi
}

draw_theme() {
    local wallpaper
    wallpaper="$(waypaper --list 2>/dev/null | jq -r '.[0].wallpaper // empty' 2>/dev/null || true)"
    [[ -f "$wallpaper" ]] || wallpaper="$(jq -r '.wallpaper // empty' "$HOME/.config/tempered/settings.json" 2>/dev/null || true)"
    [[ -f "$wallpaper" ]] || wallpaper="$HOME/.config/tempered/wallpapers/default.png"
    "$HOME/.local/bin/tempered-theme" "$wallpaper" >/dev/null
}

retire_orbitos() {
    local path
    local targets=(
        .local/bin/orbitos-boot .local/bin/orbitos-game .local/bin/orbitos-launcher
        .local/bin/orbitos-settings .local/bin/orbitos-tools .local/lib/orbitos
        .local/share/applications/io.github.dsksnkz.OrbitOS.Boot.desktop
        .local/share/applications/io.github.dsksnkz.OrbitOS.GameAccelerator.desktop
        .local/share/applications/io.github.dsksnkz.OrbitOS.Launcher.desktop
        .local/share/applications/io.github.dsksnkz.OrbitOS.Settings.desktop
        .local/share/applications/io.github.dsksnkz.OrbitOS.desktop
        .local/state/orbitos
        .config/quickshell/BarButton.qml .config/quickshell/HomeScreen.qml
        .config/quickshell/TimeHub.qml .config/quickshell/UtilityTile.qml
        .config/quickshell/BrightnessHub.qml .config/quickshell/orbitos-boot
        .config/quickshell/scripts .config/quickshell/shell.qml
        .config/hypr/ORBITOS-NOTES.md .config/hypr/orbitos.png
        .config/hypr/orbitos.svg .config/hypr/hyprmod
    )
    for path in "${targets[@]}"; do
        [[ -e "$HOME/$path" || -L "$HOME/$path" ]] || continue
        if [[ -d "$HOME/$path" && ! -L "$HOME/$path" ]]; then
            rm -rf -- "$HOME/$path"
        else
            rm -f -- "$HOME/$path"
        fi
    done
}

stop_legacy_shell() {
    local pid
    command -v quickshell >/dev/null || return 0
    while read -r pid; do
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        quickshell kill --pid "$pid" >/dev/null 2>&1 || true
    done < <(quickshell list --all 2>/dev/null | awk '
        /Process ID:/ { pid=$3 }
        /Shell ID: orbitos-shell/ { print pid }
    ')
}

while (($#)); do
    case "$1" in
        -y|--yes) YES=true ;;
        --no-packages) PACKAGES=false ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; usage; exit 2 ;;
    esac
    shift
done

printf '\n  TEMPERED OS\n  color from place · shape from use\n\n'
grep -q '^ID=arch$' /etc/os-release || { printf 'Tempered OS currently targets Arch Linux.\n' >&2; exit 1; }

if [[ "$PACKAGES" == true ]] && ask 'Install the software used by Tempered OS?' yes; then
    sudo -v
    step 'Installing desktop dependencies' install_packages
fi

if ask 'Back up the desktop files Tempered OS will manage?' yes; then
    step 'Preserving the current desktop' backup_existing
    [[ -d "$BACKUP" ]] && printf '    %s\n' "$BACKUP"
else
    ask 'Continue without a backup?' no || exit 0
fi

# Capture before deploy: the repository never ships somebody else's connector layout.
step 'Remembering connected displays' capture_monitors
step 'Placing the new desktop' deploy
step 'Connecting Waypaper colors' configure_waypaper
step 'Drawing colors from the wallpaper' draw_theme

if [[ -e "$HOME/.local/bin/orbitos-settings" ]] && ask 'Remove the retired OrbitOS surfaces (keep Orbit Apps)?' yes; then
    stop_legacy_shell
    step 'Retiring OrbitOS surfaces' retire_orbitos
fi

if [[ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]]; then
    quickshell kill --path "$HOME/.config/quickshell/tempered/shell.qml" >/dev/null 2>&1 || true
    hyprctl reload >/dev/null
    quickshell --daemonize --path "$HOME/.config/quickshell/tempered/shell.qml"
fi

printf '\n  Tempered OS is installed. Log out once to see the complete boot handoff.\n\n'
