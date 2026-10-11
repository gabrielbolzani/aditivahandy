# AditivaHandy

Ponte local entre as impressoras da sua rede e o AditivaFlow. O cadastro da máquina fica na plataforma. Este programa só recebe o que a sua conta liberar.

A versão do programa está só em `aditivahandy/__init__.py`. Os arquivos para baixar ficam em https://github.com/gabrielbolzani/aditivahandy/releases.

## Antes de instalar

O programa precisa falar com as impressoras na mesma rede. O computador ou o Raspberry tem que estar ligado nessa rede.

**Python 3.12**, de 64 bits no Windows.

- Windows: https://www.python.org/downloads/windows/
- Linux: https://www.python.org/downloads/
- Instalador direto do Windows, caso queira baixar à mão: https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe

No Windows você não precisa instalar o Python antes. O `AditivaHandy.exe` procura o 3.12 e, se não achar, baixa esse instalador e instala para o seu usuário.

No Linux, se o Docker estiver instalado e respondendo, a instalação usa container e o Python já vai dentro da imagem. Sem Docker, instale o Python 3.12 antes:

- Debian e Ubuntu: `sudo apt install python3.12 python3.12-venv python3-pip`
- Fedora: `sudo dnf install python3.12`

## Windows

1. Abra https://github.com/gabrielbolzani/aditivahandy/releases e baixe o arquivo que termina com `-windows.zip`.
2. Extraia a pasta inteira. Não rode o programa de dentro do zip.
3. Abra `AditivaHandy.exe`.
4. Na primeira vez, espere a instalação do Python 3.12 e das bibliotecas. A janela mostra o andamento.
5. Quando a ponte estiver no ar, clique em **Abrir painel**. O endereço é `http://127.0.0.1:8787`.
6. Na página, abra o link do AditivaFlow, entre na sua conta e autorize este computador.

A opção **Iniciar com o Windows** já vem ligada. O programa abre de novo quando você entra no computador.

Minimizar a janela, ou fechar pelo X, deixa o AditivaHandy na barra de tarefas. A ponte continua rodando. Só o botão **Sair** encerra.

O vínculo deste computador fica em `%APPDATA%\AditivaHandy\device.json`.

## Linux

No computador ou no Raspberry, rode:

```bash
curl -fsSL https://raw.githubusercontent.com/gabrielbolzani/aditivahandy/v1.2.0/install.sh | bash
```

O script escolhe um dos dois caminhos:

- **Com Docker.** Sobe um container na rede do computador (`network_mode: host`) com `restart: unless-stopped`. Depois de reiniciar a máquina, a ponte volta sozinha. O Python 3.12 já está na imagem.
- **Sem Docker.** Confere o Python 3.12. Se faltar, para e mostra os links acima. Se estiver instalado, copia o programa para `~/.local/share/aditivahandy`, cria o ambiente virtual e registra o serviço do usuário. Também aplica `loginctl enable-linger`, para continuar rodando sem alguém logado na tela, como num Raspberry.

Quando o comando terminar, abra `http://127.0.0.1:8787` nesse computador, entre no AditivaFlow e autorize.

O arquivo que termina com `-linux.tar.gz`, na mesma página de releases, traz o `install.sh`, o `Dockerfile` e o `docker-compose.yml`. Dentro da pasta extraída, `bash install.sh` faz a mesma instalação.

Para ver se o serviço sem Docker está no ar: `systemctl --user status aditivahandy`. Para ver o container: `docker compose -f ~/.local/share/aditivahandy/docker-compose.yml ps`.

O vínculo fica em `~/.config/aditivahandy/device.json`.

## Depois de instalar

A porta padrão é `8787`. Ela muda com `--port` ou com a variável `HANDY_PORT`.

A página local mostra um código e um link. Você entra na conta do AditivaFlow e aprova este computador uma vez. A partir daí a plataforma envia as máquinas com integração AditivaHandy: IP, protocolo e código de acesso não ficam gravados neste programa.

Ele fala com Bambu Lab, Moonraker/Klipper e Elegoo, manda o estado a cada 3 segundos e soma o tempo em impressão em cima do horímetro da plataforma. OctoPrint, PrusaLink e o protocolo "outro" ainda não têm driver.

Os drivers vêm em `vendor/3d_printer_connection_hub`. A variável `ADITIVA_HUB_DIR` aponta para outra cópia, se você tiver uma.
