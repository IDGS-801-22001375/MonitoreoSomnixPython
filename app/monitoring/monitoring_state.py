class MonitoringState:

    def __init__(self):
        self.activo = False
        self.pausado = False
        self.usuario_id = None
        self.ruta_id = None
        self.nombre_ruta = None

    def iniciar(
        self,
        usuario_id,
        ruta_id,
        nombre_ruta=None
    ):
        self.activo = True
        self.pausado = False
        self.usuario_id = usuario_id
        self.ruta_id = ruta_id
        self.nombre_ruta = nombre_ruta

    def pausar(self):
        if self.activo:
            self.pausado = True

    def reanudar(self):
        if self.activo:
            self.pausado = False

    def detener(self):
        self.activo = False
        self.pausado = False

    def limpiar(self):
        self.activo = False
        self.pausado = False
        self.usuario_id = None
        self.ruta_id = None
        self.nombre_ruta = None