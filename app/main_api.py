from datetime import datetime, timedelta

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from app.firebase.firebase_service import FirebaseService
from app.services.monitoring_service import MonitoringService
from app.detection.drowsiness_detector import DrowsinessDetector


app = FastAPI(title="SOMNIX API Python")

monitoring_service = MonitoringService()
firebase_service = FirebaseService()
detector = DrowsinessDetector()

ultima_notificacion_fatiga = {}


class IniciarViajeRequest(BaseModel):
    usuarioId: str
    rutaId: str
    nombreRuta: str | None = None


class ApagarAlarmaRequest(BaseModel):
    usuarioId: str
    rutaId: str


class NecesidadConductorRequest(BaseModel):
    usuarioId: str
    rutaId: str
    tipo: str
    mensaje: str

class TerminarViajeRequest(BaseModel):
    usuarioId: str
    rutaId: str


def puede_notificar_fatiga(usuario_id: str, nivel_fatiga: str):
    ahora = datetime.now()
    clave = f"{usuario_id}_{nivel_fatiga}"

    if clave not in ultima_notificacion_fatiga:
        ultima_notificacion_fatiga[clave] = ahora
        return True

    diferencia = ahora - ultima_notificacion_fatiga[clave]

    if diferencia >= timedelta(minutes=3):
        ultima_notificacion_fatiga[clave] = ahora
        return True

    return False


@app.get("/")
def home():
    return {
        "mensaje": "Servidor SOMNIX Python activo"
    }


@app.post("/api/viaje/iniciar")
def iniciar_viaje(request: IniciarViajeRequest):
    return monitoring_service.iniciar(
        usuario_id=request.usuarioId,
        ruta_id=request.rutaId,
        nombre_ruta=request.nombreRuta
    )


@app.post("/api/viaje/pausar")
def pausar_viaje():
    return monitoring_service.pausar()


@app.post("/api/viaje/terminar")
def terminar_viaje(request: TerminarViajeRequest):
    resultado = monitoring_service.detener()

    firebase_service.terminar_ruta(
        ruta_id=request.rutaId
    )

    firebase_service.crear_notificacion(
        request.usuarioId,
        "Ruta terminada",
        "La ruta se marcó como terminada correctamente.",
        "ruta"
    )

    return resultado


@app.get("/api/monitoreo/estado")
def estado_monitoreo():
    return monitoring_service.estado()


@app.post("/api/alarma/apagar")
def apagar_alarma(request: ApagarAlarmaRequest):
    return firebase_service.apagar_ultima_alerta(
        usuario_id=request.usuarioId,
        ruta_id=request.rutaId
    )


@app.post("/api/conductor/necesidad")
def registrar_necesidad(request: NecesidadConductorRequest):
    return firebase_service.registrar_necesidad_conductor(
        usuario_id=request.usuarioId,
        ruta_id=request.rutaId,
        tipo=request.tipo,
        mensaje=request.mensaje
    )


@app.post("/api/monitoreo/frame")
async def analizar_frame(
    usuarioId: str,
    rutaId: str,
    file: UploadFile = File(...)
):
    contenido = await file.read()

    np_array = np.frombuffer(contenido, np.uint8)
    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    if frame is None:
        return {
            "ok": False,
            "mensaje": "No se pudo leer la imagen"
        }

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    resultado = detector.analizar(frame_rgb)

    fatiga = resultado["fatiga"]

    firebase_service.crear_monitoreo(
        usuarioId,
        rutaId,
        resultado["ojos_cerrados"],
        fatiga,
        resultado["bostezos"],
        "activa"
    )

    if fatiga >= 50:
        if puede_notificar_fatiga(usuarioId, "fatiga_50"):
            firebase_service.crear_alerta(
                usuarioId,
                rutaId,
                "fatiga_alta",
                f"Fatiga elevada detectada: {fatiga}%. Se recomienda detener el viaje.",
                "alto"
            )

            firebase_service.crear_notificacion(
                usuarioId,
                "Fatiga alta detectada",
                "Tu nivel de fatiga es alto. ¿Deseas pausar el viaje o descansar?",
                "fatiga_alta"
            )

    elif fatiga >= 30:
        if puede_notificar_fatiga(usuarioId, "fatiga_30"):
            firebase_service.crear_notificacion(
                usuarioId,
                "Fatiga moderada",
                "Tu fatiga está aumentando. ¿Deseas descansar o pausar el viaje?",
                "fatiga_moderada"
            )

    elif fatiga >= 20:
        if puede_notificar_fatiga(usuarioId, "fatiga_20"):
            firebase_service.crear_notificacion(
                usuarioId,
                "Atención",
                "Se detectan señales leves de cansancio. ¿Deseas tomar un descanso?",
                "fatiga_leve"
            )

    elif fatiga >= 10:
        if puede_notificar_fatiga(usuarioId, "fatiga_10"):
            firebase_service.crear_notificacion(
                usuarioId,
                "Recomendación",
                "Mantente alerta. Puedes pausar el viaje si te sientes cansado.",
                "recomendacion"
            )

    if resultado["tipo_alerta"] is not None:
        if detector.puede_enviar_alerta():
            firebase_service.crear_alerta(
                usuarioId,
                rutaId,
                resultado["tipo_alerta"],
                resultado["mensaje"],
                resultado["nivel"]
            )

            firebase_service.crear_notificacion(
                usuarioId,
                "Alerta de fatiga",
                resultado["mensaje"],
                "alerta"
            )

    return {
        "ok": True,
        "estado": resultado["estado"],
        "fatiga": fatiga,
        "ojosCerrados": resultado["ojos_cerrados"],
        "bostezos": resultado["bostezos"],
        "tipoAlerta": resultado["tipo_alerta"],
        "mensaje": resultado["mensaje"],
        "nivel": resultado["nivel"]
    }