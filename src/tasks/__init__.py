"""
tasks

Pacote de TaskAnalyzers. Importar este pacote registra todas as
tarefas embutidas (ver registry.py) — quem monta os pipelines só
precisa de `import tasks` para que os tipos fiquem disponíveis para uso
em tasks.yaml.
"""

from . import missing_product, ppe_compliance, treadmill_counter  # noqa: F401

try:
    from . import face_id  # noqa: F401
except ImportError:
    pass  # insightface/onnxruntime não instalados — face_id fica indisponível,
    # o resto da aplicação continua funcionando normalmente.
