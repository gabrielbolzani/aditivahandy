#!/usr/bin/env bash
# Instala o AditivaHandy e deixa a ponte voltando depois de cada reinício.
# Com Docker, sobe o container. Sem Docker, usa o Python 3.12 ou mais novo e o systemd do usuário.
set -euo pipefail

VERSION=1.2.1
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
  local candidate found
  for candidate in python3 python3.14 python3.13 python3.12; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    found=$("$candidate" -c 'import sys; print(sys.executable if sys.version_info[:2] >= (3, 12) else "")' 2>/dev/null || true)
    if [ -n "$found" ]; then
      printf '%s\n' "$found"
      return
    fi
  done
  say "O AditivaHandy precisa do Python 3.12 ou mais novo quando não há Docker."
  say "Instalação: ${PYTHON_PAGE}"
  say "Debian, Ubuntu e Raspberry Pi OS: sudo apt install python3 python3-venv python3-pip"
  say "Fedora: sudo dnf install python3"
  exit 1
}

install_service() {
  local python_bin="$1"
  if ! "$python_bin" -m venv "${DEST}/.venv"; then
    say "Não foi possível criar o ambiente virtual do Python."
    say "Debian, Ubuntu e Raspberry Pi OS: sudo apt install python3-venv"
    exit 1
  fi
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
  systemctl --user enable aditivahandy.service
  systemctl --user restart aditivahandy.service
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "${USER}" || true
  fi
  say "A ponte está no serviço do usuário e abre sozinha quando a máquina liga."
  show_address
}

show_address() {
  say "Neste computador: http://127.0.0.1:8787"
  say "De outro computador da rede: http://$(hostname).local:8787"
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
    show_address
    exit 0
  fi
  say "Docker não está disponível. A instalação usa o Python do sistema."
  local python_bin
  python_bin=$(require_python)
  install_service "$python_bin"
}

main
