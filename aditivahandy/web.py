"""Página local só de leitura. A configuração das máquinas fica no AditivaFlow."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import APP_NAME, APP_VERSION
from . import alexa

PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AditivaHandy</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.45 "Segoe UI", system-ui, sans-serif; background: #0e141b; color: #e7edf4; }
  main { max-width: 880px; margin: 0 auto; padding: 28px 18px 48px; }
  h1 { font-size: 1.4rem; margin: 0 0 6px; }
  p { margin: 0; color: #9aabbd; }
  .card { background: #17202a; border: 1px solid #2a3848; border-radius: 12px; padding: 16px; margin-top: 16px; }
  a.button, button { display: inline-block; margin-top: 12px; background: #3d8bfd; color: white; border: 0; border-radius: 8px; padding: 10px 14px; font: inherit; text-decoration: none; cursor: pointer; }
  button.ghost { background: transparent; color: #9aabbd; border: 1px solid #2a3848; }
  label { display: block; margin-top: 12px; color: #9aabbd; font-size: 0.85rem; }
  select, input, textarea { width: 100%; margin-top: 4px; background: #0e141b; color: #e7edf4; border: 1px solid #2a3848; border-radius: 8px; padding: 8px 10px; font: inherit; }
  textarea { min-height: 72px; resize: vertical; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; }
  code { font-size: 1.15rem; letter-spacing: 0.08em; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #2a3848; vertical-align: top; }
  th { color: #9aabbd; font-weight: 600; font-size: 0.85rem; }
  .log { white-space: pre-wrap; color: #c5d2e0; font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
  .hidden { display: none; }
</style>
</head>
<body>
<main>
  <h1>AditivaHandy</h1>
  <p>Este computador só recebe as máquinas que a sua conta liberar. IP, protocolo e código de acesso ficam no AditivaFlow.</p>
  <div class="card">
    <p id="status">Carregando…</p>
    <div id="pairing" class="hidden">
      <p style="margin-top:12px">Entre na sua conta para autorizar este computador.</p>
      <p style="margin-top:8px">Código <code id="code"></code></p>
      <a id="link" class="button" target="_blank" rel="noopener">Abrir o AditivaFlow</a>
    </div>
    <button id="relink" class="ghost" type="button">Gerar outro link</button>
  </div>
  <div class="card">
    <strong>Máquinas</strong>
    <table>
      <thead><tr><th>Máquina</th><th>Protocolo</th><th>IP</th><th>Estado</th><th>Progresso</th><th>Aviso</th></tr></thead>
      <tbody id="machines"></tbody>
    </table>
  </div>
  <div class="card">
    <strong>Alexa</strong>
    <p style="margin-top:8px">O botão abre a página de login da Amazon. A senha fica lá. Quando a Amazon terminar e a página parar, copie o endereço da barra do navegador e cole aqui. A plataforma ainda não manda comandos.</p>
    <p id="alexa-state" style="margin-top:8px"></p>
    <div id="alexa-login">
      <button id="alexa-open" type="button">Abrir login da Amazon</button>
      <label>Endereço da página final<input id="alexa-final-url" type="text" autocomplete="off" placeholder="https://www.amazon.com/ap/maplanding?..."></label>
      <button id="alexa-finish" class="ghost" type="button">Concluir</button>
    </div>
    <div id="alexa-ready" class="hidden">
      <label>Aparelho<select id="alexa-device"></select></label>
      <label>O que falar<textarea id="alexa-message" maxlength="400">Teste do AditivaHandy. Se você ouviu isso, o Echo recebeu o comando.</textarea></label>
      <div class="row">
        <button id="alexa-speak" type="button">Falar</button>
        <button id="alexa-announce" class="ghost" type="button">Anunciar</button>
        <button id="alexa-refresh" class="ghost" type="button">Atualizar aparelhos</button>
        <button id="alexa-logout" class="ghost" type="button">Sair da conta Amazon</button>
      </div>
    </div>
    <p id="alexa-result" style="margin-top:8px"></p>
  </div>
  <div class="card"><div id="log" class="log"></div></div>
</main>
<script>
async function refresh() {
  const data = await fetch("/api/status").then(r => r.json());
  document.getElementById("status").textContent = data.status || "";
  const pairing = data.pairing || {};
  const box = document.getElementById("pairing");
  if (pairing.url) {
    box.classList.remove("hidden");
    document.getElementById("code").textContent = pairing.user_code || "";
    const link = document.getElementById("link");
    link.href = pairing.url;
  } else {
    box.classList.add("hidden");
  }
  const body = document.getElementById("machines");
  body.replaceChildren();
  for (const row of data.machines || []) {
    const tr = document.createElement("tr");
    let progress = "";
    const value = Number(row.progress);
    if (Number.isFinite(value)) progress = Math.round(value) + "%";
    for (const text of [row.name, row.protocol, row.ip, row.state, progress, row.note || ""]) {
      const td = document.createElement("td");
      td.textContent = text || "";
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
  if (!(data.machines || []).length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.textContent = "Nenhuma máquina liberada ainda. Marque a integração como AditivaHandy na plataforma.";
    tr.appendChild(td);
    body.appendChild(tr);
  }
  document.getElementById("log").textContent = (data.log || []).join("\\n");
}
document.getElementById("relink").onclick = async () => {
  await fetch("/api/relink", { method: "POST" });
  refresh();
};
function showAlexa(data) {
  document.getElementById("alexa-login").classList.toggle("hidden", !!data.linked);
  document.getElementById("alexa-ready").classList.toggle("hidden", !data.linked);
  document.getElementById("alexa-state").textContent = data.linked
    ? "Conta conectada neste computador: " + (data.email || "")
    : "Nenhuma conta Amazon neste computador.";
  const select = document.getElementById("alexa-device");
  const current = select.value;
  select.replaceChildren();
  for (const device of data.devices || []) {
    const option = document.createElement("option");
    option.value = device.serial || "";
    const state = device.online ? "online" : "offline";
    option.textContent = (device.name || device.serial || "Echo") + " (" + state + ")";
    select.appendChild(option);
  }
  if (current) select.value = current;
  if (data.error) document.getElementById("alexa-result").textContent = data.error;
}
async function loadAlexa() {
  showAlexa(await fetch("/api/alexa").then(r => r.json()));
}
async function postAlexa(path, body) {
  const result = document.getElementById("alexa-result");
  result.textContent = "Aguarde…";
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  }).then(r => r.json());
  result.textContent = response.ok ? (response.message || "Pronto.") : (response.error || "A Amazon recusou.");
  if (response.linked || response.devices) showAlexa(response);
  else loadAlexa();
}
document.getElementById("alexa-open").onclick = async () => {
  const result = document.getElementById("alexa-result");
  const popup = window.open("about:blank", "_blank");
  result.textContent = "Abrindo a Amazon…";
  const response = await fetch("/api/alexa/login/start", { method: "POST" }).then(r => r.json());
  if (!response.ok || !response.url) {
    if (popup) popup.close();
    result.textContent = response.error || "Não consegui abrir a Amazon.";
    return;
  }
  if (popup) popup.location = response.url;
  else window.location = response.url;
  result.textContent = "Entre na conta na aba da Amazon. Quando a página parar, copie o endereço e cole abaixo.";
};
document.getElementById("alexa-finish").onclick = () => {
  const field = document.getElementById("alexa-final-url");
  postAlexa("/api/alexa/login/finish", { url: field.value });
  field.value = "";
};
document.getElementById("alexa-refresh").onclick = () => postAlexa("/api/alexa/devices");
document.getElementById("alexa-logout").onclick = () => postAlexa("/api/alexa/logout");
function sendAlexa(announcement) {
  postAlexa("/api/alexa/speak", {
    serial: document.getElementById("alexa-device").value,
    text: document.getElementById("alexa-message").value,
    announcement: announcement
  });
}
document.getElementById("alexa-speak").onclick = () => sendAlexa(false);
document.getElementById("alexa-announce").onclick = () => sendAlexa(true);
refresh();
loadAlexa();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    engine = None

    def log_message(self, fmt, *args):
        return

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 100_000))
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            self._json(self.engine.snapshot())
            return
        if path == "/api/alexa":
            self._json(alexa.public_status())
            return
        if path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/relink":
            self.engine.relink()
            self._json({"ok": True})
            return
        if path == "/api/alexa/login/start":
            self._json(alexa.begin_login())
            return
        if path == "/api/alexa/login/finish":
            body = self._body()
            self._json(alexa.finish_login(str(body.get("url") or "")))
            return
        if path == "/api/alexa/devices":
            self._json(alexa.refresh_devices())
            return
        if path == "/api/alexa/speak":
            body = self._body()
            self._json(alexa.speak(
                str(body.get("serial") or ""),
                str(body.get("text") or ""),
                bool(body.get("announcement")),
            ))
            return
        if path == "/api/alexa/logout":
            self._json(alexa.logout())
            return
        self.send_error(404)


def serve(engine, host: str, port: int) -> None:
    Handler.engine = engine
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"{APP_NAME} {APP_VERSION} em http://{host}:{port}", flush=True)
    if host in ("0.0.0.0", "::"):
        print(f"Na própria máquina: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        server.server_close()
