import logging
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Any, Dict

from app.services.gorra_service import GorraService


logger = logging.getLogger("somnix.gorra")


class GorraCommandDispatcher:
    """
    Envía comandos remotos a la gorra sin bloquear FastAPI.

    La comunicación principal de la aplicación es Bluetooth.
    Esta comunicación mediante .NET funciona únicamente como
    respaldo cuando existe Internet.

    Los endpoints de iniciar, pausar o terminar no esperarán
    hasta 10 segundos a que Render/.NET responda.
    """

    def __init__(
        self,
        gorra_service: GorraService,
        max_workers: int = 2,
        max_pendientes: int = 10
    ):
        self.gorra = gorra_service

        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="somnix-gorra"
        )

        self.capacidad = BoundedSemaphore(
            value=max_pendientes
        )

    def enviar(
        self,
        comando: str
    ) -> Dict[str, Any]:
        comando_seguro = str(
            comando or ""
        ).strip().upper()

        if not comando_seguro:
            return {
                "ok": False,
                "aceptado": False,
                "mensaje": "El comando está vacío."
            }

        espacio_disponible = (
            self.capacidad.acquire(
                blocking=False
            )
        )

        if not espacio_disponible:
            logger.warning(
                "Cola remota llena. Comando rechazado: %s",
                comando_seguro
            )

            return {
                "ok": False,
                "aceptado": False,
                "comando": comando_seguro,
                "mensaje": (
                    "La cola de comandos remotos está llena."
                )
            }

        try:
            future = self.executor.submit(
                self.gorra.enviar_comando,
                comando_seguro
            )

            future.add_done_callback(
                lambda tarea: self._finalizar(
                    comando_seguro,
                    tarea
                )
            )

            return {
                "ok": True,
                "aceptado": True,
                "comando": comando_seguro,
                "modo": "asincrono",
                "mensaje": (
                    "Comando remoto colocado en cola."
                )
            }

        except Exception as error:
            self.capacidad.release()

            logger.exception(
                "No se pudo colocar el comando %s en cola",
                comando_seguro
            )

            return {
                "ok": False,
                "aceptado": False,
                "comando": comando_seguro,
                "mensaje": str(error)
            }

    def _finalizar(
        self,
        comando: str,
        future: Future
    ):
        try:
            resultado = future.result()

            if resultado.get("ok", False):
                logger.info(
                    "Comando remoto completado: %s",
                    comando
                )
            else:
                logger.warning(
                    "Comando remoto fallido: %s. Resultado: %s",
                    comando,
                    resultado
                )

        except Exception:
            logger.exception(
                "Error ejecutando comando remoto: %s",
                comando
            )

        finally:
            self.capacidad.release()

    def cerrar(self):
        """
        Cierra el ejecutor cuando termina el proceso.

        wait=False evita detener el apagado del servidor por
        solicitudes externas lentas.
        """
        self.executor.shutdown(
            wait=False,
            cancel_futures=True
        )