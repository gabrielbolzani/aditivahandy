# AditivaHandy

Serviço local, sem janela, que liga as impressoras da rede ao AditivaFlow. O cadastro da máquina (IP, porta, protocolo, código de acesso ou API key) fica na plataforma. Este programa só recebe o que a conta liberar.

Acompanha o estado pelo navegador, em qualquer computador da rede. Não há tela de configuração.

O login continua o do AditivaFlow: a página local mostra um link. Você abre, entra na conta e aprova este computador. O vínculo fica em `%APPDATA%\AditivaHandy\device.json` no Windows e em `~/.config/aditivahandy/device.json` no Linux.

## O que ele faz

- Pareia pela conta e guarda só o token do computador.
- Conecta no gateway `handy-gateway`.
- Aplica o `config.snapshot` das máquinas com integração AditivaHandy.
- Fala com Bambu Lab, Moonraker/Klipper e Elegoo usando os drivers do Hub.
- Envia telemetria a cada 3 s, quadro de câmera da Bambu e miniatura quando o driver tiver a imagem.
- Conta localmente só o tempo em impressão e manda esse acréscimo. O horímetro oficial fica no AditivaFlow: uma correção sua permanece, e o tempo novo é somado em cima dela.
- Abre o login da Amazon neste computador e pode pedir para um Echo falar. A senha fica na página da Amazon. A plataforma ainda não envia esses comandos.
- Executa pausa, retomada, parada, LED, velocidade e ventilador pedidos pela plataforma.

OctoPrint, PrusaLink e o protocolo "outro" aparecem na lista, mas ainda não têm driver.

## Como rodar

Na pasta do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

No Linux ou no Raspberry Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Abra `http://IP-DA-MAQUINA:8787`. A porta muda com `--port` ou com a variável `HANDY_PORT`.

Os drivers de impressora ficam no repositório `3d_printer_connection_hub`, ao lado desta pasta (`../3d_printer_connection_hub`) ou no caminho da variável `ADITIVA_HUB_DIR`.

A versão do programa está só em `aditivahandy/__init__.py`. Cada computador envia esse número no pareamento e no `handy.health`. A plataforma compara com a release publicada em https://github.com/gabrielbolzani/aditivahandy. O botão Atualizar grava um pedido; a troca automática dos arquivos entra numa versão seguinte.
