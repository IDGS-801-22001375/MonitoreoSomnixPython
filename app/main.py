import cv2
from app.firebase.firebase_service import FirebaseService
from app.camera.camera_service import CameraService
from app.detection.drowsiness_detector import DrowsinessDetector


def main():
    firebase = FirebaseService()

    ruta = firebase.obtener_ruta_activa()

    usuario_id = ruta["UsuarioId"]
    ruta_id = ruta["RutaId"]

    print("Ruta seleccionada:", ruta)

    camera = CameraService()
    detector = DrowsinessDetector()

    firebase.crear_notificacion(
        usuario_id,
        "Monitoreo iniciado",
        f"El monitoreo de la ruta {ruta.get('Nombre')} ha comenzado.",
        "monitoreo"
    )

    while True:
        ret, frame = camera.leer_frame()

        if not ret:
            firebase.crear_monitoreo(
                usuario_id,
                ruta_id,
                False,
                0,
                0,
                "inactiva"
            )

            firebase.crear_alerta(
                usuario_id,
                ruta_id,
                "camara_inactiva",
                "La cámara se encuentra inactiva durante la ruta.",
                "medio"
            )

            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado = detector.analizar(frame_rgb)

        firebase.crear_monitoreo(
            usuario_id,
            ruta_id,
            resultado["ojos_cerrados"],
            resultado["fatiga"],
            resultado["bostezos"],
            "activa"
        )

        if resultado["tipo_alerta"] is not None:
            if detector.puede_enviar_alerta():
                firebase.crear_alerta(
                    usuario_id,
                    ruta_id,
                    resultado["tipo_alerta"],
                    resultado["mensaje"],
                    resultado["nivel"]
                )

                firebase.crear_notificacion(
                    usuario_id,
                    "Alerta de fatiga",
                    resultado["mensaje"],
                    "alerta"
                )

        cv2.putText(
            frame,
            f"EAR: {resultado['ear']:.2f}",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Estado: {resultado['estado']}",
            (30, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255),
            2
        )

        cv2.imshow("SOMNIX - Monitoreo IA", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.liberar()

    firebase.crear_notificacion(
        usuario_id,
        "Monitoreo finalizado",
        "El monitoreo de la ruta ha finalizado.",
        "monitoreo"
    )


if __name__ == "__main__":
    main()