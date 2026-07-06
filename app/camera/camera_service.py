import cv2
from app.config import CAMERA_URL


class CameraService:
    def __init__(self):
        self.cap = cv2.VideoCapture(CAMERA_URL)
        if not self.cap.isOpened():
            raise Exception("No se pudo abrir la cámara")
    def leer_frame(self):
        return self.cap.read()
    def liberar(self):
        self.cap.release()
        cv2.destroyAllWindows()