#!/usr/bin/env bash
# Instala o AditivaHandy e deixa a ponte voltando depois de cada reinício.
# Com Docker, sobe o container. Sem Docker, usa Python 3.12 e o systemd do usuário.
set -euo pipefail

VERSION=1.2.0
DEST="${HOME}/.local/share/aditivahandy"
PYTHON_PAGE="https://www.python.org/downloads/"

say() {
  printf '%s\n' "$*" >&2
}

copy_tree() {
  local src="$1"
  local dest="$2"
  mkdir -p "$dest"
  local src_real dest_real
  src_real=$(cd "$src" && pwd)
  dest_real=$(cd "$dest" && pwd)
  if [ "$src_real" = "$dest_real" ]; then
    return
  fi
  tar -C "$src_real" --exclude .venv --exclude __pycache__ --exclude windows -cf - . | tar -C "$dest_real" -xf -
}

locate_source() {
  local here=""
  if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  fi
  if [ -n "$here" ] && [ -f "$here/Dockerfile" ]; then
    printf '%s\n' "$here"
    return
  fi
  local tmp
  tmp=$(mktemp -d)
  say "Baixando o AditivaHandy ${VERSION}."
  curl -fsSL "https://github.com/gabrielbolzani/aditivahandy/archive/refs/tags/v${VERSION}.tar.gz" | tar -xz -C "$tmp"
  printf '%s\n' "$tmp"/aditivahandy-*
}

use_docker() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

require_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    local found
    found=$(python3 -c 'import sys; print(sys.executable if sys.version_info[:2] == (3, 12) else "")')
    if [ -n "$found" ]; then
      printf '%s\n' "$found"
      return
    fi
  fi
  say "O AditivaHandy precisa do Python 3.12 quando não há Docker."
  say "Instalação: ${PYTHON_PAGE}"
  say "Debian e Ubuntu: sudo apt install python3.12 python3.12-venv python3-pip"
  say "Fedora: sudo dnf install python3.12"
  exit 1
}

install_service() {
  local python_bin="$1"
  "$python_bin" -m venv "${DEST}/.venv"
  "${DEST}/.venv/bin/python" -m pip install --disable-pip-version-check -r "${DEST}/requirements.txt"
  mkdir -p "${HOME}/.config/systemd/user"
  cat > "${HOME}/.config/systemd/user/aditivahandy.service" <<EOF
[Unit]
Description=AditivaHandy
After=network-online.target

[Service]
WorkingDirectory=${DEST}
ExecStart=${DEST}/.venv/bin/python -m aditivahandy
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now aditivahandy.service
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "${USER}" || true
  fi
  say "A ponte está no serviço do usuário e volta quando a sessão inicia."
  say "Abra http://127.0.0.1:8787 neste computador."
}

main() {
  local src
  src=$(locate_source)
  copy_tree "$src" "$DEST"
  if use_docker; then
    say "Docker encontrado. A ponte vai rodar em container e voltar depois de reiniciar."
    if docker compose version >/dev/null 2>&1; then
      (cd "$DEST" && docker compose up -d --build)
    elif command -v docker-compose >/dev/null 2>&1; then
      (cd "$DEST" && docker-compose up -d --build)
    else
      say "O Docker está instalado, mas o comando docker compose não está disponível."
      exit 1
    fi
    say "Abra http://127.0.0.1:8787 neste computador."
    exit 0
  fi
  say "Docker não está disponível. A instalação usa o Python 3.12."
  local python_bin
  python_bin=$(require_python)
  install_service "$python_bin"
}

main
