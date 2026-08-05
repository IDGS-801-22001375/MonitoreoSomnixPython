from typing import Any, Dict, Tuple

from app.monitoring.monitoring_state import MonitoringState
from app.services.gorra_command_dispatcher import (
    GorraCommandDispatcher
)
from app.services.gorra_service import GorraService


class MonitoringService:
    """
    Coordina el estado lógico del monitoreo.

    No abre cámaras.
    No procesa imágenes.
    No crea un hilo de MonitoringLoop.
    No espera las respuestas de .NET.

    La cámara de Android envía los frames mediante:
    POST /api/monitoreo/frame
    """

    def __init__(self):
        self.state = MonitoringState()

        self.gorra_service = GorraService()

        self.gorra_dispatcher = (
            GorraCommandDispatcher(
                gorra_service=self.gorra_service
            )
        )

    def iniciar(
        self,
        usuario_id: Any,
        ruta_id: Any,
        nombre_ruta: Any = None
    ) -> Dict[str, Any]:
        resultado_estado = self.state.iniciar(
            usuario_id=usuario_id,
            ruta_id=ruta_id,
            nombre_ruta=nombre_ruta
        )

        if not resultado_estado.get(
            "ok",
            False
        ):
            return resultado_estado

        reutilizado = resultado_estado.get(
            "reutilizado",
            False
        )

        if reutilizado:
            resultado_gorra = {
                "ok": True,
                "aceptado": False,
                "mensaje": (
                    "El viaje ya estaba activo; "
                    "no se duplicó el comando."
                )
            }
        else:
            resultado_gorra = (
                self.gorra_dispatcher.enviar(
                    "VIAJE_INICIAR"
                )
            )

        return {
            "ok": True,
            "mensaje": (
                "Viaje iniciado correctamente"
                if not reutilizado
                else "El viaje ya estaba iniciado"
            ),
            "estado": "activo",
            "reutilizado": reutilizado,
            "monitoreo": (
                resultado_estado.get("estado")
            ),
            "gorra": resultado_gorra
        }

    def pausar(self) -> Dict[str, Any]:
        resultado_estado = self.state.pausar()

        if not resultado_estado.get(
            "ok",
            False
        ):
            return resultado_estado

        reutilizado = resultado_estado.get(
            "reutilizado",
            False
        )

        if reutilizado:
            resultado_gorra = {
                "ok": True,
                "aceptado": False,
                "mensaje": (
                    "El viaje ya estaba pausado; "
                    "no se duplicó el comando."
                )
            }
        else:
            resultado_gorra = (
                self.gorra_dispatcher.enviar(
                    "VIAJE_PAUSAR"
                )
            )

        return {
            "ok": True,
            "mensaje": (
                "Viaje pausado correctamente"
                if not reutilizado
                else "El viaje ya estaba pausado"
            ),
            "estado": "pausado",
            "reutilizado": reutilizado,
            "monitoreo": (
                resultado_estado.get("estado")
            ),
            "gorra": resultado_gorra
        }

    def reanudar(self) -> Dict[str, Any]:
        resultado_estado = self.state.reanudar()

        if not resultado_estado.get(
            "ok",
            False
        ):
            return resultado_estado

        reutilizado = resultado_estado.get(
            "reutilizado",
            False
        )

        if reutilizado:
            resultado_gorra = {
                "ok": True,
                "aceptado": False,
                "mensaje": (
                    "El viaje ya estaba activo; "
                    "no se duplicó el comando."
                )
            }
        else:
            resultado_gorra = (
                self.gorra_dispatcher.enviar(
                    "VIAJE_REANUDAR"
                )
            )

        return {
            "ok": True,
            "mensaje": (
                "Viaje reanudado correctamente"
                if not reutilizado
                else "El viaje ya estaba activo"
            ),
            "estado": "activo",
            "reutilizado": reutilizado,
            "monitoreo": (
                resultado_estado.get("estado")
            ),
            "gorra": resultado_gorra
        }

    def detener(self) -> Dict[str, Any]:
        resultado_estado = self.state.detener()

        if not resultado_estado.get(
            "ok",
            False
        ):
            return resultado_estado

        reutilizado = resultado_estado.get(
            "reutilizado",
            False
        )

        if reutilizado:
            resultado_gorra = {
                "ok": True,
                "aceptado": False,
                "mensaje": (
                    "El viaje ya estaba detenido; "
                    "no se duplicó el comando."
                )
            }
        else:
            resultado_gorra = (
                self.gorra_dispatcher.enviar(
                    "VIAJE_TERMINAR"
                )
            )

        resultado = {
            "ok": True,
            "mensaje": (
                "Viaje terminado correctamente"
                if not reutilizado
                else "El viaje ya estaba terminado"
            ),
            "estado": "terminado",
            "reutilizado": reutilizado,
            "estadoAnterior": (
                resultado_estado.get(
                    "estadoAnterior"
                )
            ),
            "gorra": resultado_gorra
        }

        """
         * Aquí se liberan usuario, ruta y contadores.
         * El endpoint ya recibió estadoAnterior antes de limpiar.
        """
        self.state.limpiar()

        return resultado

    def apagar_alarma(self) -> Dict[str, Any]:
        resultado_gorra = (
            self.gorra_dispatcher.enviar(
                "STOP_ALERT"
            )
        )

        return {
            "ok": resultado_gorra.get(
                "aceptado",
                False
            ),
            "mensaje": (
                "Comando para apagar la alarma "
                "aceptado en segundo plano"
            ),
            "gorra": resultado_gorra
        }

    def estado(self) -> Dict[str, Any]:
        return self.state.obtener_estado()

    def validar_frame(
        self,
        usuario_id: Any,
        ruta_id: Any
    ) -> Tuple[bool, str]:
        return self.state.validar_frame(
            usuario_id=usuario_id,
            ruta_id=ruta_id
        )

    def registrar_frame(self):
        self.state.registrar_frame()

    def cerrar(self):
        """
        Libera los hilos del despachador durante el apagado
        controlado de FastAPI.
        """
        self.gorra_dispatcher.cerrar()