import time
from typing import Any, Dict, Tuple

import cv2
import numpy as np

from app.detection.detector_registry import (
    DetectorRegistry
)


class FrameAnalysisError(Exception):
    """
    Error controlado durante la validación o procesamiento
    de una imagen.
    """

    def __init__(
        self,
        mensaje: str,
        codigo: str = "FRAME_INVALIDO"
    ):
        super().__init__(mensaje)

        self.mensaje = mensaje
        self.codigo = codigo


class FrameAnalysisService:
    """
    Prepara y analiza frames enviados desde Android.

    Responsabilidades:

    - Validar tamaño.
    - Decodificar JPEG.
    - Redimensionar.
    - Evaluar iluminación y nitidez.
    - Mejorar imágenes oscuras.
    - Convertir BGR a RGB.
    - Utilizar DetectorRegistry.
    - Medir tiempo de procesamiento.

    No guarda datos en Firebase.
    No administra el estado del viaje.
    """

    def __init__(
        self,
        detector_registry: DetectorRegistry,
        max_bytes: int = 5 * 1024 * 1024,
        dimension_maxima: int = 640
    ):
        self.detector_registry = (
            detector_registry
        )

        self.max_bytes = max(
            int(max_bytes),
            100_000
        )

        self.dimension_maxima = max(
            int(dimension_maxima),
            320
        )

        """
         * Evita que OpenCV cree muchos hilos internos
         * dentro de un contenedor pequeño de Render.
        """
        try:
            cv2.setNumThreads(1)
        except Exception:
            pass

    def analizar(
        self,
        usuario_id: Any,
        ruta_id: Any,
        contenido: bytes
    ) -> Dict[str, Any]:
        inicio = time.perf_counter()

        self._validar_contenido(
            contenido
        )

        frame = self._decodificar(
            contenido
        )

        alto_original, ancho_original = (
            frame.shape[:2]
        )

        frame = self._redimensionar(
            frame
        )

        alto_procesado, ancho_procesado = (
            frame.shape[:2]
        )

        brillo, nitidez = (
            self._calcular_calidad(frame)
        )

        frame_mejorado = False

        if brillo < 55.0:
            frame = self._mejorar_iluminacion(
                frame
            )

            frame_mejorado = True

            brillo, nitidez = (
                self._calcular_calidad(frame)
            )

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        """
         * ascontiguousarray evita problemas cuando una operación
         * anterior produjo memoria no contigua.
        """
        frame_rgb = np.ascontiguousarray(
            frame_rgb
        )

        resultado = (
            self.detector_registry.analizar(
                usuario_id=usuario_id,
                ruta_id=ruta_id,
                frame_rgb=frame_rgb
            )
        )

        duracion_ms = (
            time.perf_counter() - inicio
        ) * 1000.0

        calidad = self._clasificar_calidad(
            brillo=brillo,
            nitidez=nitidez
        )

        return {
            **resultado,
            "procesamiento": {
                "duracionMs": round(
                    duracion_ms,
                    1
                ),
                "bytesRecibidos": len(
                    contenido
                ),
                "anchoOriginal": int(
                    ancho_original
                ),
                "altoOriginal": int(
                    alto_original
                ),
                "anchoProcesado": int(
                    ancho_procesado
                ),
                "altoProcesado": int(
                    alto_procesado
                ),
                "brillo": round(
                    brillo,
                    1
                ),
                "nitidez": round(
                    nitidez,
                    1
                ),
                "calidad": calidad,
                "iluminacionMejorada": (
                    frame_mejorado
                )
            }
        }

    def _validar_contenido(
        self,
        contenido: bytes
    ):
        if not contenido:
            raise FrameAnalysisError(
                mensaje=(
                    "El archivo de imagen está vacío."
                ),
                codigo="FRAME_VACIO"
            )

        if len(contenido) > self.max_bytes:
            raise FrameAnalysisError(
                mensaje=(
                    "La imagen supera el tamaño máximo "
                    "permitido."
                ),
                codigo="FRAME_DEMASIADO_GRANDE"
            )

        """
         * Una imagen JPEG real normalmente será mucho mayor.
         * Este límite detecta payloads vacíos o dañados.
        """
        if len(contenido) < 1000:
            raise FrameAnalysisError(
                mensaje=(
                    "El contenido recibido es demasiado "
                    "pequeño para ser una imagen válida."
                ),
                codigo="FRAME_INCOMPLETO"
            )

    def _decodificar(
        self,
        contenido: bytes
    ):
        np_array = np.frombuffer(
            contenido,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            np_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            raise FrameAnalysisError(
                mensaje=(
                    "OpenCV no pudo decodificar la imagen."
                ),
                codigo="FRAME_NO_DECODIFICABLE"
            )

        if (
            frame.ndim != 3
            or frame.shape[2] != 3
        ):
            raise FrameAnalysisError(
                mensaje=(
                    "La imagen no contiene tres canales "
                    "de color."
                ),
                codigo="FRAME_FORMATO_INVALIDO"
            )

        alto, ancho = frame.shape[:2]

        if alto < 80 or ancho < 80:
            raise FrameAnalysisError(
                mensaje=(
                    "La resolución del frame es "
                    "demasiado pequeña."
                ),
                codigo="FRAME_RESOLUCION_BAJA"
            )

        return frame

    def _redimensionar(
        self,
        frame
    ):
        alto, ancho = frame.shape[:2]

        lado_mayor = max(
            alto,
            ancho
        )

        if lado_mayor <= self.dimension_maxima:
            return frame

        escala = (
            self.dimension_maxima /
            float(lado_mayor)
        )

        nuevo_ancho = max(
            int(round(ancho * escala)),
            1
        )

        nuevo_alto = max(
            int(round(alto * escala)),
            1
        )

        return cv2.resize(
            frame,
            (
                nuevo_ancho,
                nuevo_alto
            ),
            interpolation=cv2.INTER_AREA
        )

    def _calcular_calidad(
        self,
        frame
    ) -> Tuple[float, float]:
        gris = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        brillo = float(
            np.mean(gris)
        )

        nitidez = float(
            cv2.Laplacian(
                gris,
                cv2.CV_64F
            ).var()
        )

        return brillo, nitidez

    def _mejorar_iluminacion(
        self,
        frame
    ):
        """
        Aplica CLAHE solamente sobre luminosidad.

        No modifica directamente los canales de color, evitando
        alterar demasiado los landmarks faciales.
        """

        lab = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2LAB
        )

        canal_l, canal_a, canal_b = (
            cv2.split(lab)
        )

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )

        canal_l_mejorado = clahe.apply(
            canal_l
        )

        lab_mejorado = cv2.merge(
            (
                canal_l_mejorado,
                canal_a,
                canal_b
            )
        )

        return cv2.cvtColor(
            lab_mejorado,
            cv2.COLOR_LAB2BGR
        )

    def _clasificar_calidad(
        self,
        brillo: float,
        nitidez: float
    ) -> str:
        if brillo < 35:
            return "muy_oscura"

        if brillo > 225:
            return "sobreexpuesta"

        if nitidez < 25:
            return "borrosa"

        if brillo < 60:
            return "oscura_mejorada"

        return "adecuada"

    def puede_enviar_alerta(
        self,
        usuario_id: Any,
        ruta_id: Any
    ) -> bool:
        return (
            self.detector_registry
            .puede_enviar_alerta(
                usuario_id=usuario_id,
                ruta_id=ruta_id
            )
        )

    def eliminar_detector(
        self,
        usuario_id: Any,
        ruta_id: Any
    ) -> bool:
        return (
            self.detector_registry.eliminar(
                usuario_id=usuario_id,
                ruta_id=ruta_id
            )
        )

    def cerrar(self):
        self.detector_registry.cerrar_todos()