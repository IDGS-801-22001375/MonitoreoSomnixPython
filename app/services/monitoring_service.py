import threading

from app.firebase.firebase_service import FirebaseService
from app.monitoring.monitoring_state import MonitoringState
from app.monitoring.monitoring_loop import MonitoringLoop
from app.services.gorra_service import GorraService


class MonitoringService:
    def __init__(self):
        self.state = MonitoringState()
        self.firebase = FirebaseService()
        self.gorra = GorraService()
        self.thread = None

    def iniciar(self, usuario_id, ruta_id, nombre_ruta=None):
        if self.state.activo:
            return {
                "ok": False,
                "mensaje": "El monitoreo ya está activo"
            }

        self.state.iniciar(usuario_id, ruta_id, nombre_ruta)

        resultado_gorra = self.gorra.iniciar_gorra(usuario_id, ruta_id)

        loop = MonitoringLoop(
            firebase_service=self.firebase,
            state=self.state
        )

        self.thread = threading.Thread(
            target=loop.ejecutar,
            daemon=True
        )

        self.thread.start()

        return {
            "ok": True,
            "mensaje": "Viaje iniciado correctamente",
            "gorra": resultado_gorra
        }

    def detener(self):
        if not self.state.activo:
            return {
                "ok": False,
                "mensaje": "No hay monitoreo activo"
            }

        usuario_id = self.state.usuario_id
        ruta_id = self.state.ruta_id

        resultado_gorra = self.gorra.detener_gorra(usuario_id, ruta_id)

        self.state.detener()

        return {
            "ok": True,
            "mensaje": "Viaje detenido correctamente",
            "gorra": resultado_gorra
        }

    def estado(self):
        return {
            "activo": self.state.activo,
            "usuarioId": self.state.usuario_id,
            "rutaId": self.state.ruta_id,
            "nombreRuta": self.state.nombre_ruta
        }
    
    def pausar(self):
        if not self.state.activo:
            return {
                "ok": False,
                "mensaje": "No hay monitoreo activo para pausar"
            }

        self.state.detener()

        return {
            "ok": True,
            "mensaje": "Viaje pausado correctamente"
        }