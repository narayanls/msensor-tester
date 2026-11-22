"""Tradução pt_BR. Chave = texto em inglês usado no código."""

PT_BR = {
    # --- Diálogos -----------------------------------------------------------
    "Reading the raw sensor data requires access to /dev/input. The package installs a udev rule that grants this access only to mice, and only to the user logged in at the computer (keyboards are not included).":
        "Ler os dados brutos do sensor exige acesso a /dev/input. O pacote instala uma regra udev que libera esse acesso só para mouses, e só para o usuário logado no computador (teclados não são incluídos).",
    "Then press the refresh button next to the mouse list.":
        "Depois, clique no botão de atualizar ao lado da lista de mouses.",
    "Permission needed": "Permissão necessária",
    "OK": "OK",
    "Preferences": "Preferências",
    "CPI measurement distance (cm)": "Distância para medir o CPI (cm)",
    "How far you move the mouse in “Measure CPI”": "Quanto você move o mouse em “Medir CPI”",
    "Takes effect after restarting the app": "Vale após reiniciar o aplicativo",
    "Inspired by": "Inspirado em",
    "The rule is installed but has not been applied to the connected mice yet. Unplug and reconnect the mouse, or run:":
        "A regra está instalada, mas ainda não foi aplicada aos mouses conectados. Desconecte e reconecte o mouse, ou execute:",
    "The rule was not found. Install it with:": "A regra não foi encontrada. Instale-a com:",
    "Tests": "Testes",
    "Lock the cursor during tests": "Travar o cursor durante os testes",
    "Language": "Idioma",
    "Automatic (system)": "Automático (sistema)",
    "Interface language": "Idioma da interface",
    "Mouse sensor tracking and polling rate tester for Linux. Reads the raw sensor data directly from evdev, with microsecond kernel timestamps.":
        "Teste de rastreio do sensor e de polling rate de mouses para Linux. Lê os dados brutos do sensor direto do evdev, com tempos do kernel em microssegundos.",

    # --- Gráficos -----------------------------------------------------------
    "Move the mouse to start": "Mova o mouse para começar",
    "No data yet": "Sem dados ainda",
    "Time (ms)": "Tempo (ms)",
    "xCount vs. Time": "Contagem X × Tempo",
    "yCount vs. Time": "Contagem Y × Tempo",
    "xyCount vs. Time": "Contagem XY × Tempo",
    "X vs. Y": "X × Y (trajetória)",
    "Reports": "Relatórios",
    "From event": "Do evento",
    "to": "até",
    "Lines": "Linhas",
    "Stems": "Hastes",
    "Smoothed (8 ms)": "Suavizado (8 ms)",
    "xCounts": "Contagens X",
    "yCounts": "Contagens Y",
    "Counts": "Contagens",
    "Plots need matplotlib: {error}": "Os gráficos precisam do matplotlib: {error}",
    "Plots": "Gráficos",

    # --- Polling rate -------------------------------------------------------
    "Move the mouse to start…": "Mova o mouse para começar…",
    "Average": "Média",
    "Peak": "Pico",
    "Time left": "Tempo restante",
    "Click “Start test” and move the mouse quickly in all directions (circles work well). The timer starts with the first movement.":
        "Clique em “Iniciar teste” e mova o mouse rápido em todas as direções (círculos funcionam bem). A contagem começa no primeiro movimento.",
    "CURRENT": "ATUAL",
    "AVERAGE": "MÉDIA",
    "Test cancelled.": "Teste cancelado.",
    "Test finished.": "Teste concluído.",
    "Duration": "Duração",
    "Polling rate over time": "Polling rate ao longo do tempo",
    "Interval between reports": "Intervalo entre relatórios",
    "Detailed result": "Resultado detalhado",
    "Pauses in movement are excluded from the calculations.": "As pausas no movimento são descartadas dos cálculos.",
    "Detected rate": "Taxa detectada",
    "Nearest standard rate": "Taxa padrão mais próxima",
    "Average rate": "Taxa média",
    "Reports per second while moving": "Relatórios por segundo durante o movimento",
    "Peak / lowest": "Pico / mínima",
    "Best and worst 100 ms windows": "Melhor e pior janela de 100 ms",
    "Mean / median interval": "Intervalo médio / mediano",
    "Shortest / longest interval": "Menor / maior intervalo",
    "Jitter (standard deviation)": "Jitter (desvio padrão)",
    "Lower is more stable": "Quanto menor, mais estável",
    "Percentiles 1% / 99%": "Percentis 1% / 99%",
    "Intervals within ±25%": "Intervalos dentro de ±25%",
    "Share of intervals close to the nominal value": "Parcela dos intervalos próximos ao valor nominal",
    "Reports / active time": "Relatórios / tempo ativo",
    "Pauses": "Pausas",
    "Times the movement stopped during the test": "Vezes que o movimento parou durante o teste",
    "Kernel buffer overflows": "Estouros do buffer do kernel",
    "Should be zero": "Deve ser zero",
    "The cursor is locked; press Esc to cancel.": "O cursor está travado; pressione Esc para cancelar.",
    "The mouse was disconnected.": "O mouse foi desconectado.",
    "Not enough data. Move the mouse continuously during the test.":
        "Dados insuficientes. Mova o mouse sem parar durante o teste.",
    "Detected: {rate} Hz": "Detectado: {rate} Hz",
    "Cancel (Esc)": "Cancelar (Esc)",
    "Start test (F1)": "Iniciar teste (F1)",
    "Keep moving the mouse!": "Continue movendo o mouse!",
    "No movement detected. Test cancelled.": "Nenhum movimento detectado. Teste cancelado.",
    "Esc cancels.": "Esc cancela.",

    # --- Sensor -------------------------------------------------------------
    "counts": "contagens",
    "Measure CPI": "Medir CPI",
    "Collect": "Coletar",
    "Plots (F3)": "Gráficos (F3)",
    "Save CSV": "Salvar CSV",
    "Open CSV": "Abrir CSV",
    "CPI (DPI)": "CPI (DPI)",
    "Type the mouse value or use “Measure CPI”": "Digite o valor do mouse ou use “Medir CPI”",
    "Events": "Eventos",
    "Sum X": "Soma X",
    "Sum Y": "Soma Y",
    "Path": "Caminho",
    "Average report rate": "Taxa média de relatórios",
    "Ready": "Pronto",
    "Cancelled": "Cancelado",
    "The test was cancelled.": "O teste foi cancelado.",
    "Done": "Concluído",
    "Press “Plots” (F3) to view the data or “Save CSV” to keep the log.":
        "Clique em “Gráficos” (F3) para ver os dados ou em “Salvar CSV” para guardar o log.",
    "CSV files": "Arquivos CSV",
    "All files": "Todos os arquivos",
    "File loaded": "Arquivo carregado",
    "Settings": "Configuração",
    "Description": "Descrição",
    "Result": "Resultado",
    "Mouse disconnected": "Mouse desconectado",
    "The device stopped responding.": "O dispositivo parou de responder.",
    "Recording time limit reached.": "Tempo máximo de gravação atingido.",
    "No movement was recorded. Try again.": "Nenhum movimento foi gravado. Tente de novo.",
    "No data": "Sem dados",
    "No movement was recorded.": "Nenhum movimento foi gravado.",
    "No data to plot yet.": "Ainda não há dados para os gráficos.",
    "Save log": "Salvar log",
    "Open log": "Abrir log",
    "Events: {n}": "Eventos: {n}",
    "Saved {name}": "{name} salvo",
    "Warning: the kernel discarded data {n} time(s) (buffer overflow).":
        "Atenção: o kernel descartou dados {n} vez(es) (estouro de buffer).",
    "Measured CPI: {cpi}": "CPI medido: {cpi}",
    "{avg} (nominal {nominal} Hz)": "{avg} (nominal {nominal} Hz)",
    "Could not save: {error}": "Não foi possível salvar: {error}",
    "Could not open the file: {error}": "Não foi possível abrir o arquivo: {error}",
    "{counts} counts over {dist} cm.": "{counts} contagens em {dist} cm.",

    # --- Janela principal ---------------------------------------------------
    "Mouse to test": "Mouse a testar",
    "Detect: move the mouse you want to test": "Detectar: mova o mouse que deseja testar",
    "Refresh the list of mice": "Atualizar a lista de mouses",
    "About MSensor Tester": "Sobre o MSensor Tester",
    "Main menu": "Menu principal",
    "Sensor": "Sensor",
    "Polling rate": "Polling rate",
    "Move the mouse you want to test…": "Mova o mouse que deseja testar…",
    "No permission to read the mice": "Sem permissão para ler os mouses",
    "How to fix": "Como resolver",
    "No mouse found": "Nenhum mouse encontrado",
    "No mouse selected.": "Nenhum mouse selecionado.",
    "Test stopped because the window lost focus.": "Teste interrompido porque a janela perdeu o foco.",
    "no permission": "sem permissão",
    "No movement detected.": "Nenhum movimento detectado.",
    "Selected: {name}": "Selecionado: {name}",
    "Could not open the mouse: {error}": "Não foi possível abrir o mouse: {error}",
    # --- Sem trava do cursor / área de teste --------------------------------
    "Optional. Fails if another program has exclusive access to the mouse (input-remapper, keyd, kanata…). The measurement is the same with or without it.":
        "Opcional. Falha se outro programa tiver acesso exclusivo ao mouse (input-remapper, keyd, kanata…). A medição é a mesma com ou sem a trava.",
    "The cursor moves normally; this does not affect the measurement.":
        "O cursor se move normalmente; isso não afeta a medição.",
    "With the cursor over this area:\n1. Press and hold the left mouse button\n2. Move the mouse\n3. Release the left button":
        "Com o cursor sobre esta área:\n1. Pressione e segure o botão esquerdo do mouse\n2. Mova o mouse\n3. Solte o botão esquerdo",
    "With the cursor over this area:\n1. Press and hold the left mouse button\n2. Move the mouse {dist} cm in a straight line (use a ruler)\n3. Release the left button":
        "Com o cursor sobre esta área:\n1. Pressione e segure o botão esquerdo do mouse\n2. Mova o mouse {dist} cm em linha reta (use uma régua)\n3. Solte o botão esquerdo",
    "The cursor is locked during the test.": "O cursor fica travado durante o teste.",
    "Measuring…": "Medindo…",
    "Collecting…": "Coletando…",
    "≈ {cm} cm at the current CPI": "≈ {cm} cm com o CPI atual",
    "another program already has exclusive access to it (input-remapper, keyd, kanata…)":
        "outro programa já tem acesso exclusivo a ele (input-remapper, keyd, kanata…)",
    "Could not lock the cursor: {reason}. The test continues without the lock.":
        "Não foi possível travar o cursor: {reason}. O teste continua sem a trava.",

    # --- Diagnóstico -------------------------------------------------------
    'Collecting information… during the listening test, move the mouse and click.':
        'Coletando informações… durante o teste de escuta, mova o mouse e clique.',
    'System':
        'Sistema',
    'other':
        'outro',
    'readable':
        'legível',
    'NOT readable':
        'NÃO legível',
    'Exclusive access (EVIOCGRAB) by other programs':
        'Acesso exclusivo (EVIOCGRAB) por outros programas',
    'Known input-grabbing programs running':
        'Programas conhecidos por capturar a entrada em execução',
    'Processes with input devices open (visible to this user)':
        'Processos com dispositivos de entrada abertos (visíveis para este usuário)',
    'Conclusions':
        'Conclusões',
    'No mouse (REL_X + REL_Y + BTN_LEFT) was found in /sys/class/input.':
        'Nenhum mouse (REL_X + REL_Y + BTN_LEFT) foi encontrado em /sys/class/input.',
    'Close it during the test, or select the virtual device it creates (the polling rate will then be that of the virtual device).':
        'Feche-o durante o teste ou selecione o dispositivo virtual que ele cria (o polling rate medido será o do dispositivo virtual).',
    'No movement was received from any mouse during the listening test. If you moved the mouse, it is probably grabbed by another program.':
        'Nenhum movimento chegou de nenhum mouse durante o teste de escuta. Se você moveu o mouse, ele provavelmente está capturado por outro programa.',
    'No problem detected.':
        'Nenhum problema detectado.',
    'diagnostic report':
        'relatório de diagnóstico',
    'Distribution':
        'Distribuição',
    'Session':
        'Sessão',
    'User':
        'Usuário',
    'groups':
        'grupos',
    'udev rule installed':
        'regra udev instalada',
    'Input devices':
        'Dispositivos de entrada',
    'MOUSE':
        'MOUSE',
    'keyboard':
        'teclado',
    'absolute (touchpad/tablet)':
        'absoluto (touchpad/mesa digitalizadora)',
    'no mouse found':
        'nenhum mouse encontrado',
    'none found':
        'nenhum encontrado',
    'none visible':
        'nenhum visível',
    'nothing to listen to (no readable mouse)':
        'nada para escutar (nenhum mouse legível)',
    'Some mice are not readable and the udev rule is not installed.':
        'Alguns mouses não são legíveis e a regra udev não está instalada.',
    "Some mice are not readable even with the udev rule installed: reconnect the mouse or run 'sudo udevadm trigger --subsystem-match=input --action=change'. The rule only works for the user logged in locally.":
        "Alguns mouses não são legíveis mesmo com a regra udev instalada: reconecte o mouse ou execute 'sudo udevadm trigger --subsystem-match=input --action=change'. A regra só vale para o usuário logado localmente.",
    'These mice are grabbed by another program: {names}. While that happens, the kernel delivers the events only to that program.':
        'Estes mouses estão capturados por outro programa: {names}. Enquanto isso acontece, o kernel entrega os eventos só para esse programa.',
    'yes':
        'sim',
    'NO':
        'NÃO',
    'no':
        'não',
    'type':
        'tipo',
    'capabilities':
        'recursos',
    'permission':
        'permissão',
    'free':
        'livre',
    'BUSY — another program has exclusive access; events do not reach this app':
        'OCUPADO — outro programa tem acesso exclusivo; os eventos não chegam a este app',
    'not supported':
        'não suportado',
    'error':
        'erro',
    'Listening test ({s} s) — move the mouse and click':
        'Teste de escuta ({s} s) — mova o mouse e clique',
    'selected':
        'selecionado',
    'Move the mouse now':
        'Mova o mouse agora',
    'not tested (no permission)':
        'não testado (sem permissão)',
    '({n} processes of other users/root are not visible; run with sudo to see them)':
        '({n} processos de outros usuários/root não são visíveis; rode com sudo para vê-los)',
    'nominal':
        'nominal',
    'Likely culprit: {who}.':
        'Provável responsável: {who}.',
    'The selected device received nothing, but {other} did: select it in the list (or use the Detect button).':
        'O dispositivo selecionado não recebeu nada, mas {other} recebeu: selecione-o na lista (ou use o botão Detectar).',
    'database not available':
        'banco de dados indisponível',
    'could not open':
        'não foi possível abrir',
    'raw events':
        'eventos brutos',
    'motion reports':
        'relatórios de movimento',
    'clicks':
        'cliques',
    'rate':
        'taxa',
    'Collecting information…':
        'Coletando informações…',
    'Analyzing…':
        'Analisando…',
    'Done. Copy the report and send it along with your question.':
        'Pronto. Copie o relatório e envie junto com a sua dúvida.',
    'Report copied':
        'Relatório copiado',
    'Diagnostics':
        'Diagnóstico',
    'Diagnostics…':
        'Diagnóstico…',
    'Run again':
        'Executar de novo',
    'Copy':
        'Copiar',
    'Move the mouse and click now… {s} s':
        'Mova o mouse e clique agora… {s} s',
    'Done. Debug log: {path}':
        'Pronto. Log de debug: {path}',
    'The diagnostic failed':
        'O diagnóstico falhou',
    'Mouse in exclusive use':
        'Mouse em uso exclusivo',
    'The kernel is delivering the events of “{name}” only to another program (exclusive access), so MSensor Tester receives nothing.':
        'O kernel está entregando os eventos de “{name}” só para outro programa (acesso exclusivo), então o MSensor Tester não recebe nada.',
    'Running program that usually does this: {who}.':
        'Programa em execução que costuma fazer isso: {who}.',
    'No event has arrived from this device yet. Use Menu → Diagnostics.':
        'Nenhum evento chegou deste dispositivo ainda. Use Menu → Diagnóstico.',
    'Nothing received from “{name}”. Is this the mouse you are moving?':
        'Nada recebido de “{name}”. É este o mouse que você está movendo?',
    '{n} keys/buttons':
        '{n} teclas/botões',
    'Processes that create virtual input devices (uinput)':
        'Processos que criam dispositivos de entrada virtuais (uinput)',
    'likely responsible':
        'provável responsável',
    'virtual device that receives the events':
        'dispositivo virtual que recebe os eventos',
    'To stop it: kill {pids}':
        'Para encerrá-lo: kill {pids}',
    'To measure the real mouse, close that program and press the refresh button.':
        'Para medir o mouse de verdade, feche esse programa e clique no botão de atualizar.',
    'Use virtual device':
        'Usar dispositivo virtual',
    'Process holding the mouse:':
        'Processo que está segurando o mouse:',
    'To measure the real mouse, close that program (for example: kill {pids}) and press the refresh button.':
        'Para medir o mouse de verdade, feche esse programa (por exemplo: kill {pids}) e clique no botão de atualizar.',
    "You can also test the virtual device “{name}”, which receives the events. The CPI and tracking stay valid, but the polling rate will be the rate at which that program forwards the events, not the mouse's.":
        'Você também pode testar o dispositivo virtual “{name}”, que recebe os eventos. O CPI e o rastreio continuam válidos, mas o polling rate será a taxa com que esse programa repassa os eventos, não a do mouse.',
    'Virtual device selected. Start the test again.':
        'Dispositivo virtual selecionado. Inicie o teste de novo.',
    "Note: this is a virtual device; the rate shown is the rate at which the program that creates it forwards the events, not the mouse's.":
        'Atenção: este é um dispositivo virtual; a taxa mostrada é a taxa com que o programa que o cria repassa os eventos, não a do mouse.',
    'in exclusive use':
        'em uso exclusivo',
    'virtual':
        'virtual',
    # --- Simplificação (sem Log) --------------------------------------------
    'Collect (F1)':
        'Coletar (F1)',
    'Type the correct CPI, or use “Measure CPI”.\nThen use “Collect” (records while the left button is held), or open a CSV file.':
        'Digite o CPI correto ou use “Medir CPI”.\nDepois use “Coletar” (grava enquanto o botão esquerdo estiver pressionado) ou abra um arquivo CSV.',
    'Now use “Collect”.':
        'Agora use “Coletar”.',
}
