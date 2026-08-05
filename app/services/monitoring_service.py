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

    def iniciar(
        self,
        usuario_id,
        ruta_id,
        nombre_ruta=None
    ):
        if self.state.activo:
            return {
                "ok": False,
                "mensaje": (
                    "El monitoreo ya está activo"
                )
            }

        self.state.iniciar(
            usuario_id,
            ruta_id,
            nombre_ruta
        )

        resultado_gorra = (
            self.gorra.iniciar_gorra(
                usuario_id,
                ruta_id
            )
        )

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
            "mensaje": (
                "Viaje iniciado correctamente"
            ),
            "estado": "activo",
            "gorra": resultado_gorra
        }

    def pausar(self):
        if not self.state.activo:
            return {
                "ok": False,
                "mensaje": (
                    "No hay monitoreo activo "
                    "para pausar"
                )
            }

        if self.state.pausado:
            return {
                "ok": False,
                "mensaje": (
                    "El monitoreo ya está pausado"
                )
            }

        usuario_id = self.state.usuario_id
        ruta_id = self.state.ruta_id

        resultado_gorra = (
            self.gorra.pausar_gorra(
                usuario_id,
                ruta_id
            )
        )

        self.state.pausar()

        return {
            "ok": True,
            "mensaje": (
                "Viaje pausado correctamente"
            ),
            "estado": "pausado",
            "gorra": resultado_gorra
        }

    def reanudar(self):
        if not self.state.activo:
            return {
                "ok": False,
                "mensaje": (
                    "No existe un monitoreo "
                    "para reanudar"
                )
            }

        if not self.state.pausado:
            return {
                "ok": False,
                "mensaje": (
                    "El monitoreo no está pausado"
                )
            }

        usuario_id = self.state.usuario_id
        ruta_id = self.state.ruta_id

        resultado_gorra = (
            self.gorra.reanudar_gorra(
                usuario_id,
                ruta_id
            )
        )

        self.state.reanudar()

        return {
            "ok": True,
            "mensaje": (
                "Viaje reanudado correctamente"
            ),
            "estado": "activo",
            "gorra": resultado_gorra
        }

    def detener(self):
        if not self.state.activo:
            return {
                "ok": False,
                "mensaje": (
                    "No hay monitoreo activo"
                )
            }

        usuario_id = self.state.usuario_id
        ruta_id = self.state.ruta_id

        resultado_gorra = (
            self.gorra.detener_gorra(
                usuario_id,
                ruta_id
            )
        )

        self.state.detener()

        return {
            "ok": True,
            "mensaje": (
                "Viaje detenido correctamente"
            ),
            "estado": "terminado",
            "gorra": resultado_gorra
        }

    def apagar_alarma(self):
        resultado_gorra = (
            self.gorra.apagar_alarma()
        )

        return {
            "ok": resultado_gorra.get(
                "ok",
                False
            ),
            "mensaje": (
                "Comando para apagar la alarma "
                "enviado a la gorra"
            ),
            "gorra": resultado_gorra
        }

    def estado(self):
        if not self.state.activo:
            estado_actual = "inactivo"
        elif self.state.pausado:
            estado_actual = "pausado"
        else:
            estado_actual = "activo"

        return {
            "activo": self.state.activo,
            "pausado": self.state.pausado,
            "estado": estado_actual,
            "usuarioId": self.state.usuario_id,
            "rutaId": self.state.ruta_id,
            "nombreRuta": self.state.nombre_ruta
        }