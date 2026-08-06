import statistics
import time
from collections import deque
from typing import Any, Dict, List

import mediapipe as mp

from app.config import (
    TIEMPO_ENTRE_ALERTAS,
    TIEMPO_OJOS_CERRADOS
)
from app.utils.math_utils import distancia


class DrowsinessDetector:
    """
    Detector temporal de somnolencia.

    Está diseñado para recibir frames independientes enviados
    desde la aplicación Android.

    Detecta:

    - Ojos cerrados.
    - PERCLOS basado en duración.
    - Bostezos sostenidos.
    - Cabeceos sostenidos.
    - Ausencia prolongada de rostro.
    - Fatiga suavizada.
    """

    def __init__(self):
        self.face_mesh = (
            mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        )

        # Ojos

        self.ojo_izquierdo = [
            159, 158, 145, 153, 33, 133
        ]

        self.ojo_derecho = [
            386, 385, 374, 380, 362, 263
        ]

        self.EAR_UMBRAL_BASE = 0.20
        self.ear_umbral_actual = (
            self.EAR_UMBRAL_BASE
        )

        self.muestras_ear_abierto: List[float] = []
        self.max_muestras_ear = 30

        self.ojo_estaba_cerrado = False
        self.ojos_cerrados_inicio = None
        self.contador_parpadeos = 0

        # Boca y bostezos

        self.boca_puntos = [
            13, 14, 78, 308
        ]

        self.MAR_UMBRAL = 0.42
        self.TIEMPO_MINIMO_BOSTEZO = 0.7

        self.boca_abierta_inicio = None
        self.bostezo_en_curso = False
        self.bostezo_confirmado = False
        self.contador_bostezos = 0

        # Cabeceos

        self.frente = 10
        self.barbilla = 152
        self.nariz = 1

        self.baseline_inclinacion = None
        self.muestras_inclinacion: List[float] = []
        self.max_muestras_inclinacion = 30

        self.UMBRAL_CABECEO = 0.16
        self.TIEMPO_MINIMO_CABECEO = 0.5

        self.cabeceo_inicio = None
        self.cabeceo_en_curso = False
        self.cabeceo_confirmado = False
        self.contador_cabeceos = 0

        # Rostro

        self.sin_rostro_inicio = None
        self.TIEMPO_SIN_ROSTRO_ALERTA = 3.0

        # Fatiga

        self.fatiga_suavizada = 0.0

        # Alertas

        self.ultimo_envio_alerta = 0.0

        # Historial temporal PERCLOS

        self.ventana_segundos = 60.0
        self.max_intervalo_muestra = 3.0
        self.historial = deque()

    def calcular_ear(
        self,
        puntos,
        indices
    ) -> float:
        sup1, sup2, inf1, inf2, izq, der = (
            indices
        )

        vertical1 = distancia(
            puntos[sup1],
            puntos[inf1]
        )

        vertical2 = distancia(
            puntos[sup2],
            puntos[inf2]
        )

        horizontal = distancia(
            puntos[izq],
            puntos[der]
        )

        if horizontal <= 0.000001:
            return 0.0

        return (
            vertical1 + vertical2
        ) / (2.0 * horizontal)

    def calcular_mar(
        self,
        puntos
    ) -> float:
        sup, inf, izq, der = self.boca_puntos

        vertical = distancia(
            puntos[sup],
            puntos[inf]
        )

        horizontal = distancia(
            puntos[izq],
            puntos[der]
        )

        if horizontal <= 0.000001:
            return 0.0

        return vertical / horizontal

    def calibrar_ear(
        self,
        ear: float
    ):
        """
        Ajusta el umbral de cierre de ojos al conductor.

        Solamente utiliza muestras que razonablemente
        representan ojos abiertos.
        """

        if (
            len(self.muestras_ear_abierto)
            >= self.max_muestras_ear
        ):
            return

        if 0.18 <= ear <= 0.45:
            self.muestras_ear_abierto.append(
                ear
            )

        if (
            len(self.muestras_ear_abierto)
            >= 10
        ):
            ear_base = statistics.median(
                self.muestras_ear_abierto
            )

            umbral_adaptado = (
                ear_base * 0.72
            )

            self.ear_umbral_actual = max(
                0.16,
                min(umbral_adaptado, 0.24)
            )

    def calibrar_inclinacion(
        self,
        inclinacion: float
    ):
        if (
            len(self.muestras_inclinacion)
            >= self.max_muestras_inclinacion
        ):
            return

        self.muestras_inclinacion.append(
            inclinacion
        )

        if (
            len(self.muestras_inclinacion)
            >= 10
        ):
            self.baseline_inclinacion = (
                statistics.median(
                    self.muestras_inclinacion
                )
            )

    def registrar_historial(
        self,
        rostro_detectado: bool,
        ojos_cerrados: bool,
        bostezo: bool,
        cabeceo: bool,
        ahora: float
    ):
        self.historial.append({
            "tiempo": ahora,
            "rostro_detectado": rostro_detectado,
            "ojos_cerrados": ojos_cerrados,
            "bostezo": bostezo,
            "cabeceo": cabeceo
        })

        limite = (
            ahora - self.ventana_segundos
        )

        while (
            self.historial
            and self.historial[0]["tiempo"]
            < limite - self.max_intervalo_muestra
        ):
            self.historial.popleft()

    def calcular_perclos(
        self,
        ahora: float
    ) -> float:
        """
        Calcula el porcentaje de tiempo observado durante
        el cual los ojos permanecieron cerrados.

        Los periodos sin rostro no se consideran ojos abiertos.
        Los huecos de red mayores a tres segundos tampoco se
        cuentan completamente.
        """

        if len(self.historial) < 2:
            return 0.0

        elementos = list(self.historial)

        inicio_ventana = (
            ahora - self.ventana_segundos
        )

        tiempo_observado = 0.0
        tiempo_cerrado = 0.0

        for indice, item in enumerate(
            elementos
        ):
            inicio = max(
                item["tiempo"],
                inicio_ventana
            )

            if indice + 1 < len(elementos):
                fin = elementos[
                    indice + 1
                ]["tiempo"]
            else:
                fin = ahora

            duracion = max(
                0.0,
                fin - inicio
            )

            duracion = min(
                duracion,
                self.max_intervalo_muestra
            )

            if (
                duracion <= 0
                or not item["rostro_detectado"]
            ):
                continue

            tiempo_observado += duracion

            if item["ojos_cerrados"]:
                tiempo_cerrado += duracion

        if tiempo_observado <= 0:
            return 0.0

        return max(
            0.0,
            min(
                tiempo_cerrado /
                tiempo_observado,
                1.0
            )
        )

    def contar_eventos_recientes(
        self,
        campo: str
    ) -> int:
        return sum(
            1
            for item in self.historial
            if item.get(campo, False)
        )

    def calcular_fatiga(
        self,
        perclos: float,
        tiempo_cerrado: float,
        bostezos_recientes: int,
        cabeceos_recientes: int
    ) -> int:
        fatiga = perclos * 65.0

        if (
            tiempo_cerrado >=
            TIEMPO_OJOS_CERRADOS
        ):
            bono_ojos = 75.0
        elif tiempo_cerrado >= 2.0:
            bono_ojos = 50.0
        elif tiempo_cerrado >= 1.0:
            bono_ojos = 30.0
        elif tiempo_cerrado >= 0.5:
            bono_ojos = 12.0
        else:
            bono_ojos = 0.0

        fatiga += bono_ojos

        fatiga += min(
            bostezos_recientes * 8.0,
            24.0
        )

        fatiga += min(
            cabeceos_recientes * 15.0,
            30.0
        )

        fatiga_cruda = max(
            0.0,
            min(fatiga, 100.0)
        )

        if (
            fatiga_cruda >=
            self.fatiga_suavizada
        ):
            factor = 0.55
        else:
            factor = 0.18

        fatiga_anterior = self.fatiga_suavizada

        fatiga_calculada = (
            self.fatiga_suavizada
            + factor
            * (
                fatiga_cruda
                - self.fatiga_suavizada
            )
        )

        # Evita saltos visuales como 0 -> 75 en un solo frame.
        # Con el intervalo actual de Android (750 ms), la fatiga
        # puede avanzar aproximadamente 6 puntos por respuesta:
        # 0, 6, 12, 18... La alarma de 15% sigue activándose.
        if (
            fatiga_calculada >
            fatiga_anterior
        ):
            self.fatiga_suavizada = min(
                fatiga_calculada,
                fatiga_anterior + 6.0
            )
        else:
            self.fatiga_suavizada = (
                fatiga_calculada
            )

        return min(
            int(round(self.fatiga_suavizada)),
            100
        )

    def analizar(
        self,
        frame_rgb
    ) -> Dict[str, Any]:
        ahora = time.monotonic()

        resultado = self.face_mesh.process(
            frame_rgb
        )

        if not resultado.multi_face_landmarks:
            if self.sin_rostro_inicio is None:
                self.sin_rostro_inicio = ahora

            tiempo_sin_rostro = (
                ahora - self.sin_rostro_inicio
            )

            self.boca_abierta_inicio = None
            self.bostezo_en_curso = False
            self.bostezo_confirmado = False

            self.cabeceo_inicio = None
            self.cabeceo_en_curso = False
            self.cabeceo_confirmado = False

            self.registrar_historial(
                rostro_detectado=False,
                ojos_cerrados=False,
                bostezo=False,
                cabeceo=False,
                ahora=ahora
            )

            perclos = self.calcular_perclos(
                ahora
            )

            if (
                tiempo_sin_rostro >=
                self.TIEMPO_SIN_ROSTRO_ALERTA
            ):
                return self._respuesta_base(
                    estado="SIN_ROSTRO",
                    mensaje=(
                        "No se detecta el rostro "
                        "del conductor."
                    ),
                    nivel="medio",
                    tipo_alerta="sin_rostro",
                    fatiga=int(
                        round(
                            self.fatiga_suavizada
                        )
                    ),
                    perclos=perclos,
                    tiempo_sin_rostro=(
                        tiempo_sin_rostro
                    )
                )

            return self._respuesta_base(
                estado="BUSCANDO_ROSTRO",
                mensaje=(
                    "Buscando el rostro "
                    "del conductor."
                ),
                nivel="bajo",
                tipo_alerta=None,
                fatiga=int(
                    round(
                        self.fatiga_suavizada
                    )
                ),
                perclos=perclos,
                tiempo_sin_rostro=(
                    tiempo_sin_rostro
                )
            )

        self.sin_rostro_inicio = None

        puntos = (
            resultado
            .multi_face_landmarks[0]
            .landmark
        )

        # Ojos

        ear_izq = self.calcular_ear(
            puntos,
            self.ojo_izquierdo
        )

        ear_der = self.calcular_ear(
            puntos,
            self.ojo_derecho
        )

        ear = (
            ear_izq + ear_der
        ) / 2.0

        self.calibrar_ear(ear)

        ojos_cerrados = (
            ear < self.ear_umbral_actual
        )

        if (
            ojos_cerrados
            and not self.ojo_estaba_cerrado
        ):
            self.ojos_cerrados_inicio = ahora

        if (
            not ojos_cerrados
            and self.ojo_estaba_cerrado
        ):
            duracion_cierre = (
                ahora -
                (
                    self.ojos_cerrados_inicio
                    or ahora
                )
            )

            if (
                0.08 <= duracion_cierre
                < TIEMPO_OJOS_CERRADOS
            ):
                self.contador_parpadeos += 1

        self.ojo_estaba_cerrado = (
            ojos_cerrados
        )

        if ojos_cerrados:
            tiempo_cerrado = (
                ahora -
                (
                    self.ojos_cerrados_inicio
                    or ahora
                )
            )
        else:
            tiempo_cerrado = 0.0
            self.ojos_cerrados_inicio = None

        # Bostezos

        mar = self.calcular_mar(puntos)

        boca_abierta = (
            mar > self.MAR_UMBRAL
        )

        bostezo_detectado = False

        if boca_abierta:
            if self.boca_abierta_inicio is None:
                self.boca_abierta_inicio = ahora
                self.bostezo_en_curso = True
                self.bostezo_confirmado = False

            duracion_boca_abierta = (
                ahora -
                self.boca_abierta_inicio
            )

            if (
                duracion_boca_abierta >=
                self.TIEMPO_MINIMO_BOSTEZO
                and not self.bostezo_confirmado
            ):
                self.bostezo_confirmado = True
                self.contador_bostezos += 1
                bostezo_detectado = True

        else:
            self.boca_abierta_inicio = None
            self.bostezo_en_curso = False
            self.bostezo_confirmado = False

        # Cabeceos

        alto_cara = distancia(
            puntos[self.frente],
            puntos[self.barbilla]
        )

        if alto_cara <= 0.000001:
            inclinacion = (
                self.baseline_inclinacion
                or 0.0
            )
        else:
            inclinacion = (
                puntos[self.barbilla].y
                - puntos[self.nariz].y
            ) / alto_cara

        self.calibrar_inclinacion(
            inclinacion
        )

        baseline = (
            self.baseline_inclinacion
            if self.baseline_inclinacion
            is not None
            else inclinacion
        )

        desviacion = (
            inclinacion - baseline
        )

        cabeceo_detectado = False

        if (
            desviacion >
            self.UMBRAL_CABECEO
        ):
            if self.cabeceo_inicio is None:
                self.cabeceo_inicio = ahora
                self.cabeceo_en_curso = True
                self.cabeceo_confirmado = False

            duracion_cabeceo = (
                ahora - self.cabeceo_inicio
            )

            if (
                duracion_cabeceo >=
                self.TIEMPO_MINIMO_CABECEO
                and not self.cabeceo_confirmado
            ):
                self.cabeceo_confirmado = True
                self.contador_cabeceos += 1
                cabeceo_detectado = True

        else:
            self.cabeceo_inicio = None
            self.cabeceo_en_curso = False
            self.cabeceo_confirmado = False

        self.registrar_historial(
            rostro_detectado=True,
            ojos_cerrados=ojos_cerrados,
            bostezo=bostezo_detectado,
            cabeceo=cabeceo_detectado,
            ahora=ahora
        )

        perclos = self.calcular_perclos(
            ahora
        )

        bostezos_recientes = (
            self.contar_eventos_recientes(
                "bostezo"
            )
        )

        cabeceos_recientes = (
            self.contar_eventos_recientes(
                "cabeceo"
            )
        )

        fatiga = self.calcular_fatiga(
            perclos=perclos,
            tiempo_cerrado=tiempo_cerrado,
            bostezos_recientes=(
                bostezos_recientes
            ),
            cabeceos_recientes=(
                cabeceos_recientes
            )
        )

        estado = "NORMAL"
        mensaje = "Conductor en estado normal"
        nivel = "bajo"
        tipo_alerta = None

        if (
            ojos_cerrados
            and tiempo_cerrado >=
            TIEMPO_OJOS_CERRADOS
        ):
            estado = "OJOS_CERRADOS"
            mensaje = (
                f"Ojos cerrados durante "
                f"{tiempo_cerrado:.1f}s"
            )
            nivel = "alto"
            tipo_alerta = "ojos_cerrados"

        elif fatiga >= 75:
            estado = "SOMNOLENCIA"
            mensaje = (
                f"Fatiga alta detectada: "
                f"{fatiga}%"
            )
            nivel = "alto"
            tipo_alerta = "fatiga_alta"

        elif cabeceo_detectado:
            estado = "CABECEO"
            mensaje = (
                "Se detectó un posible "
                "cabeceo del conductor."
            )
            nivel = "alto"
            tipo_alerta = "cabeceo"

        elif fatiga >= 50:
            estado = "FATIGA_MODERADA"
            mensaje = (
                f"Fatiga moderada detectada: "
                f"{fatiga}%"
            )
            nivel = "medio"
            tipo_alerta = "fatiga_moderada"

        elif bostezo_detectado:
            estado = "BOSTEZO"
            mensaje = (
                "Se detectó un bostezo "
                "del conductor."
            )
            nivel = "medio"
            tipo_alerta = "bostezo"

        return {
            "estado": estado,
            "rostro_detectado": True,
            "ojos_cerrados": ojos_cerrados,
            "tiempo_ojos_cerrados": round(
                tiempo_cerrado,
                2
            ),
            "fatiga": fatiga,
            "bostezos": self.contador_bostezos,
            "parpadeos": self.contador_parpadeos,
            "cabeceos": self.contador_cabeceos,
            "mensaje": mensaje,
            "nivel": nivel,
            "tipo_alerta": tipo_alerta,
            "ear": round(ear, 4),
            "ear_umbral": round(
                self.ear_umbral_actual,
                4
            ),
            "mar": round(mar, 4),
            "perclos": round(perclos, 3)
        }

    def _respuesta_base(
        self,
        estado: str,
        mensaje: str,
        nivel: str,
        tipo_alerta,
        fatiga: int,
        perclos: float,
        tiempo_sin_rostro: float
    ) -> Dict[str, Any]:
        return {
            "estado": estado,
            "rostro_detectado": False,
            "ojos_cerrados": False,
            "tiempo_ojos_cerrados": 0.0,
            "fatiga": fatiga,
            "bostezos": self.contador_bostezos,
            "parpadeos": self.contador_parpadeos,
            "cabeceos": self.contador_cabeceos,
            "mensaje": mensaje,
            "nivel": nivel,
            "tipo_alerta": tipo_alerta,
            "ear": 0.0,
            "ear_umbral": round(
                self.ear_umbral_actual,
                4
            ),
            "mar": 0.0,
            "perclos": round(perclos, 3),
            "tiempo_sin_rostro": round(
                tiempo_sin_rostro,
                2
            )
        }

    def puede_enviar_alerta(self) -> bool:
        ahora = time.monotonic()

        if (
            ahora - self.ultimo_envio_alerta
            >= TIEMPO_ENTRE_ALERTAS
        ):
            self.ultimo_envio_alerta = ahora
            return True

        return False

    def cerrar(self):
        try:
            self.face_mesh.close()
        except Exception:
            pass

        self.historial.clear()