import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional

from app.firebase.firebase_service import (
    FirebaseService
)


logger = logging.getLogger(
    "somnix.persistence"
)


@dataclass
class PersistenceState:
    lock: RLock = field(
        default_factory=RLock
    )

    ultimo_guardado: float = 0.0

    fatiga_guardada: int = 0

    ultimo_estado: str = ""
    ultimo_tipo_alerta: Optional[str] = None

    ultimos_ojos_cerrados: bool = False
    ultimo_rostro_detectado: bool = True

    ultimos_bostezos: int = 0
    ultimos_parpadeos: int = 0
    ultimos_cabeceos: int = 0

    ultimo_resultado: Optional[
        Dict[str, Any]
    ] = None

    forzar_siguiente_guardado: bool = False


class MonitoringPersistenceService:
    """
    Controla la cantidad de escrituras en Firebase.

    Se guarda una muestra cuando:

    - Es el primer frame.
    - Pasó el intervalo configurado.
    - Cambió el estado del detector.
    - Cambió el estado de los ojos.
    - Se perdió o recuperó el rostro.
    - La fatiga cambió significativamente.
    - Aumentó un contador.
    - Apareció un tipo de alerta nuevo.

    Esto evita crear cientos o miles de registros por viaje.
    """

    def __init__(
        self,
        firebase_service: FirebaseService,
        intervalo_guardado_segundos: float = 5.0,
        cambio_fatiga_minimo: int = 8
    ):
        self.firebase = firebase_service

        self.intervalo_guardado = max(
            float(intervalo_guardado_segundos),
            1.0
        )

        self.cambio_fatiga_minimo = max(
            int(cambio_fatiga_minimo),
            1
        )

        self._lock = RLock()

        self._estados: Dict[
            str,
            PersistenceState
        ] = {}

    def _normalizar_id(
        self,
        value: Any
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def _crear_clave(
        self,
        usuario_id: Any,
        ruta_id: Any
    ) -> str:
        usuario = self._normalizar_id(
            usuario_id
        )

        ruta = self._normalizar_id(
            ruta_id
        )

        if not usuario:
            raise ValueError(
                "Usuario vacío para persistencia."
            )

        if not ruta:
            raise ValueError(
                "Ruta vacía para persistencia."
            )

        return f"{usuario}::{ruta}"

    def _obtener_estado(
        self,
        clave: str
    ) -> PersistenceState:
        with self._lock:
            estado = self._estados.get(
                clave
            )

            if estado is None:
                estado = PersistenceState()

                self._estados[clave] = (
                    estado
                )

            return estado

    def procesar_resultado(
        self,
        usuario_id: Any,
        ruta_id: Any,
        resultado: Dict[str, Any]
    ) -> Dict[str, Any]:
        clave = self._crear_clave(
            usuario_id,
            ruta_id
        )

        estado_persistencia = (
            self._obtener_estado(clave)
        )

        ahora = time.monotonic()

        with estado_persistencia.lock:
            debe_guardar, motivo = (
                self._debe_guardar(
                    estado_persistencia,
                    resultado,
                    ahora
                )
            )

            estado_persistencia.ultimo_resultado = (
                dict(resultado)
            )

            if not debe_guardar:
                self._actualizar_observacion(
                    estado_persistencia,
                    resultado
                )

                return {
                    "ok": True,
                    "guardado": False,
                    "motivo": motivo
                }

            try:
                data = self._guardar(
                    usuario_id=usuario_id,
                    ruta_id=ruta_id,
                    resultado=resultado
                )

                estado_persistencia.ultimo_guardado = (
                    ahora
                )

                estado_persistencia.fatiga_guardada = (
                    self._to_int(
                        resultado.get(
                            "fatiga",
                            0
                        )
                    )
                )

                estado_persistencia.forzar_siguiente_guardado = (
                    False
                )

                self._actualizar_observacion(
                    estado_persistencia,
                    resultado
                )

                return {
                    "ok": True,
                    "guardado": True,
                    "motivo": motivo,
                    "data": data
                }

            except Exception as error:
                estado_persistencia.forzar_siguiente_guardado = (
                    True
                )

                logger.exception(
                    "Error guardando monitoreo %s",
                    clave
                )

                return {
                    "ok": False,
                    "guardado": False,
                    "motivo": "error_firebase",
                    "mensaje": str(error)
                }

    def _debe_guardar(
        self,
        estado: PersistenceState,
        resultado: Dict[str, Any],
        ahora: float
    ):
        if estado.forzar_siguiente_guardado:
            return (
                True,
                "reintento"
            )

        if estado.ultimo_guardado <= 0:
            return (
                True,
                "primer_frame"
            )

        transcurrido = (
            ahora - estado.ultimo_guardado
        )

        if transcurrido >= self.intervalo_guardado:
            return (
                True,
                "intervalo"
            )

        estado_detector = str(
            resultado.get(
                "estado",
                "SIN_DATOS"
            )
        ).strip()

        if (
            estado.ultimo_estado
            and estado_detector !=
            estado.ultimo_estado
        ):
            return (
                True,
                "cambio_estado"
            )

        ojos_cerrados = bool(
            resultado.get(
                "ojos_cerrados",
                False
            )
        )

        if (
            ojos_cerrados !=
            estado.ultimos_ojos_cerrados
        ):
            return (
                True,
                "cambio_ojos"
            )

        rostro_detectado = bool(
            resultado.get(
                "rostro_detectado",
                True
            )
        )

        if (
            rostro_detectado !=
            estado.ultimo_rostro_detectado
        ):
            return (
                True,
                "cambio_rostro"
            )

        fatiga = self._to_int(
            resultado.get(
                "fatiga",
                0
            )
        )

        diferencia_fatiga = abs(
            fatiga -
            estado.fatiga_guardada
        )

        if (
            diferencia_fatiga >=
            self.cambio_fatiga_minimo
        ):
            return (
                True,
                "cambio_fatiga"
            )

        bostezos = self._to_int(
            resultado.get(
                "bostezos",
                0
            )
        )

        if bostezos > estado.ultimos_bostezos:
            return (
                True,
                "nuevo_bostezo"
            )

        parpadeos = self._to_int(
            resultado.get(
                "parpadeos",
                0
            )
        )

        if (
            parpadeos >
            estado.ultimos_parpadeos
        ):
            return (
                True,
                "nuevo_parpadeo"
            )

        cabeceos = self._to_int(
            resultado.get(
                "cabeceos",
                0
            )
        )

        if cabeceos > estado.ultimos_cabeceos:
            return (
                True,
                "nuevo_cabeceo"
            )

        tipo_alerta = resultado.get(
            "tipo_alerta"
        )

        if (
            tipo_alerta
            and tipo_alerta !=
            estado.ultimo_tipo_alerta
        ):
            return (
                True,
                "nueva_alerta"
            )

        return (
            False,
            "sin_cambios_importantes"
        )

    def _actualizar_observacion(
        self,
        estado: PersistenceState,
        resultado: Dict[str, Any]
    ):
        estado.ultimo_estado = str(
            resultado.get(
                "estado",
                "SIN_DATOS"
            )
        ).strip()

        estado.ultimo_tipo_alerta = (
            resultado.get(
                "tipo_alerta"
            )
        )

        estado.ultimos_ojos_cerrados = bool(
            resultado.get(
                "ojos_cerrados",
                False
            )
        )

        estado.ultimo_rostro_detectado = bool(
            resultado.get(
                "rostro_detectado",
                True
            )
        )

        estado.ultimos_bostezos = self._to_int(
            resultado.get(
                "bostezos",
                0
            )
        )

        estado.ultimos_parpadeos = self._to_int(
            resultado.get(
                "parpadeos",
                0
            )
        )

        estado.ultimos_cabeceos = self._to_int(
            resultado.get(
                "cabeceos",
                0
            )
        )

    def _guardar(
        self,
        usuario_id: Any,
        ruta_id: Any,
        resultado: Dict[str, Any]
    ):
        procesamiento = resultado.get(
            "procesamiento",
            {}
        )

        return self.firebase.crear_monitoreo(
            usuario_id=usuario_id,
            ruta_id=ruta_id,
            ojos_cerrados=resultado.get(
                "ojos_cerrados",
                False
            ),
            fatiga=resultado.get(
                "fatiga",
                0
            ),
            bostezos=resultado.get(
                "bostezos",
                0
            ),
            estado_camara="activa",
            parpadeos=resultado.get(
                "parpadeos",
                0
            ),
            cabeceos=resultado.get(
                "cabeceos",
                0
            ),
            perclos=resultado.get(
                "perclos",
                0.0
            ),
            ear=resultado.get(
                "ear",
                0.0
            ),
            mar=resultado.get(
                "mar",
                0.0
            ),
            estado_detector=resultado.get(
                "estado",
                "SIN_DATOS"
            ),
            rostro_detectado=resultado.get(
                "rostro_detectado",
                True
            ),
            tiempo_ojos_cerrados=(
                resultado.get(
                    "tiempo_ojos_cerrados",
                    0.0
                )
            ),
            procesamiento_ms=(
                procesamiento.get(
                    "duracionMs",
                    0.0
                )
            ),
            calidad_frame=(
                procesamiento.get(
                    "calidad",
                    "sin_datos"
                )
            )
        )

    def finalizar_sesion(
        self,
        usuario_id: Any,
        ruta_id: Any
    ) -> Dict[str, Any]:
        try:
            clave = self._crear_clave(
                usuario_id,
                ruta_id
            )
        except ValueError:
            return {
                "ok": False,
                "guardado": False,
                "mensaje": (
                    "No se pudo identificar la sesión."
                )
            }

        with self._lock:
            estado = self._estados.pop(
                clave,
                None
            )

        if estado is None:
            return {
                "ok": True,
                "guardado": False,
                "mensaje": (
                    "No existía persistencia pendiente."
                )
            }

        with estado.lock:
            ultimo_resultado = (
                estado.ultimo_resultado
            )

            if ultimo_resultado is None:
                return {
                    "ok": True,
                    "guardado": False,
                    "mensaje": (
                        "La sesión no recibió frames."
                    )
                }

            try:
                data = self._guardar(
                    usuario_id=usuario_id,
                    ruta_id=ruta_id,
                    resultado=ultimo_resultado
                )

                return {
                    "ok": True,
                    "guardado": True,
                    "mensaje": (
                        "Muestra final guardada."
                    ),
                    "data": data
                }

            except Exception as error:
                logger.exception(
                    "Error guardando muestra final %s",
                    clave
                )

                return {
                    "ok": False,
                    "guardado": False,
                    "mensaje": str(error)
                }

    def descartar_sesion(
        self,
        usuario_id: Any,
        ruta_id: Any
    ):
        try:
            clave = self._crear_clave(
                usuario_id,
                ruta_id
            )
        except ValueError:
            return

        with self._lock:
            self._estados.pop(
                clave,
                None
            )

    def _to_int(
        self,
        value: Any
    ) -> int:
        try:
            return max(
                int(float(value)),
                0
            )
        except (TypeError, ValueError):
            return 0