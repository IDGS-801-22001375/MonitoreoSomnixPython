import logging
import time
from dataclasses import dataclass
from threading import RLock
from typing import Dict, Optional, Tuple

from app.detection.drowsiness_detector import (
    DrowsinessDetector
)


logger = logging.getLogger(
    "somnix.detectors"
)


@dataclass
class DetectorEntry:
    detector: DrowsinessDetector
    lock: RLock
    ultima_actividad: float


class DetectorRegistry:
    """
    Administra un detector independiente por usuario y ruta.

    MediaPipe conserva información temporal, por ejemplo:

    - Calibración de inclinación.
    - Inicio del cierre de ojos.
    - Bostezos.
    - Parpadeos.
    - Cabeceos.
    - Historial PERCLOS.

    Por eso no debe existir un único detector global compartido
    entre todos los viajes.

    Cada detector también tiene su propio lock porque FaceMesh
    no debe procesar dos imágenes simultáneamente.
    """

    def __init__(
        self,
        tiempo_expiracion_segundos: int = 1800,
        max_detectores: int = 4
    ):
        self.tiempo_expiracion_segundos = max(
            int(tiempo_expiracion_segundos),
            60
        )

        self.max_detectores = max(
            int(max_detectores),
            1
        )

        self._lock = RLock()

        self._detectores: Dict[
            str,
            DetectorEntry
        ] = {}

    def _normalizar_id(
        self,
        value
    ) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def _crear_clave(
        self,
        usuario_id,
        ruta_id
    ) -> str:
        usuario = self._normalizar_id(
            usuario_id
        )

        ruta = self._normalizar_id(
            ruta_id
        )

        if not usuario:
            raise ValueError(
                "El usuario del detector está vacío."
            )

        if not ruta:
            raise ValueError(
                "La ruta del detector está vacía."
            )

        return f"{usuario}::{ruta}"

    def obtener(
        self,
        usuario_id,
        ruta_id
    ) -> Tuple[str, DetectorEntry]:
        clave = self._crear_clave(
            usuario_id,
            ruta_id
        )

        ahora = time.monotonic()

        self.limpiar_inactivos(
            ahora=ahora
        )

        with self._lock:
            entry = self._detectores.get(
                clave
            )

            if entry is not None:
                entry.ultima_actividad = ahora
                return clave, entry

            self._liberar_espacio_si_es_necesario()

            entry = DetectorEntry(
                detector=DrowsinessDetector(),
                lock=RLock(),
                ultima_actividad=ahora
            )

            self._detectores[clave] = entry

            logger.info(
                "Detector creado para %s",
                clave
            )

            return clave, entry

    def analizar(
        self,
        usuario_id,
        ruta_id,
        frame_rgb
    ):
        clave, entry = self.obtener(
            usuario_id=usuario_id,
            ruta_id=ruta_id
        )

        """
         * El lock pertenece únicamente a este detector.
         * Otros viajes no comparten el mismo FaceMesh.
        """
        with entry.lock:
            entry.ultima_actividad = (
                time.monotonic()
            )

            resultado = entry.detector.analizar(
                frame_rgb
            )

            entry.ultima_actividad = (
                time.monotonic()
            )

        logger.debug(
            "Frame analizado para %s",
            clave
        )

        return resultado

    def puede_enviar_alerta(
        self,
        usuario_id,
        ruta_id
    ) -> bool:
        _, entry = self.obtener(
            usuario_id=usuario_id,
            ruta_id=ruta_id
        )

        with entry.lock:
            return (
                entry.detector
                .puede_enviar_alerta()
            )

    def eliminar(
        self,
        usuario_id,
        ruta_id
    ) -> bool:
        try:
            clave = self._crear_clave(
                usuario_id,
                ruta_id
            )
        except ValueError:
            return False

        with self._lock:
            entry = self._detectores.pop(
                clave,
                None
            )

        if entry is None:
            return False

        self._cerrar_entry(
            clave,
            entry
        )

        return True

    def limpiar_inactivos(
        self,
        ahora: Optional[float] = None
    ) -> int:
        momento = (
            ahora
            if ahora is not None
            else time.monotonic()
        )

        expirados = []

        with self._lock:
            for clave, entry in list(
                self._detectores.items()
            ):
                tiempo_inactivo = (
                    momento -
                    entry.ultima_actividad
                )

                if (
                    tiempo_inactivo >=
                    self.tiempo_expiracion_segundos
                ):
                    expirados.append(
                        (
                            clave,
                            self._detectores.pop(
                                clave
                            )
                        )
                    )

        for clave, entry in expirados:
            self._cerrar_entry(
                clave,
                entry
            )

        return len(expirados)

    def _liberar_espacio_si_es_necesario(
        self
    ):
        if (
            len(self._detectores) <
            self.max_detectores
        ):
            return

        clave_antigua = min(
            self._detectores,
            key=lambda clave: (
                self._detectores[
                    clave
                ].ultima_actividad
            )
        )

        entry = self._detectores.pop(
            clave_antigua
        )

        self._cerrar_entry(
            clave_antigua,
            entry
        )

    def _cerrar_entry(
        self,
        clave: str,
        entry: DetectorEntry
    ):
        try:
            with entry.lock:
                cerrar = getattr(
                    entry.detector,
                    "cerrar",
                    None
                )

                if callable(cerrar):
                    cerrar()

        except Exception:
            logger.exception(
                "Error cerrando detector %s",
                clave
            )

        logger.info(
            "Detector liberado: %s",
            clave
        )

    def cerrar_todos(self):
        with self._lock:
            entries = list(
                self._detectores.items()
            )

            self._detectores.clear()

        for clave, entry in entries:
            self._cerrar_entry(
                clave,
                entry
            )

    def total_detectores(self) -> int:
        with self._lock:
            return len(
                self._detectores
            )