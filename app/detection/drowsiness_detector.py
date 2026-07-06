# app/detection/drowsiness_detector.py
import time
import mediapipe as mp
from app.config import TIEMPO_OJOS_CERRADOS, TIEMPO_ENTRE_ALERTAS
from app.utils.math_utils import distancia

class DrowsinessDetector:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        # --- Ojos (EAR) ---
        self.ojo_izquierdo = [159, 158, 145, 153, 33, 133]
        self.ojo_derecho = [386, 385, 374, 380, 362, 263]
        self.EAR_UMBRAL = 0.20
        self.ojos_cerrados_inicio = None

        # --- Boca (MAR - Mouth Aspect Ratio) para bostezos ---
        # 13/14 = labio sup/inf interior, 78/308 = comisuras
        self.boca_puntos = [13, 14, 78, 308]
        self.MAR_UMBRAL = 0.55
        self.bostezo_en_curso = False
        self.contador_bostezos = 0

        # --- Parpadeos ---
        self.ojo_estaba_cerrado = False
        self.contador_parpadeos = 0

        # --- Cabeceo (usando ángulo de inclinación relativo, no solo Y) ---
        self.frente = 10   # punto superior de la frente
        self.barbilla = 152
        self.nariz = 1
        self.baseline_inclinacion = None  # se calibra en los primeros frames
        self.frames_calibracion = 0
        self.contador_cabeceos = 0
        self.cabeceo_en_curso = False

        self.ultimo_envio_alerta = 0

    def calcular_ear(self, puntos, indices):
        sup1, sup2, inf1, inf2, izq, der = indices
        vertical1 = distancia(puntos[sup1], puntos[inf1])
        vertical2 = distancia(puntos[sup2], puntos[inf2])
        horizontal = distancia(puntos[izq], puntos[der])
        return (vertical1 + vertical2) / (2.0 * horizontal)

    def calcular_mar(self, puntos):
        sup, inf, izq, der = self.boca_puntos
        vertical = distancia(puntos[sup], puntos[inf])
        horizontal = distancia(puntos[izq], puntos[der])
        return vertical / horizontal

    def analizar(self, frame_rgb):
        resultado = self.face_mesh.process(frame_rgb)

        if not resultado.multi_face_landmarks:
            return self._respuesta_base(
                estado="SIN_ROSTRO",
                mensaje="No se detecta rostro del conductor",
                nivel="medio",
                tipo_alerta="sin_rostro"
            )

        puntos = resultado.multi_face_landmarks[0].landmark

        # ---------- EAR (ojos) ----------
        ear_izq = self.calcular_ear(puntos, self.ojo_izquierdo)
        ear_der = self.calcular_ear(puntos, self.ojo_derecho)
        ear = (ear_izq + ear_der) / 2

        ojos_cerrados = ear < self.EAR_UMBRAL

        # Contador de parpadeos (transición cerrado -> abierto)
        if ojos_cerrados and not self.ojo_estaba_cerrado:
            self.ojos_cerrados_inicio = time.time()
        if not ojos_cerrados and self.ojo_estaba_cerrado:
            # si el cierre fue corto, fue un parpadeo normal
            duracion = time.time() - (self.ojos_cerrados_inicio or time.time())
            if duracion < TIEMPO_OJOS_CERRADOS:
                self.contador_parpadeos += 1
        self.ojo_estaba_cerrado = ojos_cerrados

        estado = "NORMAL"
        mensaje = "Conductor en estado normal"
        nivel = "bajo"
        tipo_alerta = None
        fatiga = 0

        if ojos_cerrados:
            tiempo_cerrado = time.time() - (self.ojos_cerrados_inicio or time.time())
            if tiempo_cerrado >= TIEMPO_OJOS_CERRADOS:
                estado = "SOMNOLENCIA"
                fatiga = 80
                mensaje = f"Ojos cerrados por {tiempo_cerrado:.1f}s"
                nivel = "alto"
                tipo_alerta = "ojos_cerrados"
        else:
            self.ojos_cerrados_inicio = None

        # ---------- MAR (bostezos) ----------
        mar = self.calcular_mar(puntos)
        boca_abierta = mar > self.MAR_UMBRAL

        if boca_abierta and not self.bostezo_en_curso:
            self.bostezo_en_curso = True
            self.contador_bostezos += 1
            if tipo_alerta is None:  # no pisar una alerta más grave
                estado = "BOSTEZO"
                mensaje = "Se detectó un bostezo del conductor."
                nivel = "medio"
                tipo_alerta = "bostezo"
        elif not boca_abierta:
            self.bostezo_en_curso = False

        # ---------- Cabeceo (inclinación relativa a la altura de la cara) ----------
        alto_cara = distancia(puntos[self.frente], puntos[self.barbilla])
        inclinacion = (puntos[self.barbilla].y - puntos[self.nariz].y) / alto_cara

        # Calibración: promedia los primeros 30 frames como "postura normal"
        if self.frames_calibracion < 30:
            if self.baseline_inclinacion is None:
                self.baseline_inclinacion = inclinacion
            else:
                self.baseline_inclinacion = (
                    self.baseline_inclinacion * self.frames_calibracion + inclinacion
                ) / (self.frames_calibracion + 1)
            self.frames_calibracion += 1

        desviacion = inclinacion - (self.baseline_inclinacion or inclinacion)

        if desviacion > 0.18:  # cabeza cayó notablemente respecto a su postura normal
            if not self.cabeceo_en_curso:
                self.cabeceo_en_curso = True
                self.contador_cabeceos += 1
            estado = "CABECEO"
            fatiga = 90
            mensaje = "Se detectó posible cabeceo del conductor."
            nivel = "alto"
            tipo_alerta = "cabeceo"
        else:
            self.cabeceo_en_curso = False

        return {
            "estado": estado,
            "ojos_cerrados": ojos_cerrados,
            "fatiga": fatiga,
            "bostezos": self.contador_bostezos,
            "parpadeos": self.contador_parpadeos,
            "cabeceos": self.contador_cabeceos,
            "mensaje": mensaje,
            "nivel": nivel,
            "tipo_alerta": tipo_alerta,
            "ear": ear,
            "mar": mar
        }

    def _respuesta_base(self, estado, mensaje, nivel, tipo_alerta):
        return {
            "estado": estado,
            "ojos_cerrados": False,
            "fatiga": 0,
            "bostezos": self.contador_bostezos,
            "parpadeos": self.contador_parpadeos,
            "cabeceos": self.contador_cabeceos,
            "mensaje": mensaje,
            "nivel": nivel,
            "tipo_alerta": tipo_alerta,
            "ear": 0,
            "mar": 0
        }

    def puede_enviar_alerta(self):
        ahora = time.time()
        if ahora - self.ultimo_envio_alerta >= TIEMPO_ENTRE_ALERTAS:
            self.ultimo_envio_alerta = ahora
            return True
        return False