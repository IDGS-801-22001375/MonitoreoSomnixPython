import logging
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict

from app.config import TIEMPO_ENTRE_ALERTAS
from app.firebase.firebase_service import (
    FirebaseService
)


logger = logging.getLogger(
    "somnix.alertas"
)


@dataclass
class AlertSessionState:
    lock: RLock = field(
        default_factory=RLock
    )

    ultimos_eventos: Dict[
        str,
        float
    ] = field(
        default_factory=dict
    )

    ultimas_notificaciones_fatiga: Dict[
        str,
        float
    ] = field(
        default_factory=dict
    )


class AlertManagementService:
    """
    Centraliza alertas y notificaciones del detector.

    Evita que un mismo frame genere simultáneamente:

    - Una alerta por fatiga.
    - Otra alerta por tipo_alerta.
    - Varias notificaciones idénticas.

    Los eventos específicos tienen prioridad sobre una alerta
    genérica de fatiga.
    """

    def __init__(
        self,
        firebase_service: FirebaseService,
        cooldown_notificacion_segundos: float = 180.0
    ):
        self.firebase = firebase_service

        self.cooldown_evento = max(
            float(TIEMPO_ENTRE_ALERTAS),
            10.0
        )

        self.cooldown_notificacion = max(
            float(
                cooldown_notificacion_segundos
            ),
            30.0
        )

        self._lock = RLock()

        self._sesiones: Dict[
            str,
            AlertSessionState
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

        if not usuario or not ruta:
            raise ValueError(
                "No se pudo identificar la sesión."
            )

        return f"{usuario}::{ruta}"

    def _obtener_estado(
        self,
        clave: str
    ) -> AlertSessionState:
        with self._lock:
            estado = self._sesiones.get(
                clave
            )

            if estado is None:
                estado = AlertSessionState()

                self._sesiones[clave] = (
                    estado
                )

            return estado

    def procesar_resultado(
        self,
        usuario_id: Any,
        ruta_id: Any,
        resultado: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            clave = self._crear_clave(
                usuario_id,
                ruta_id
            )
        except ValueError as error:
            return {
                "ok": False,
                "alertaCreada": False,
                "notificacionCreada": False,
                "mensaje": str(error)
            }

        estado_sesion = self._obtener_estado(
            clave
        )

        ahora = time.monotonic()

        fatiga = self._to_int(
            resultado.get(
                "fatiga",
                0
            )
        )

        tipo_alerta = str(
            resultado.get(
                "tipo_alerta"
            ) or ""
        ).strip().lower()

        nivel = str(
            resultado.get(
                "nivel",
                "bajo"
            )
        ).strip().lower()

        mensaje = str(
            resultado.get(
                "mensaje",
                "Se detectó una condición de riesgo."
            )
        ).strip()

        with estado_sesion.lock:
            evento_especifico = (
                tipo_alerta
                not in {
                    "",
                    "fatiga_alta",
                    "fatiga_moderada"
                }
            )

            resultado_evento = {
                "alertaCreada": False,
                "notificacionCreada": False
            }

            if evento_especifico:
                resultado_evento = (
                    self._procesar_evento(
                        estado=estado_sesion,
                        ahora=ahora,
                        usuario_id=usuario_id,
                        ruta_id=ruta_id,
                        tipo_alerta=tipo_alerta,
                        mensaje=mensaje,
                        nivel=nivel
                    )
                )

            resultado_fatiga = {
                "alertaCreada": False,
                "notificacionCreada": False
            }

            """
             * Si ya se creó una alerta específica en este frame,
             * no se genera además una alerta genérica de fatiga.
            """
            if not resultado_evento.get(
                "alertaCreada",
                False
            ):
                resultado_fatiga = (
                    self._procesar_fatiga(
                        estado=estado_sesion,
                        ahora=ahora,
                        usuario_id=usuario_id,
                        ruta_id=ruta_id,
                        fatiga=fatiga
                    )
                )

            return {
                "ok": True,
                "alertaCreada": (
                    resultado_evento.get(
                        "alertaCreada",
                        False
                    )
                    or resultado_fatiga.get(
                        "alertaCreada",
                        False
                    )
                ),
                "notificacionCreada": (
                    resultado_evento.get(
                        "notificacionCreada",
                        False
                    )
                    or resultado_fatiga.get(
                        "notificacionCreada",
                        False
                    )
                ),
                "evento": resultado_evento,
                "fatiga": resultado_fatiga
            }

    def _procesar_evento(
        self,
        estado: AlertSessionState,
        ahora: float,
        usuario_id: Any,
        ruta_id: Any,
        tipo_alerta: str,
        mensaje: str,
        nivel: str
    ) -> Dict[str, Any]:
        ultima_vez = (
            estado.ultimos_eventos.get(
                tipo_alerta,
                0.0
            )
        )

        if (
            ahora - ultima_vez
            < self.cooldown_evento
        ):
            return {
                "alertaCreada": False,
                "notificacionCreada": False,
                "motivo": "cooldown_evento"
            }

        nivel_seguro = (
            nivel
            if nivel in {
                "bajo",
                "medio",
                "alto"
            }
            else "medio"
        )

        titulo = self._titulo_evento(
            tipo_alerta
        )

        alerta_creada = False
        notificacion_creada = False

        try:
            self.firebase.crear_alerta(
                usuario_id,
                ruta_id,
                tipo_alerta,
                mensaje,
                nivel_seguro
            )

            alerta_creada = True

        except Exception:
            logger.exception(
                "Error creando alerta %s",
                tipo_alerta
            )

        try:
            self.firebase.crear_notificacion(
                usuario_id,
                titulo,
                mensaje,
                tipo_alerta
            )

            notificacion_creada = True

        except Exception:
            logger.exception(
                "Error creando notificación %s",
                tipo_alerta
            )

        if (
            alerta_creada
            or notificacion_creada
        ):
            estado.ultimos_eventos[
                tipo_alerta
            ] = ahora

        return {
            "alertaCreada": alerta_creada,
            "notificacionCreada": (
                notificacion_creada
            ),
            "tipo": tipo_alerta,
            "nivel": nivel_seguro
        }

    def _procesar_fatiga(
        self,
        estado: AlertSessionState,
        ahora: float,
        usuario_id: Any,
        ruta_id: Any,
        fatiga: int
    ) -> Dict[str, Any]:
        configuracion = (
            self._configuracion_fatiga(
                fatiga
            )
        )

        if configuracion is None:
            return {
                "alertaCreada": False,
                "notificacionCreada": False,
                "motivo": "fatiga_baja"
            }

        clave_nivel = configuracion[
            "clave"
        ]

        ultima_vez = (
            estado
            .ultimas_notificaciones_fatiga
            .get(
                clave_nivel,
                0.0
            )
        )

        if (
            ahora - ultima_vez
            < self.cooldown_notificacion
        ):
            return {
                "alertaCreada": False,
                "notificacionCreada": False,
                "motivo": "cooldown_fatiga",
                "nivelFatiga": clave_nivel
            }

        alerta_creada = False
        notificacion_creada = False

        if configuracion["crear_alerta"]:
            try:
                self.firebase.crear_alerta(
                    usuario_id,
                    ruta_id,
                    configuracion[
                        "tipo"
                    ],
                    configuracion[
                        "mensaje_alerta"
                    ].format(
                        fatiga=fatiga
                    ),
                    configuracion[
                        "nivel"
                    ]
                )

                alerta_creada = True

            except Exception:
                logger.exception(
                    "Error creando alerta de fatiga"
                )

        try:
            self.firebase.crear_notificacion(
                usuario_id,
                configuracion["titulo"],
                configuracion[
                    "mensaje_notificacion"
                ].format(
                    fatiga=fatiga
                ),
                configuracion["tipo"]
            )

            notificacion_creada = True

        except Exception:
            logger.exception(
                "Error creando notificación de fatiga"
            )

        if (
            alerta_creada
            or notificacion_creada
        ):
            estado.ultimas_notificaciones_fatiga[
                clave_nivel
            ] = ahora

        return {
            "alertaCreada": alerta_creada,
            "notificacionCreada": (
                notificacion_creada
            ),
            "nivelFatiga": clave_nivel,
            "fatiga": fatiga
        }

    def _configuracion_fatiga(
        self,
        fatiga: int
    ):
        if fatiga >= 50:
            return {
                "clave": "fatiga_50",
                "tipo": "fatiga_alta",
                "nivel": "alto",
                "crear_alerta": True,
                "titulo": (
                    "Fatiga alta detectada"
                ),
                "mensaje_alerta": (
                    "Fatiga elevada detectada: "
                    "{fatiga}%. Se recomienda "
                    "detener el viaje."
                ),
                "mensaje_notificacion": (
                    "Tu nivel de fatiga es alto "
                    "({fatiga}%). ¿Deseas pausar "
                    "el viaje o descansar?"
                )
            }

        if fatiga >= 30:
            return {
                "clave": "fatiga_30",
                "tipo": "fatiga_moderada",
                "nivel": "medio",
                "crear_alerta": False,
                "titulo": "Fatiga moderada",
                "mensaje_alerta": "",
                "mensaje_notificacion": (
                    "Tu fatiga está aumentando "
                    "({fatiga}%). Considera tomar "
                    "un descanso."
                )
            }

        if fatiga >= 20:
            return {
                "clave": "fatiga_20",
                "tipo": "fatiga_leve",
                "nivel": "bajo",
                "crear_alerta": False,
                "titulo": "Atención",
                "mensaje_alerta": "",
                "mensaje_notificacion": (
                    "Se detectan señales leves "
                    "de cansancio ({fatiga}%)."
                )
            }

        if fatiga >= 10:
            return {
                "clave": "fatiga_10",
                "tipo": "recomendacion",
                "nivel": "bajo",
                "crear_alerta": False,
                "titulo": "Recomendación",
                "mensaje_alerta": "",
                "mensaje_notificacion": (
                    "Mantente alerta. Fatiga "
                    "estimada: {fatiga}%."
                )
            }

        return None

    def _titulo_evento(
        self,
        tipo_alerta: str
    ) -> str:
        titulos = {
            "ojos_cerrados": (
                "Ojos cerrados"
            ),
            "cabeceo": (
                "Cabeceo detectado"
            ),
            "bostezo": (
                "Bostezo detectado"
            ),
            "sin_rostro": (
                "Conductor no visible"
            )
        }

        return titulos.get(
            tipo_alerta,
            "Alerta de fatiga"
        )

    def limpiar_sesion(
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
            self._sesiones.pop(
                clave,
                None
            )

    def _to_int(
        self,
        value: Any
    ) -> int:
        try:
            return max(
                0,
                min(
                    int(float(value)),
                    100
                )
            )
        except (TypeError, ValueError):
            return 0