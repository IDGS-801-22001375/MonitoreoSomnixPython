from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Optional, Tuple


class MonitoringState:
    """
    Mantiene el estado lógico del viaje recibido desde Android.

    Esta clase no controla ninguna cámara ni crea hilos.
    Solamente administra:

    - Viaje activo.
    - Viaje pausado.
    - Usuario actual.
    - Ruta actual.
    - Última actividad.
    - Validación de frames.

    RLock evita inconsistencias cuando FastAPI recibe al mismo
    tiempo un frame y una orden de pausar o terminar.
    """

    def __init__(self):
        self._lock = RLock()

        self.activo = False
        self.pausado = False

        self.usuario_id: Optional[str] = None
        self.ruta_id: Optional[str] = None
        self.nombre_ruta: Optional[str] = None

        self.fecha_inicio: Optional[str] = None
        self.fecha_ultima_actividad: Optional[str] = None
        self.frames_recibidos = 0

    def _ahora_iso(self) -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _normalizar_id(
        self,
        value: Any
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def iniciar(
        self,
        usuario_id: Any,
        ruta_id: Any,
        nombre_ruta: Any = None
    ) -> Dict[str, Any]:
        usuario_seguro = self._normalizar_id(
            usuario_id
        )

        ruta_segura = self._normalizar_id(
            ruta_id
        )

        nombre_seguro = (
            str(nombre_ruta).strip()
            if nombre_ruta is not None
            else ""
        )

        if not usuario_seguro:
            return {
                "ok": False,
                "mensaje": (
                    "No se recibió un usuario válido."
                )
            }

        if not ruta_segura:
            return {
                "ok": False,
                "mensaje": (
                    "No se recibió una ruta válida."
                )
            }

        with self._lock:
            """
             * Esta comparación hace que iniciar sea idempotente.
             *
             * Si Android repite la solicitud porque Render tardó,
             * no se crea un segundo monitoreo.
            """
             
            if (
                self.activo
                and self.usuario_id == usuario_seguro
                and self.ruta_id == ruta_segura
            ):
                self.pausado = False
                self.fecha_ultima_actividad = (
                    self._ahora_iso()
                )

                return {
                    "ok": True,
                    "mensaje": (
                        "El monitoreo ya estaba iniciado."
                    ),
                    "reutilizado": True,
                    "estado": self.obtener_estado()
                }

            if self.activo:
                return {
                    "ok": False,
                    "mensaje": (
                        "Ya existe otro monitoreo activo."
                    ),
                    "estado": self.obtener_estado()
                }

            ahora = self._ahora_iso()

            self.activo = True
            self.pausado = False
            self.usuario_id = usuario_seguro
            self.ruta_id = ruta_segura
            self.nombre_ruta = (
                nombre_seguro or None
            )
            self.fecha_inicio = ahora
            self.fecha_ultima_actividad = ahora
            self.frames_recibidos = 0

            return {
                "ok": True,
                "mensaje": (
                    "Estado de monitoreo iniciado."
                ),
                "reutilizado": False,
                "estado": self.obtener_estado()
            }

    def pausar(self) -> Dict[str, Any]:
        with self._lock:
            if not self.activo:
                return {
                    "ok": False,
                    "mensaje": (
                        "No existe un monitoreo activo."
                    ),
                    "estado": self.obtener_estado()
                }

            if self.pausado:
                return {
                    "ok": True,
                    "mensaje": (
                        "El monitoreo ya estaba pausado."
                    ),
                    "reutilizado": True,
                    "estado": self.obtener_estado()
                }

            self.pausado = True
            self.fecha_ultima_actividad = (
                self._ahora_iso()
            )

            return {
                "ok": True,
                "mensaje": (
                    "Estado de monitoreo pausado."
                ),
                "reutilizado": False,
                "estado": self.obtener_estado()
            }

    def reanudar(self) -> Dict[str, Any]:
        with self._lock:
            if not self.activo:
                return {
                    "ok": False,
                    "mensaje": (
                        "No existe un monitoreo para reanudar."
                    ),
                    "estado": self.obtener_estado()
                }

            if not self.pausado:
                return {
                    "ok": True,
                    "mensaje": (
                        "El monitoreo ya estaba activo."
                    ),
                    "reutilizado": True,
                    "estado": self.obtener_estado()
                }

            self.pausado = False
            self.fecha_ultima_actividad = (
                self._ahora_iso()
            )

            return {
                "ok": True,
                "mensaje": (
                    "Estado de monitoreo reanudado."
                ),
                "reutilizado": False,
                "estado": self.obtener_estado()
            }

    def detener(self) -> Dict[str, Any]:
        with self._lock:
            if not self.activo:
                return {
                    "ok": True,
                    "mensaje": (
                        "El monitoreo ya estaba detenido."
                    ),
                    "reutilizado": True,
                    "estado": self.obtener_estado()
                }

            estado_anterior = self.obtener_estado()

            self.activo = False
            self.pausado = False
            self.fecha_ultima_actividad = (
                self._ahora_iso()
            )

            return {
                "ok": True,
                "mensaje": (
                    "Estado de monitoreo detenido."
                ),
                "reutilizado": False,
                "estadoAnterior": estado_anterior,
                "estado": self.obtener_estado()
            }

    def limpiar(self):
        with self._lock:
            self.activo = False
            self.pausado = False
            self.usuario_id = None
            self.ruta_id = None
            self.nombre_ruta = None
            self.fecha_inicio = None
            self.fecha_ultima_actividad = None
            self.frames_recibidos = 0

    def validar_frame(
        self,
        usuario_id: Any,
        ruta_id: Any
    ) -> Tuple[bool, str]:
        """
        Comprueba que el frame pertenezca al viaje actual.

        Evita analizar imágenes:

        - Después de terminar.
        - Mientras el viaje está pausado.
        - De otro usuario.
        - De otra ruta.
        """

        usuario_seguro = self._normalizar_id(
            usuario_id
        )

        ruta_segura = self._normalizar_id(
            ruta_id
        )

        with self._lock:
            if not self.activo:
                return (
                    False,
                    "No existe un monitoreo activo."
                )

            if self.pausado:
                return (
                    False,
                    "El monitoreo está pausado."
                )

            if self.usuario_id != usuario_seguro:
                return (
                    False,
                    "El frame no pertenece al usuario activo."
                )

            if self.ruta_id != ruta_segura:
                return (
                    False,
                    "El frame no pertenece a la ruta activa."
                )

            return (
                True,
                "Frame autorizado."
            )

    def registrar_frame(self):
        with self._lock:
            if not self.activo or self.pausado:
                return

            self.frames_recibidos += 1
            self.fecha_ultima_actividad = (
                self._ahora_iso()
            )

    def obtener_estado(self) -> Dict[str, Any]:
        with self._lock:
            if not self.activo:
                estado_actual = "inactivo"
            elif self.pausado:
                estado_actual = "pausado"
            else:
                estado_actual = "activo"

            return {
                "activo": bool(self.activo),
                "pausado": bool(self.pausado),
                "estado": estado_actual,
                "usuarioId": self.usuario_id,
                "rutaId": self.ruta_id,
                "nombreRuta": self.nombre_ruta,
                "fechaInicio": self.fecha_inicio,
                "fechaUltimaActividad": (
                    self.fecha_ultima_actividad
                ),
                "framesRecibidos": int(
                    self.frames_recibidos
                )
            }