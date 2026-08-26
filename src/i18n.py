"""
i18n.py

The single translation catalog for the whole application.

Both interfaces read from here, so a wording change lands in both at
once:

    the desktop GUI (PySide6)  imports t() directly and renders in the
                               language from app.yaml -> ui.language
    the web UI                 fetches the catalog from GET /api/i18n
                               and translates in the browser, which is
                               what makes the language picker switch the
                               page instantly, without a reload

Only two languages are supported on purpose: English (the default) and
Portuguese. To add a third, add its code to LANGUAGES, add a dict to
CATALOG with the same keys, and both interfaces pick it up — the web
language picker is built from LANGUAGES.

Keys are grouped by area with a "group.name" convention. Placeholders
use Python's str.format syntax ({name}), which the JavaScript side
implements too — so the SAME string works in both interfaces.
"""

# Supported languages, in the order the picker shows them. The first
# entry is the fallback whenever a language or a key is missing.
LANGUAGES = (
    ("en", "English"),
    ("pt", "Português"),
)

DEFAULT_LANGUAGE = "en"


CATALOG: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ #
    "en": {
        # ---- Application chrome
        "app.name": "Vision Central",
        "app.tagline": "video monitoring",
        "app.window_title": "Computer Vision Central",
        "app.exit": "Exit application",
        "app.exit_confirm": "Stop the backend and close this window? Every camera stream stops.",
        "app.exiting": "Shutting down…",

        # ---- Lock screen (POST /api/unlock, security/env_vault.py) —
        # shown before AppRuntime exists, so this MUST stay reachable
        # without a live backend (see GET /api/i18n in web/api.py).
        "lock.title": "Computer Vision Central",
        "lock.subtitle_unlock": "Enter the password to unlock your camera credentials.",
        "lock.subtitle_first_run": "Choose a password to encrypt your camera credentials (.env → .env.enc). You will need it every time the application starts — it is never stored anywhere.",
        "lock.password": "Password",
        "lock.confirm_password": "Confirm password",
        "lock.unlock": "Unlock",
        "lock.create": "Encrypt & start",
        "lock.exit": "Exit",
        "lock.starting": "Starting the backend…",

        # ---- Navigation / view headers
        "nav.live": "Live",
        "nav.calibration": "Calibration",
        "nav.settings": "Settings",
        "nav.employees": "Employees",
        "view.live.subtitle": "All registered cameras, in real time.",
        "view.calibration.subtitle": "Draw counting lines and zones over a frozen frame.",
        "view.settings.subtitle": "Vision tasks of each camera and what they notify.",
        "view.employees.subtitle": "Face enrollment for the face_id task.",

        # ---- Sidebar status
        "status.device": "Device",
        "status.cameras": "Cameras",
        "status.pipelines": "Pipelines",
        "status.narrator": "Narrator",
        "status.narrator_off": "off",
        "status.language": "Language",
        "status.connecting": "connecting…",
        "status.connected": "backend connected",
        "status.disconnected": "no connection to the backend",

        # ---- Live view
        "live.columns": "Columns",
        "live.columns.auto": "Automatic",
        "live.quality": "Quality",
        "live.quality.low": "Low (saves bandwidth)",
        "live.quality.medium": "Medium",
        "live.quality.high": "High",
        "live.overlay": "Detection boxes",
        "live.empty.title": "No cameras registered",
        "live.empty.body": "Add cameras to config/cameras.yaml and restart the application.",
        "live.streaming": "live",
        "live.waiting": "waiting for connection…",
        "live.connected": "connected",
        "live.no_tasks": "no tasks",
        "live.tracked": "{count} tracked",
        "live.expand": "Click to expand",
        "live.close_hint": "{name} — ESC or click to close",
        "live.video_alt": "Live video from camera {name}",
        "live.zoom_alt": "Expanded video from camera {name}",
        "live.host_link_title": "Open {host}'s own configuration page",

        # ---- Live view: "Add camera" panel
        "live.add_camera": "Add camera",
        "live.add_camera.title": "New camera",
        "live.add_camera.id": "Id (optional)",
        "live.add_camera.id_placeholder": "auto-generated from the name",
        "live.add_camera.name": "Name",
        "live.add_camera.protocol": "Connection",
        "live.add_camera.host": "Host / IPv4",
        "live.add_camera.port": "Port (optional)",
        "live.add_camera.path": "Path",
        "live.add_camera.path_placeholder": "/cam/realmonitor?channel=1&subtype=0",
        "live.add_camera.username": "Username",
        "live.add_camera.password": "Password",
        "live.add_camera.enabled": "Enabled",
        "live.add_camera.submit": "Add camera",
        "live.add_camera.cancel": "Cancel",
        "live.add_camera.added": "Camera \"{name}\" added.",

        # ---- Live view: per-camera settings (the cog button)
        "live.camera_settings": "Camera settings",
        "live.camera_settings.title": "{name} settings",
        "live.camera_settings.save": "Save",
        "live.camera_settings.delete": "Delete camera",
        "live.camera_settings.confirm_delete": "Delete camera \"{name}\"? This removes it from cameras.yaml and stops its stream.",
        "live.camera_settings.saved": "Camera \"{name}\" saved.",
        "live.camera_settings.deleted": "Camera \"{name}\" deleted.",

        # ---- Calibration view
        "calib.camera": "Camera",
        "calib.task": "Task",
        "calib.zone_name": "Zone name",
        "calib.zone_name_placeholder": "e.g. shelf_1",
        "calib.expected_class": "Expected class",
        "calib.expected_class_placeholder": "e.g. bottle",
        "calib.capture": "Capture frame",
        "calib.undo": "Undo point",
        "calib.clear": "Clear",
        "calib.save": "Save geometry",
        "calib.save_points": "Save geometry ({count} points)",
        "calib.hint.start": "Select a camera and a task, then capture a frame.",
        "calib.hint.no_tasks": "This camera has no tasks with geometry (line or zone). Add one under Settings.",
        "calib.hint.select_task": "Select a task.",
        "calib.hint.line": "Capture a frame and click 2 points to draw the counting line.",
        "calib.hint.zone": "Capture a frame and click at least 3 points to draw the zone polygon.",
        "calib.hint.captured": "Frame captured ({width}×{height}). Click to mark points.",
        "calib.saved": "Geometry saved to tasks.yaml.",

        # ---- Settings view
        "settings.camera": "Camera",
        "settings.new_task": "New task",
        "settings.add": "Add task",
        "settings.apply": "Apply now",
        "settings.apply_title": "Reloads the inference pipelines with the current tasks.yaml",
        "settings.empty.title": "No tasks on this camera",
        "settings.empty.body": "Cameras without tasks generate no inference pipeline — the video still shows under Live, but without detections.",
        "settings.detect_fps": "detect_fps",
        "settings.detect_fps_hint": "How many times per second this camera is analyzed.",
        "settings.model": "YOLO model",
        "settings.model_placeholder": "device default (app.yaml)",
        "settings.model_hint": "Edit the model: field in tasks.yaml to change it.",
        "settings.required_ppe": "Required PPE",
        "settings.required_ppe_placeholder": "e.g. helmet, vest",
        "settings.required_ppe_hint": "Comma-separated classes. Requires a model trained on PPE.",
        "settings.flags": "Flags ({count})",
        "settings.flag_active": "active",
        "settings.no_flags": "No flags configured — this task runs but notifies nothing. Add flags in tasks.yaml.",
        "settings.remove": "Remove",
        "settings.save": "Save",
        "settings.save_note": "Saving writes to tasks.yaml and reloads the inference pipelines.",
        "settings.geometry.line": "line",
        "settings.geometry.zone": "zone",
        "settings.not_calibrated.line": "This task has not been calibrated yet and is therefore NOT running. Draw the counting line under Calibration.",
        "settings.not_calibrated.zone": "This task has not been calibrated yet and is therefore NOT running. Draw the zone under Calibration.",
        "settings.confirm_remove": "Remove the task \"{type}\" (#{index}) from this camera?",
        "settings.saved": "Task \"{type}\" saved and applied.",
        "settings.added": "Task \"{type}\" added.",
        "settings.removed": "Task removed.",
        "settings.reloaded": "Pipelines reloaded ({count} active).",

        # ---- Employees view
        "emp.enroll_title": "Enroll employee",
        "emp.enroll_hint": "Capture the face with a camera or upload a photo. The face embedding is extracted on the server and stored in the database — the photo itself is not kept.",
        "emp.no_image": "No image selected",
        "emp.preview_alt": "Preview of the face to enroll",
        "emp.capture_from": "Capture from camera",
        "emp.capture": "Capture",
        "emp.or_upload": "Or upload a photo",
        "emp.name": "Name",
        "emp.name_placeholder": "Employee name",
        "emp.enroll": "Enroll",
        "emp.list_title": "Enrolled employees",
        "emp.empty": "Nobody enrolled yet. Without enrollments, the face_id task treats every face as unknown.",
        "emp.captured": "Frame captured. Enter the name and click Enroll.",
        "emp.enrolled": "Employee \"{name}\" enrolled.",
        "emp.name_required": "Enter the employee name.",
        "emp.image_required": "Capture from a camera or upload a photo first.",
        "emp.faces": "{count} face(s)",

        # ---- Alerts panel
        "alerts.title": "Alerts",
        "alerts.filter.all": "All",
        "alerts.filter.critical": "Critical",
        "alerts.filter.warning": "Warnings",
        "alerts.filter.info": "Info",
        "alerts.empty": "No alerts yet. They show up here as soon as a task fires.",
        "alerts.summary_label": "Summary (AI)",
        "alerts.summary_waiting": "Waiting for the first summary…",
        "alerts.toggle": "Show/hide the alerts panel",

        # ---- Severities
        "severity.info": "info",
        "severity.warning": "warning",
        "severity.critical": "critical",

        # ---- Relative time
        "time.seconds": "{value}s ago",
        "time.minutes": "{value}min ago",
        "time.hours": "{value}h ago",
        "time.days": "{value}d ago",

        # ---- Alert messages produced by the task analyzers
        "flag.count_below_threshold": "Count below expected: {count}/{expected} in the last {seconds}s (running total: {total})",
        "flag.missing_ppe": "Person #{track_id} missing: {items}",
        "flag.missing_product": "Zone '{zone}' without '{expected_class}' for more than {seconds}s",
        "flag.unknown_face": "Unrecognized face (similarity {score})",

        # ---- Calibration errors (raised in config/calibration.py)
        "calibration.line_needs_two_points": "Mark exactly 2 points for the counting line.",
        "calibration.zone_needs_three_points": "Mark at least 3 points for the zone.",
        "calibration.zone_name_required": "Enter a name for the zone.",
        "calibration.expected_class_required": "Enter the expected class for the zone.",
        "calibration.unsupported_type": "Visual calibration is not supported for this task type.",

        # ---- API errors (raised in web/api.py)
        "api.camera_not_found": "Camera not found.",
        "api.camera_already_exists": "A camera with this id already exists.",
        "api.vault_locked": "Credential store is locked — restart the application to unlock it.",
        "api.locked": "Unlock the application first.",
        "api.wrong_password": "Wrong password ({remaining} attempt(s) left).",
        "api.too_many_attempts": "Too many failed attempts — the application is shutting down.",
        "api.password_mismatch": "Passwords do not match.",
        "api.task_not_found": "That task does not exist on this camera.",
        "api.unknown_task_type": "Unknown task type.",
        "api.no_frame": "No frame available for this camera yet.",
        "api.jpeg_failed": "Failed to encode the frame as JPEG.",
        "api.image_unreadable": "Could not read the uploaded image.",
        "api.photo_or_camera_required": "Upload a photo or select a camera to capture from.",
        "api.employee_name_required": "Enter the employee name.",
        "api.face_not_detected": "Could not detect a face in the photo.",
        "api.face_unavailable": "Face recognition unavailable: install 'insightface' and 'onnxruntime'.",
        "api.generic": "Request failed ({status}).",

        # ---- Desktop GUI only
        "qt.alerts_dock": "Alerts",
        "qt.col.time": "Time",
        "qt.col.camera": "Camera",
        "qt.col.severity": "Severity",
        "qt.col.task": "Task",
        "qt.col.message": "Message",
        "qt.summary_placeholder": "No summary yet.",
        "qt.invalid_calibration": "Invalid calibration",
        "qt.no_frame_title": "No frame",
        "qt.saved_title": "Saved",
        "qt.tasks_saved": "Task changes saved.",
        "qt.flags_saved": "Flags saved.",
        "qt.remove_task_title": "Remove task",
        "qt.remove_task_question": "Remove this task?",
        "qt.error": "Error",
        "qt.image_open_failed": "Could not open the selected image.",
        "qt.select_photo": "Select photo",
        "qt.images_filter": "Images (*.png *.jpg *.jpeg)",
        "qt.load_photo": "Load photo...",
        "qt.finish_polygon": "Finish polygon",
        "qt.polygon_ready": "Polygon with {count} points ready to save.",
        "qt.task_selected": "Selected task: {type}",
        "qt.saved_to_yaml": "Saved to tasks.yaml.",
        "qt.no_face_title": "No face found",
        "qt.enrolled": "Employee '{name}' enrolled.",
        "qt.enroll_hint": "Capture or load a photo with a visible face.",
        "qt.photo_loaded": "Photo loaded. Enter the name and click Enroll.",
        "qt.no_photo_title": "No photo",
        "qt.no_photo": "Capture or load a photo first.",
        "qt.tasks_label": "Tasks",
        "qt.flags_label": "Flags of the selected task",
        "qt.save_tasks": "Save task changes",
        "qt.save_flags": "Save flags",
        "qt.new_task": "New task:",
        "qt.col.type": "Type",
        "qt.col.model": "Model",
        "qt.col.required_ppe": "Required PPE (ppe_compliance)",
        "qt.col.remove": "Remove",
        "qt.col.enabled": "enabled",
        "qt.col.notify": "notify (log,desktop)",
        "qt.col.id": "id",
    },

    # ------------------------------------------------------------------ #
    "pt": {
        # ---- Application chrome
        "app.name": "Vision Central",
        "app.tagline": "monitoramento por vídeo",
        "app.window_title": "Computer Vision Central",
        "app.exit": "Encerrar aplicação",
        "app.exit_confirm": "Parar o backend e fechar esta janela? Todos os streams de câmera param.",
        "app.exiting": "Encerrando…",

        # ---- Tela de bloqueio (POST /api/unlock, security/env_vault.py)
        # — aparece antes de existir um AppRuntime, então precisa
        # continuar acessível sem um backend vivo (ver GET /api/i18n em
        # web/api.py).
        "lock.title": "Computer Vision Central",
        "lock.subtitle_unlock": "Digite a senha para desbloquear suas credenciais de câmera.",
        "lock.subtitle_first_run": "Escolha uma senha para criptografar suas credenciais de câmera (.env → .env.enc). Você vai precisar dela toda vez que a aplicação iniciar — ela nunca é armazenada em lugar nenhum.",
        "lock.password": "Senha",
        "lock.confirm_password": "Confirmar senha",
        "lock.unlock": "Desbloquear",
        "lock.create": "Criptografar e iniciar",
        "lock.exit": "Sair",
        "lock.starting": "Iniciando o backend…",

        # ---- Navigation / view headers
        "nav.live": "Ao vivo",
        "nav.calibration": "Calibração",
        "nav.settings": "Configurações",
        "nav.employees": "Funcionários",
        "view.live.subtitle": "Todas as câmeras cadastradas, em tempo real.",
        "view.calibration.subtitle": "Desenhe linhas de contagem e zonas sobre um frame congelado.",
        "view.settings.subtitle": "Tarefas de visão de cada câmera e o que elas notificam.",
        "view.employees.subtitle": "Cadastro de rostos para a tarefa face_id.",

        # ---- Sidebar status
        "status.device": "Device",
        "status.cameras": "Câmeras",
        "status.pipelines": "Pipelines",
        "status.narrator": "Narrador",
        "status.narrator_off": "desligado",
        "status.language": "Idioma",
        "status.connecting": "conectando…",
        "status.connected": "backend conectado",
        "status.disconnected": "sem conexão com o backend",

        # ---- Live view
        "live.columns": "Colunas",
        "live.columns.auto": "Automático",
        "live.quality": "Qualidade",
        "live.quality.low": "Baixa (economiza banda)",
        "live.quality.medium": "Média",
        "live.quality.high": "Alta",
        "live.overlay": "Caixas de detecção",
        "live.empty.title": "Nenhuma câmera cadastrada",
        "live.empty.body": "Adicione câmeras em config/cameras.yaml e reinicie a aplicação.",
        "live.streaming": "ao vivo",
        "live.waiting": "aguardando conexão…",
        "live.connected": "conectada",
        "live.no_tasks": "sem tarefas",
        "live.tracked": "{count} rastreado(s)",
        "live.expand": "Clique para ampliar",
        "live.close_hint": "{name} — ESC ou clique para fechar",
        "live.video_alt": "Vídeo ao vivo da câmera {name}",
        "live.zoom_alt": "Vídeo ampliado da câmera {name}",
        "live.host_link_title": "Abrir a página de configuração da própria {host}",

        # ---- Tela Ao vivo: painel "Adicionar câmera"
        "live.add_camera": "Adicionar câmera",
        "live.add_camera.title": "Nova câmera",
        "live.add_camera.id": "Id (opcional)",
        "live.add_camera.id_placeholder": "gerado automaticamente a partir do nome",
        "live.add_camera.name": "Nome",
        "live.add_camera.protocol": "Conexão",
        "live.add_camera.host": "Host / IPv4",
        "live.add_camera.port": "Porta (opcional)",
        "live.add_camera.path": "Caminho",
        "live.add_camera.path_placeholder": "/cam/realmonitor?channel=1&subtype=0",
        "live.add_camera.username": "Usuário",
        "live.add_camera.password": "Senha",
        "live.add_camera.enabled": "Habilitada",
        "live.add_camera.submit": "Adicionar câmera",
        "live.add_camera.cancel": "Cancelar",
        "live.add_camera.added": "Câmera \"{name}\" adicionada.",

        # ---- Tela Ao vivo: configurações por câmera (botão de engrenagem)
        "live.camera_settings": "Configurações da câmera",
        "live.camera_settings.title": "Configurações de {name}",
        "live.camera_settings.save": "Salvar",
        "live.camera_settings.delete": "Excluir câmera",
        "live.camera_settings.confirm_delete": "Excluir a câmera \"{name}\"? Isso a remove de cameras.yaml e para o seu stream.",
        "live.camera_settings.saved": "Câmera \"{name}\" salva.",
        "live.camera_settings.deleted": "Câmera \"{name}\" excluída.",

        # ---- Calibration view
        "calib.camera": "Câmera",
        "calib.task": "Tarefa",
        "calib.zone_name": "Nome da zona",
        "calib.zone_name_placeholder": "ex.: prateleira_1",
        "calib.expected_class": "Classe esperada",
        "calib.expected_class_placeholder": "ex.: bottle",
        "calib.capture": "Capturar frame",
        "calib.undo": "Desfazer ponto",
        "calib.clear": "Limpar",
        "calib.save": "Salvar geometria",
        "calib.save_points": "Salvar geometria ({count} pontos)",
        "calib.hint.start": "Selecione uma câmera e uma tarefa, depois capture um frame.",
        "calib.hint.no_tasks": "Esta câmera não tem tarefas com geometria (linha ou zona). Adicione uma em Configurações.",
        "calib.hint.select_task": "Selecione uma tarefa.",
        "calib.hint.line": "Capture um frame e clique em 2 pontos para desenhar a linha de contagem.",
        "calib.hint.zone": "Capture um frame e clique em pelo menos 3 pontos para desenhar o polígono da zona.",
        "calib.hint.captured": "Frame capturado ({width}×{height}). Clique para marcar pontos.",
        "calib.saved": "Geometria salva em tasks.yaml.",

        # ---- Settings view
        "settings.camera": "Câmera",
        "settings.new_task": "Nova tarefa",
        "settings.add": "Adicionar tarefa",
        "settings.apply": "Aplicar agora",
        "settings.apply_title": "Recarrega os pipelines de inferência com o tasks.yaml atual",
        "settings.empty.title": "Nenhuma tarefa nesta câmera",
        "settings.empty.body": "Câmeras sem tarefa não geram pipeline de inferência — o vídeo continua aparecendo em Ao vivo, mas sem detecções.",
        "settings.detect_fps": "detect_fps",
        "settings.detect_fps_hint": "Quantas vezes por segundo esta câmera é analisada.",
        "settings.model": "Modelo YOLO",
        "settings.model_placeholder": "padrão do device (app.yaml)",
        "settings.model_hint": "Edite o campo model: em tasks.yaml para trocar.",
        "settings.required_ppe": "EPI exigido",
        "settings.required_ppe_placeholder": "ex.: helmet, vest",
        "settings.required_ppe_hint": "Classes separadas por vírgula. Exige um modelo treinado em EPI.",
        "settings.flags": "Flags ({count})",
        "settings.flag_active": "ativo",
        "settings.no_flags": "Nenhum flag configurado — esta tarefa roda mas não notifica nada. Adicione flags em tasks.yaml.",
        "settings.remove": "Remover",
        "settings.save": "Salvar",
        "settings.save_note": "Salvar grava em tasks.yaml e recarrega os pipelines de inferência.",
        "settings.geometry.line": "linha",
        "settings.geometry.zone": "zona",
        "settings.not_calibrated.line": "Esta tarefa ainda não foi calibrada e por isso NÃO está rodando. Desenhe a linha de contagem na aba Calibração.",
        "settings.not_calibrated.zone": "Esta tarefa ainda não foi calibrada e por isso NÃO está rodando. Desenhe a zona na aba Calibração.",
        "settings.confirm_remove": "Remover a tarefa \"{type}\" (#{index}) desta câmera?",
        "settings.saved": "Tarefa \"{type}\" salva e aplicada.",
        "settings.added": "Tarefa \"{type}\" adicionada.",
        "settings.removed": "Tarefa removida.",
        "settings.reloaded": "Pipelines recarregados ({count} ativo(s)).",

        # ---- Employees view
        "emp.enroll_title": "Cadastrar funcionário",
        "emp.enroll_hint": "Capture o rosto pela câmera ou envie uma foto. O embedding facial é extraído no servidor e salvo no banco — a foto em si não é armazenada.",
        "emp.no_image": "Nenhuma imagem selecionada",
        "emp.preview_alt": "Pré-visualização do rosto a cadastrar",
        "emp.capture_from": "Capturar da câmera",
        "emp.capture": "Capturar",
        "emp.or_upload": "Ou enviar uma foto",
        "emp.name": "Nome",
        "emp.name_placeholder": "Nome do funcionário",
        "emp.enroll": "Cadastrar",
        "emp.list_title": "Funcionários cadastrados",
        "emp.empty": "Ninguém cadastrado ainda. Sem cadastros, a tarefa face_id trata todo rosto como desconhecido.",
        "emp.captured": "Frame capturado. Informe o nome e clique em Cadastrar.",
        "emp.enrolled": "Funcionário \"{name}\" cadastrado.",
        "emp.name_required": "Informe o nome do funcionário.",
        "emp.image_required": "Capture pela câmera ou envie uma foto primeiro.",
        "emp.faces": "{count} rosto(s)",

        # ---- Alerts panel
        "alerts.title": "Alertas",
        "alerts.filter.all": "Todos",
        "alerts.filter.critical": "Críticos",
        "alerts.filter.warning": "Avisos",
        "alerts.filter.info": "Info",
        "alerts.empty": "Nenhum alerta ainda. Eles aparecem aqui assim que uma tarefa disparar.",
        "alerts.summary_label": "Resumo (IA)",
        "alerts.summary_waiting": "Aguardando o primeiro resumo…",
        "alerts.toggle": "Mostrar/ocultar o painel de alertas",

        # ---- Severities
        "severity.info": "info",
        "severity.warning": "aviso",
        "severity.critical": "crítico",

        # ---- Relative time
        "time.seconds": "há {value}s",
        "time.minutes": "há {value}min",
        "time.hours": "há {value}h",
        "time.days": "há {value}d",

        # ---- Alert messages produced by the task analyzers
        "flag.count_below_threshold": "Contagem abaixo do esperado: {count}/{expected} nos últimos {seconds}s (total acumulado: {total})",
        "flag.missing_ppe": "Pessoa #{track_id} sem: {items}",
        "flag.missing_product": "Zona '{zone}' sem '{expected_class}' há mais de {seconds}s",
        "flag.unknown_face": "Rosto não reconhecido (similaridade {score})",

        # ---- Calibration errors (raised in config/calibration.py)
        "calibration.line_needs_two_points": "Marque exatamente 2 pontos para a linha de contagem.",
        "calibration.zone_needs_three_points": "Marque pelo menos 3 pontos para a zona.",
        "calibration.zone_name_required": "Informe um nome para a zona.",
        "calibration.expected_class_required": "Informe a classe esperada da zona.",
        "calibration.unsupported_type": "Calibração visual não suportada para este tipo de tarefa.",

        # ---- API errors (raised in web/api.py)
        "api.camera_not_found": "Câmera não encontrada.",
        "api.camera_already_exists": "Já existe uma câmera com esse id.",
        "api.vault_locked": "O cofre de credenciais está bloqueado — reinicie a aplicação para desbloqueá-lo.",
        "api.locked": "Desbloqueie a aplicação primeiro.",
        "api.wrong_password": "Senha incorreta ({remaining} tentativa(s) restante(s)).",
        "api.too_many_attempts": "Muitas tentativas incorretas — a aplicação está sendo encerrada.",
        "api.password_mismatch": "As senhas não coincidem.",
        "api.task_not_found": "Esta tarefa não existe nesta câmera.",
        "api.unknown_task_type": "Tipo de tarefa desconhecido.",
        "api.no_frame": "Ainda não há frame disponível para esta câmera.",
        "api.jpeg_failed": "Falha ao codificar o frame em JPEG.",
        "api.image_unreadable": "Não foi possível ler a imagem enviada.",
        "api.photo_or_camera_required": "Envie uma foto ou selecione uma câmera para capturar.",
        "api.employee_name_required": "Informe o nome do funcionário.",
        "api.face_not_detected": "Não foi possível detectar um rosto na foto.",
        "api.face_unavailable": "Reconhecimento facial indisponível: instale 'insightface' e 'onnxruntime'.",
        "api.generic": "A requisição falhou ({status}).",

        # ---- Desktop GUI only
        "qt.alerts_dock": "Alertas",
        "qt.col.time": "Hora",
        "qt.col.camera": "Câmera",
        "qt.col.severity": "Severidade",
        "qt.col.task": "Tarefa",
        "qt.col.message": "Mensagem",
        "qt.summary_placeholder": "Nenhum resumo ainda.",
        "qt.invalid_calibration": "Calibração inválida",
        "qt.no_frame_title": "Sem frame",
        "qt.saved_title": "Salvo",
        "qt.tasks_saved": "Alterações de tarefas salvas.",
        "qt.flags_saved": "Flags salvos.",
        "qt.remove_task_title": "Remover tarefa",
        "qt.remove_task_question": "Remover esta tarefa?",
        "qt.error": "Erro",
        "qt.image_open_failed": "Não foi possível abrir a imagem selecionada.",
        "qt.select_photo": "Selecionar foto",
        "qt.images_filter": "Imagens (*.png *.jpg *.jpeg)",
        "qt.load_photo": "Carregar foto...",
        "qt.finish_polygon": "Finalizar polígono",
        "qt.polygon_ready": "Polígono com {count} pontos pronto para salvar.",
        "qt.task_selected": "Tarefa selecionada: {type}",
        "qt.saved_to_yaml": "Salvo em tasks.yaml.",
        "qt.no_face_title": "Nenhum rosto encontrado",
        "qt.enrolled": "Funcionário '{name}' cadastrado.",
        "qt.enroll_hint": "Capture ou carregue uma foto com um rosto visível.",
        "qt.photo_loaded": "Foto carregada. Informe o nome e clique em Cadastrar.",
        "qt.no_photo_title": "Sem foto",
        "qt.no_photo": "Capture ou carregue uma foto primeiro.",
        "qt.tasks_label": "Tarefas",
        "qt.flags_label": "Flags da tarefa selecionada",
        "qt.save_tasks": "Salvar alterações de tarefas",
        "qt.save_flags": "Salvar flags",
        "qt.new_task": "Nova tarefa:",
        "qt.col.type": "Tipo",
        "qt.col.model": "Modelo",
        "qt.col.required_ppe": "EPI exigido (ppe_compliance)",
        "qt.col.remove": "Remover",
        "qt.col.enabled": "habilitado",
        "qt.col.notify": "notify (log,desktop)",
        "qt.col.id": "id",
    },
}


def normalize(language: str | None) -> str:
    """Any unknown value falls back to the default language, so a typo
    in app.yaml degrades gracefully instead of breaking startup."""
    code = str(language or "").strip().lower()
    return code if code in CATALOG else DEFAULT_LANGUAGE


def t(key: str, language: str = DEFAULT_LANGUAGE, **params) -> str:
    """Translates `key`, interpolating {placeholders} from `params`.

    Missing keys fall back to English and, failing that, to the key
    itself — a missing translation shows up as visible text instead of
    crashing the interface.
    """
    code = normalize(language)
    text = CATALOG[code].get(key) or CATALOG[DEFAULT_LANGUAGE].get(key) or key

    if not params:
        return text
    try:
        return text.format(**params)
    except (KeyError, IndexError):
        # A placeholder without a matching value: better to show the raw
        # string than to blow up while rendering a screen.
        return text


def catalog_for(language: str) -> dict[str, str]:
    """Full dictionary of one language, used by GET /api/i18n."""
    return dict(CATALOG[normalize(language)])
