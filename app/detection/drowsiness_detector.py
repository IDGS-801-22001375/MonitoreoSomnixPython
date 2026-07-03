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

        self.ojos_cerrados_inicio = None
        self.ultimo_envio_alerta = 0

        self.ojo_izquierdo = [159, 158, 145, 153, 33, 133]
        self.ojo_derecho = [386, 385, 374, 380, 362, 263]

    def calcular_ear(self, puntos, indices):
        sup1, sup2, inf1, inf2, izq, der = indices

        vertical1 = distancia(puntos[sup1], puntos[inf1])
        vertical2 = distancia(puntos[sup2], puntos[inf2])
        horizontal = distancia(puntos[izq], puntos[der])

        return (vertical1 + vertical2) / (2.0 * horizontal)

    def analizar(self, frame_rgb):
        resultado = self.face_mesh.process(frame_rgb)

        if not resultado.multi_face_landmarks:
            return {
                "estado": "SIN_ROSTRO",
                "ojos_cerrados": False,
                "fatiga": 0,
                "bostezos": 0,
                "mensaje": "No se detecta rostro del conductor",
                "nivel": "medio",
                "tipo_alerta": "sin_rostro",
                "ear": 0
            }

        rostro = resultado.multi_face_landmarks[0]
        puntos = rostro.landmark

        ear_izq = self.calcular_ear(puntos, self.ojo_izquierdo)
        ear_der = self.calcular_ear(puntos, self.ojo_derecho)
        ear = (ear_izq + ear_der) / 2

        nariz = puntos[1]
        barbilla = puntos[152]

        ojos_cerrados = False
        fatiga = 0
        estado = "NORMAL"
        mensaje = "Conductor en estado normal"
        nivel = "bajo"
        tipo_alerta = None

        if ear < 0.20:
            ojos_cerrados = True

            if self.ojos_cerrados_inicio is None:
                self.ojos_cerrados_inicio = time.time()

            tiempo_cerrado = time.time() - self.ojos_cerrados_inicio

            if tiempo_cerrado >= TIEMPO_OJOS_CERRADOS:
                estado = "SOMNOLENCIA"
                fatiga = 80
                mensaje = "El conductor mantuvo los ojos cerrados por varios segundos."
                nivel = "alto"
                tipo_alerta = "ojos_cerrados"
        else:
            self.ojos_cerrados_inicio = None

        inclinacion = barbilla.y - nariz.y

        if inclinacion > 0.38:
            estado = "CABEZAZO"
            fatiga = 90
            mensaje = "Se detectó posible cabeceo del conductor."
            nivel = "alto"
            tipo_alerta = "cabeceo"

        return {
            "estado": estado,
            "ojos_cerrados": ojos_cerrados,
            "fatiga": fatiga,
            "bostezos": 0,
            "mensaje": mensaje,
            "nivel": nivel,
            "tipo_alerta": tipo_alerta,
            "ear": ear
        }

    def puede_enviar_alerta(self):
        ahora = time.time()

        if ahora - self.ultimo_envio_alerta >= TIEMPO_ENTRE_ALERTAS:
            self.ultimo_envio_alerta = ahora
            return True

        return False