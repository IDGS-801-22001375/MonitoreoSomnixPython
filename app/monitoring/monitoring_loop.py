import cv2

from app.camera.camera_service import CameraService
from app.detection.drowsiness_detector import DrowsinessDetector


class MonitoringLoop:
    def __init__(self, firebase_service, state):
        self.firebase = firebase_service
        self.state = state
        self.camera = None
        self.detector = None

    def ejecutar(self):
        self.camera = CameraService()
        self.detector = DrowsinessDetector()

        self.firebase.crear_notificacion(
            self.state.usuario_id,
            "Monitoreo iniciado",
            f"El monitoreo de la ruta {self.state.nombre_ruta or self.state.ruta_id} ha comenzado.",
            "monitoreo"
        )

        while self.state.activo:
            ret, frame = self.camera.leer_frame()

            if not ret:
                self.firebase.crear_monitoreo(
                    self.state.usuario_id,
                    self.state.ruta_id,
                    False,
                    0,
                    0,
                    "inactiva"
                )

                self.firebase.crear_alerta(
                    self.state.usuario_id,
                    self.state.ruta_id,
                    "camara_inactiva",
                    "La cámara se encuentra inactiva durante la ruta.",
                    "medio"
                )

                self.state.detener()
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultado = self.detector.analizar(frame_rgb)

            self.firebase.crear_monitoreo(
                self.state.usuario_id,
                self.state.ruta_id,
                resultado["ojos_cerrados"],
                resultado["fatiga"],
                resultado["bostezos"],
                "activa"
            )

            if resultado["tipo_alerta"] is not None:
                if self.detector.puede_enviar_alerta():
                    self.firebase.crear_alerta(
                        self.state.usuario_id,
                        self.state.ruta_id,
                        resultado["tipo_alerta"],
                        resultado["mensaje"],
                        resultado["nivel"]
                    )

                    self.firebase.crear_notificacion(
                        self.state.usuario_id,
                        "Alerta de fatiga",
                        resultado["mensaje"],
                        "alerta"
                    )

        self.finalizar()

    def finalizar(self):
        if self.camera:
            self.camera.liberar()

        self.firebase.crear_notificacion(
            self.state.usuario_id,
            "Monitoreo finalizado",
            "El monitoreo de la ruta ha finalizado.",
            "monitoreo"
        )

        self.state.limpiar()