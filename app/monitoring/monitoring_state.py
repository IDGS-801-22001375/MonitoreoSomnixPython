class MonitoringState:
    def __init__(self):
        self.activo = False
        self.usuario_id = None
        self.ruta_id = None
        self.nombre_ruta = None

    def iniciar(self, usuario_id, ruta_id, nombre_ruta=None):
        self.activo = True
        self.usuario_id = usuario_id
        self.ruta_id = ruta_id
        self.nombre_ruta = nombre_ruta

    def detener(self):
        self.activo = False

    def limpiar(self):
        self.activo = False
        self.usuario_id = None
        self.ruta_id = None
        self.nombre_ruta = None