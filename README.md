# AditivaHandy

Ponte local entre as impressoras da sua rede e o AditivaFlow. O cadastro da máquina fica na plataforma. Este programa só recebe o que a sua conta liberar.

A versão do programa está só em `aditivahandy/__init__.py`. Os arquivos para baixar ficam em https://github.com/gabrielbolzani/aditivahandy/releases.

## Antes de instalar

O programa precisa falar com as impressoras na mesma rede. O computador ou o Raspberry tem que estar ligado nessa rede.

**Python 3.12 ou mais novo.** No Windows, o programa usa o 3.12 de 64 bits.

- Windows: https://www.python.org/downloads/windows/
- Linux: https://www.python.org/downloads/
- Instalador direto do Windows, caso queira baixar à mão: https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe

No Windows você não precisa instalar o Python antes. O `AditivaHandy.exe` procura o 3.12 e, se não achar, baixa esse instalador e instala para o seu usuário.

No Linux, se o Docker estiver instalado e respondendo, a instalação usa container e o Python já vai dentro da imagem. Sem Docker, a instalação usa o Python do sistema, desde que seja 3.12 ou mais novo. O Raspberry Pi OS atual e o Ubuntu 24.04 já vêm com uma versão que serve. Se faltar algo:

- Debian, Ubuntu e Raspberry Pi OS: `sudo apt install python3 python3-venv python3-pip`
- Fedora: `sudo dnf install python3`

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

No computador, rode:

```bash
curl -fsSL https://raw.githubusercontent.com/gabrielbolzani/aditivahandy/v1.3.0/install.sh | bash
```

O script escolhe um dos dois caminhos:

- **Com Docker.** Sobe um container na rede do computador (`network_mode: host`) com `restart: unless-stopped`. Depois de reiniciar a máquina, a ponte volta sozinha. O Python já está na imagem.
- **Sem Docker.** Procura o Python 3.12 ou mais novo. Se faltar, para e mostra o comando para instalar. Se estiver instalado, copia o programa para `~/.local/share/aditivahandy`, cria o ambiente virtual e registra o serviço do usuário. Também aplica `loginctl enable-linger`, para a ponte abrir quando a máquina liga, mesmo sem ninguém entrar na sessão.

Quando o comando terminar, ele mostra dois endereços. Abra `http://127.0.0.1:8787` nesse computador, ou `http://NOME-DA-MAQUINA.local:8787` de outro computador da rede. Entre no AditivaFlow e autorize.

O arquivo que termina com `-linux.tar.gz`, na mesma página de releases, traz o `install.sh`, o `Dockerfile` e o `docker-compose.yml`. Dentro da pasta extraída, `bash install.sh` faz a mesma instalação.

Para atualizar à mão, rode o mesmo comando da versão nova. O vínculo com a conta é mantido e o serviço reinicia sozinho.

## Raspberry Pi

Funciona no Raspberry Pi 3, 4 e 5 com o Raspberry Pi OS de 64 bits. O Raspberry fica ligado perto do roteador e não precisa de tela.

1. No Raspberry Pi Imager, escolha o **Raspberry Pi OS (64-bit)**. Em **Editar configurações**, defina o nome da máquina (por exemplo `aditivahandy`), o usuário e a senha, a rede Wi-Fi se não for usar cabo, e ligue o **SSH** na aba **Serviços**.
2. Grave o cartão, coloque no Raspberry e ligue. Espere uns 2 minutos.
3. No seu computador, abra o terminal (no Windows, o PowerShell) e entre no Raspberry:

   ```bash
   ssh SEU_USUARIO@aditivahandy.local
   ```

   Troque `aditivahandy` pelo nome que você escolheu no passo 1. Na primeira conexão, responda `yes` e digite a senha.
4. Já dentro do Raspberry, rode:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/gabrielbolzani/aditivahandy/v1.3.0/install.sh | bash
   ```

   A primeira instalação leva alguns minutos, porque baixa as bibliotecas.
5. No navegador do seu computador, abra `http://aditivahandy.local:8787` (com o nome do passo 1). Clique no link do AditivaFlow, entre na sua conta e autorize.

Pronto. Sempre que o Raspberry ligar, a ponte abre sozinha. Para conferir: `systemctl --user status aditivahandy`.

Se o endereço `.local` não abrir, use o IP do Raspberry, que aparece no roteador ou com `hostname -I` dentro dele.

Se você já rodava uma versão antiga à mão (com `python run.py`), pare esse processo antes de instalar, senão a porta 8787 fica ocupada: `pkill -f "python -u run.py"`.

Na página de releases, o arquivo que termina com `-raspberry-pi.tar.gz` é o mesmo pacote do Linux, para quem prefere baixar e rodar `bash install.sh` dentro da pasta extraída.

Para ver se o serviço sem Docker está no ar: `systemctl --user status aditivahandy`. Para ver o container: `docker compose -f ~/.local/share/aditivahandy/docker-compose.yml ps`.

O vínculo fica em `~/.config/aditivahandy/device.json`.

## Atualizar pela plataforma

A partir da 1.3.0, o AditivaHandy se atualiza sozinho. No AditivaFlow, abra **Configurações**, aba **Integrações**. Quando sair uma versão nova, o computador mostra **atualização** ao lado da versão. Clique no botão de atualizar e confirme.

O programa baixa a versão pedida deste repositório, troca os próprios arquivos, instala bibliotecas novas se precisar e reinicia. O vínculo com a conta continua. Em alguns segundos a versão nova aparece na plataforma.

- **Linux e Raspberry Pi (sem Docker):** funciona direto.
- **Windows:** funciona direto. A janela do `AditivaHandy.exe` mostra a troca e liga a versão nova.
- **Docker:** o container não troca os próprios arquivos. Rode de novo o comando de instalação da versão nova.

Quem está numa versão anterior à 1.3.0 precisa instalar a 1.3.0 uma vez pelo jeito normal. As próximas podem ser pedidas pela plataforma.

## Depois de instalar

A porta padrão é `8787`. Ela muda com `--port` ou com a variável `HANDY_PORT`.

A página local mostra um código e um link. Você entra na conta do AditivaFlow e aprova este computador uma vez. A partir daí a plataforma envia as máquinas com integração AditivaHandy: IP, protocolo e código de acesso não ficam gravados neste programa.

Ele fala com Bambu Lab, Moonraker/Klipper e Elegoo, manda o estado a cada 3 segundos e soma o tempo em impressão em cima do horímetro da plataforma. OctoPrint, PrusaLink e o protocolo "outro" ainda não têm driver.

Os drivers vêm em `vendor/3d_printer_connection_hub`. A variável `ADITIVA_HUB_DIR` aponta para outra cópia, se você tiver uma.
