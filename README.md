# MSensor Tester

**Português** · [English](README.en.md)

Teste de **rastreio do sensor** e de **polling rate** de mouses para Linux, feito em Python com GTK 4 e libadwaita.

A aba **Sensor** segue o [MouseTester](https://github.com/microe1/MouseTester) do Windows: mede o CPI real, grava os movimentos e mostra os gráficos de contagem e de trajetória. A aba **Polling rate** mede quantos relatórios por segundo o mouse realmente envia, ao vivo, com estatísticas que um teste no navegador não consegue dar.

Interface em português (pt-BR) e em inglês para sistemas em outros idiomas.

Exemplo de testes:


https://github.com/user-attachments/assets/7f8cc69c-a1e7-44c1-ac63-f7493af78ade







## Instalação

### Pacote pronto (Arch Linux e derivados)

Funciona no Arch Linux e em derivados como CachyOS, EndeavourOS e Manjaro.

1. Baixe o arquivo `msensor-tester-<versão>-1-any.pkg.tar.zst` na página de [Releases](https://github.com/narayanls/msensor-tester/releases/latest).
2. Instale com o pacman, na pasta onde o arquivo foi salvo:

   ```sh
   sudo pacman -U msensor-tester-1.0.2-1-any.pkg.tar.zst
   ```

O pacman instala as dependências (`python`, `python-gobject`, `gtk4`, `libadwaita`, `python-numpy` e `python-matplotlib`) e aplica a regra udev de acesso aos mouses. Depois, abra o **MSensor Tester** pelo menu de aplicativos ou rode `msensor-tester` no terminal.

Para atualizar, baixe o pacote da versão nova e repita o `pacman -U`. Para remover:

```sh
sudo pacman -R msensor-tester
```

### Compilar a partir do código-fonte

```sh
git clone https://github.com/narayanls/msensor-tester.git
cd msensor-tester/pkgbuild
makepkg -si
```

O `makepkg` gera o mesmo arquivo `.pkg.tar.zst` publicado nos Releases, dentro da pasta `pkgbuild`.

### Rodar sem instalar

```sh
make            # compila as traduções (precisa do pacote gettext)
python3 usr/share/msensor-tester/main.py
```

Sem o `make`, o app abre em inglês.

Nesse caso a regra udev não é instalada; veja [Permissão de acesso aos mouses](#permissão-de-acesso-aos-mouses).

## Como funciona

O app lê o mouse direto do **evdev** (`/dev/input/eventN`), o equivalente Linux do Raw Input usado pelo MouseTester:

- **Contagens brutas do sensor**, sem a aceleração do ponteiro.
- **Tempo de cada relatório marcado pelo kernel**, em microssegundos. Atrasos do Python ou da interface não afetam a medição.
- **Funciona igual no Wayland e no X11**, porque não depende do compositor nem do foco da janela para ler o mouse.

O **cursor continua se movendo normalmente durante os testes**, como no MouseTester original. Isso não afeta a medição: o app lê o sensor direto do kernel, mesmo com o cursor parado na borda da tela.

Em **Medir CPI** e **Coletar**, uma área de teste cobre a aba enquanto o teste roda. Comece o clique com o cursor sobre ela: o sistema (Wayland ou X11) entrega o arraste inteiro ao app até você soltar o botão, mesmo que o cursor saia da janela, então nada é arrastado ou selecionado na área de trabalho. **Esc cancela a qualquer momento.**

Existe uma trava opcional do cursor em **Menu → Preferências** (desligada por padrão). Ela pede acesso exclusivo ao mouse e falha se outro programa já tiver esse acesso, como input-remapper, keyd ou kanata. Nesse caso o app avisa o motivo e o teste continua sem a trava.

### Aba Sensor

- **Medir CPI**: segure o botão esquerdo, mova o mouse 10 cm em linha reta (use uma régua) e solte. A distância pode ser alterada nas Preferências.
- **Coletar (F1)**: grava enquanto o botão esquerdo estiver pressionado.
- **Gráficos (F3)**: contagem X, Y e XY × tempo e trajetória X × Y. Dá para escolher a faixa de eventos, ligar linhas, hastes e a média suavizada de 8 ms, dar zoom e exportar PNG.
- **Salvar / Abrir CSV**: no **mesmo formato do MouseTester**. Logs gravados no Windows abrem aqui e vice-versa, para comparar o mesmo mouse nos dois sistemas.

### Aba Polling rate

Clique em **Iniciar teste (F1)** e mova o mouse rápido em todas as direções. A contagem começa no primeiro movimento e dura o tempo escolhido (5 a 60 s). Durante o teste aparecem a taxa atual, o gráfico da taxa ao longo do tempo e o histograma dos intervalos. No fim, o app mostra:

- **Taxa detectada**: 125, 250, 500, 1000, 2000, 4000 ou 8000 Hz.
- **Taxa média, pico e mínima**, em janelas de 100 ms.
- **Intervalos entre relatórios**: médio, mediano, menor, maior, percentis 1% e 99%.
- **Jitter** (desvio padrão) e a parcela de intervalos a ±25% do valor nominal.
- Pausas no movimento e estouros do buffer do kernel.

O mouse só envia relatórios quando se move, então **as pausas são descartadas dos cálculos**. A taxa é calculada contando relatórios por tempo, o que não se deixa enganar quando o controlador USB entrega dois relatórios quase juntos.

## Permissão de acesso aos mouses

Ler `/dev/input` exige permissão. Em vez de colocar o usuário no grupo `input`, o que daria acesso também ao teclado, o pacote instala a regra udev `/usr/lib/udev/rules.d/70-msensor-tester.rules`. Ela libera a leitura **só dos mouses**, e só para o usuário logado no computador, pela tag `uaccess` do systemd-logind.

O pacote aplica a regra na instalação, pelo `pacman -U` ou pelo `makepkg -si`. Se o app avisar que falta permissão, reconecte o mouse ou execute:

```sh
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=input --action=change
```

Para rodar direto do repositório, sem instalar o pacote, copie a regra antes:

```sh
sudo install -Dm644 usr/lib/udev/rules.d/70-msensor-tester.rules /etc/udev/rules.d/70-msensor-tester.rules
```

## Quando nada é capturado (diagnóstico)

Se o teste abre mas nenhum movimento aparece, rode o diagnóstico com o app fechado:

```sh
msensor-tester --diagnose
# sem instalar: python3 usr/share/msensor-tester/main.py --diagnose
```

Durante os 5 segundos de escuta, mova o mouse e clique. O relatório mostra:
- todos os dispositivos de entrada e as permissões de cada um;
- se a regra udev foi aplicada (tag `uaccess`);
- se outro programa tem acesso exclusivo ao mouse;
- quais programas conhecidos por capturar a entrada estão rodando;
- quantos eventos cada mouse enviou durante a escuta.

O mesmo relatório está em **Menu → Diagnóstico**, com um botão para copiar.

Para acompanhar cada passo do app, rode com log de depuração:

```sh
msensor-tester --debug
```

O log aparece no terminal e fica salvo em `~/.cache/msensor-tester/debug.log`. A cada segundo de teste ele mostra quantos eventos brutos chegaram; "0 eventos brutos" enquanto você move o mouse significa que o kernel não está entregando nada a este app.

**Causa mais comum:** um programa que captura o mouse com exclusividade (remapeadores de botões e macros como input-remapper, keyd, kanata, logiops, interception-tools, xremap ou um script próprio com python-evdev). Enquanto ele roda, o kernel entrega os eventos só para ele e os repassa por um dispositivo virtual. O app detecta isso antes de cada teste, mostra qual processo está segurando o mouse e oferece usar o dispositivo virtual. Na lista, esses mouses aparecem marcados como "em uso exclusivo" e "virtual". Para resolver, feche o programa durante o teste ou selecione o dispositivo virtual na lista (o polling medido será o do dispositivo virtual, não o do mouse).

## Dicas e limitações

- **Alguns controladores USB agrupam interrupções**: os intervalos podem alternar (por exemplo 0,9 e 1,1 ms) em vez de ficarem constantes. É comportamento real do hardware e também acontece no Windows; o histograma deixa isso visível.
- **Mouses antigos a 125 Hz**: o kernel aceita o parâmetro `usbhid.mousepoll` para forçar outra taxa em mouses que não pedem a sua. Mouses gamer modernos já pedem a taxa certa.
- **Teclas F1, F3 e Esc** só funcionam com a janela do app em foco.
- **No teste de polling rate**, prefira mover o mouse em círculos no meio da tela: encostar o cursor num canto pode abrir a visão geral do GNOME (canto ativo). A medição continua, mas a janela sai da frente.

## 🛠️ Construído com

- [Python 3](https://www.python.org) + [PyGObject](https://pygobject.gnome.org)
- [GTK4](https://gtk.org) + [Adwaita (libadwaita)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
- Vibe Coding:
  Claude Opus foi usada para geração de código. O programa foi revisado e testado por humano

## Créditos

Inspirado no [MouseTester](https://github.com/microe1/MouseTester) de microe1 (MIT). O MSensor Tester é uma reimplementação independente para Linux; nenhum código do original foi copiado.

## Licença

[GPL-3.0-or-later](LICENSE)
