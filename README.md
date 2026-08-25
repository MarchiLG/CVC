# Monitor de Câmeras IP

Esqueleto de aplicação em Python para visualizar múltiplas câmeras IP
(conectadas via hub) através de uma interface gráfica simples, com
captura contínua de frames via OpenCV.

## Instalação (Arch Linux)

Via pacman:

    sudo pacman -S python python-opencv python-pillow python-yaml tk

Alternativa via pip (dentro de um virtualenv):

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

## Configuração

Edite `config/cameras.yaml` com o id, nome e url (RTSP ou HTTP/MJPEG)
de cada câmera cadastrada.

## Execução

    python src/main.py

## Estrutura

    ip_camera_monitor/
    ├── config/
    │   └── cameras.yaml        # cadastro das câmeras
    ├── src/
    │   ├── camera/
    │   │   ├── camera_stream.py    # captura de UMA câmera (thread + frame mais recente)
    │   │   └── camera_manager.py   # carrega config e orquestra todas as câmeras
    │   ├── gui/
    │   │   └── main_window.py      # interface gráfica (Tkinter), menu + exibição
    │   └── main.py                  # ponto de entrada
    └── requirements.txt

## Como funciona

- Cada câmera roda em sua própria thread (`CameraStream`), lendo frames
  continuamente via `cv2.VideoCapture` e guardando o mais recente em
  `most_recent_frame` — sem travar a GUI enquanto a rede/câmera responde.
- O `CameraManager` carrega `cameras.yaml` e mantém um `CameraStream` por
  câmera cadastrada, expondo `get_frame(camera_id)` para quem quiser ler.
- A `MainWindow` (Tkinter) mostra um menu lateral com as câmeras; ao
  selecionar uma, a área central passa a exibir o frame mais recente
  daquela câmera, atualizado a cada ~33ms.

## Próximos passos

O ponto de extensão para processamento sobre o frame (detecção, gravação,
inferência do seu modelo, etc.) está marcado com `# TODO` dentro de
`CameraStream._capture_loop`, logo após a atualização de
`most_recent_frame` — e também pode ser feito fora da thread de captura,
lendo `get_frame()` a partir de onde for mais conveniente.
