import time
from collections import deque
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

        self.ojo_izquierdo = [159, 158, 145, 153, 33, 133]
        self.ojo_derecho = [386, 385, 374, 380, 362, 263]
        self.EAR_UMBRAL = 0.20

        self.boca_puntos = [13, 14, 78, 308]
        self.MAR_UMBRAL = 0.55
        self.bostezo_en_curso = False
        self.contador_bostezos = 0

        self.ojo_estaba_cerrado = False
        self.ojos_cerrados_inicio = None
        self.contador_parpadeos = 0

        self.frente = 10
        self.barbilla = 152
        self.nariz = 1
        self.baseline_inclinacion = None
        self.frames_calibracion = 0
        self.contador_cabeceos = 0
        self.cabeceo_en_curso = False

        self.ultimo_envio_alerta = 0

        # Historial para PERCLOS
        self.ventana_segundos = 60
        self.historial = deque()

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

    def registrar_historial(self, ojos_cerrados, bostezo, cabeceo):
        ahora = time.time()

        self.historial.append({
            "tiempo": ahora,
            "ojos_cerrados": ojos_cerrados,
            "bostezo": bostezo,
            "cabeceo": cabeceo
        })

        while self.historial and ahora - self.historial[0]["tiempo"] > self.ventana_segundos:
            self.historial.popleft()

    def calcular_perclos(self):
        if not self.historial:
            return 0

        total = len(self.historial)
        cerrados = sum(1 for item in self.historial if item["ojos_cerrados"])

        return cerrados / total

    def calcular_fatiga(self, perclos, tiempo_cerrado, bostezos_recientes, cabeceos_recientes):
        fatiga = 0

        # PERCLOS pesa más porque mide fatiga acumulada
        fatiga += perclos * 70

        # Ojos cerrados sostenidos
        if tiempo_cerrado >= 0.5:
            fatiga += 10
        if tiempo_cerrado >= 1.0:
            fatiga += 15
        if tiempo_cerrado >= 2.0:
            fatiga += 25
        if tiempo_cerrado >= TIEMPO_OJOS_CERRADOS:
            fatiga += 35

        # Bostezos recientes
        fatiga += min(bostezos_recientes * 8, 24)

        # Cabeceos recientes
        fatiga += min(cabeceos_recientes * 15, 30)

        return min(int(round(fatiga)), 100)

    def analizar(self, frame_rgb):
        resultado = self.face_mesh.process(frame_rgb)

        if not resultado.multi_face_landmarks:
            self.registrar_historial(False, False, False)

            return self._respuesta_base(
                estado="SIN_ROSTRO",
                mensaje="No se detecta rostro del conductor",
                nivel="medio",
                tipo_alerta="sin_rostro"
            )

        puntos = resultado.multi_face_landmarks[0].landmark

        ear_izq = self.calcular_ear(puntos, self.ojo_izquierdo)
        ear_der = self.calcular_ear(puntos, self.ojo_derecho)
        ear = (ear_izq + ear_der) / 2

        ojos_cerrados = ear < self.EAR_UMBRAL

        if ojos_cerrados and not self.ojo_estaba_cerrado:
            self.ojos_cerrados_inicio = time.time()

        if not ojos_cerrados and self.ojo_estaba_cerrado:
            duracion = time.time() - (self.ojos_cerrados_inicio or time.time())
            if duracion < TIEMPO_OJOS_CERRADOS:
                self.contador_parpadeos += 1

        self.ojo_estaba_cerrado = ojos_cerrados

        tiempo_cerrado = 0
        if ojos_cerrados:
            tiempo_cerrado = time.time() - (self.ojos_cerrados_inicio or time.time())
        else:
            self.ojos_cerrados_inicio = None

        mar = self.calcular_mar(puntos)
        boca_abierta = mar > self.MAR_UMBRAL
        bostezo_detectado = False

        if boca_abierta and not self.bostezo_en_curso:
            self.bostezo_en_curso = True
            self.contador_bostezos += 1
            bostezo_detectado = True
        elif not boca_abierta:
            self.bostezo_en_curso = False

        alto_cara = distancia(puntos[self.frente], puntos[self.barbilla])
        inclinacion = (puntos[self.barbilla].y - puntos[self.nariz].y) / alto_cara

        if self.frames_calibracion < 30:
            if self.baseline_inclinacion is None:
                self.baseline_inclinacion = inclinacion
            else:
                self.baseline_inclinacion = (
                    self.baseline_inclinacion * self.frames_calibracion + inclinacion
                ) / (self.frames_calibracion + 1)
            self.frames_calibracion += 1

        desviacion = inclinacion - (self.baseline_inclinacion or inclinacion)
        cabeceo_detectado = False

        if desviacion > 0.18:
            if not self.cabeceo_en_curso:
                self.cabeceo_en_curso = True
                self.contador_cabeceos += 1
                cabeceo_detectado = True
        else:
            self.cabeceo_en_curso = False

        self.registrar_historial(
            ojos_cerrados=ojos_cerrados,
            bostezo=bostezo_detectado,
            cabeceo=cabeceo_detectado
        )

        perclos = self.calcular_perclos()

        bostezos_recientes = sum(1 for item in self.historial if item["bostezo"])
        cabeceos_recientes = sum(1 for item in self.historial if item["cabeceo"])

        fatiga = self.calcular_fatiga(
            perclos=perclos,
            tiempo_cerrado=tiempo_cerrado,
            bostezos_recientes=bostezos_recientes,
            cabeceos_recientes=cabeceos_recientes
        )

        estado = "NORMAL"
        mensaje = "Conductor en estado normal"
        nivel = "bajo"
        tipo_alerta = None

        if fatiga >= 75:
            estado = "SOMNOLENCIA"
            mensaje = f"Fatiga alta detectada: {fatiga}%"
            nivel = "alto"
            tipo_alerta = "fatiga_alta"
        elif fatiga >= 50:
            estado = "FATIGA_MODERADA"
            mensaje = f"Fatiga moderada detectada: {fatiga}%"
            nivel = "medio"
            tipo_alerta = "fatiga_moderada"
        elif bostezo_detectado:
            estado = "BOSTEZO"
            mensaje = "Se detectó un bostezo del conductor."
            nivel = "medio"
            tipo_alerta = "bostezo"
        elif cabeceo_detectado:
            estado = "CABECEO"
            mensaje = "Se detectó posible cabeceo del conductor."
            nivel = "alto"
            tipo_alerta = "cabeceo"
        elif ojos_cerrados and tiempo_cerrado >= TIEMPO_OJOS_CERRADOS:
            estado = "OJOS_CERRADOS"
            mensaje = f"Ojos cerrados por {tiempo_cerrado:.1f}s"
            nivel = "alto"
            tipo_alerta = "ojos_cerrados"

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
            "mar": mar,
            "perclos": round(perclos, 2)
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
            "mar": 0,
            "perclos": 0
        }

    def puede_enviar_alerta(self):
        ahora = time.time()

        if ahora - self.ultimo_envio_alerta >= TIEMPO_ENTRE_ALERTAS:
            self.ultimo_envio_alerta = ahora
            return True

        return False