from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    UploadFile
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.analytics.statistics_service import StatisticsService
from app.detection.detector_registry import DetectorRegistry
from app.firebase.firebase_service import FirebaseService
from app.services.alert_management_service import AlertManagementService
from app.services.frame_analysis_service import (
    FrameAnalysisError,
    FrameAnalysisService
)
from app.services.monitoring_persistence_service import (
    MonitoringPersistenceService
)
from app.services.monitoring_service import MonitoringService


# ============================================================
# SERVICIOS GLOBALES
# ============================================================

firebase_service = FirebaseService()
monitoring_service = MonitoringService()

detector_registry = DetectorRegistry()

frame_analysis_service = FrameAnalysisService(
    detector_registry=detector_registry
)

monitoring_persistence_service = MonitoringPersistenceService(
    firebase_service=firebase_service
)

alert_management_service = AlertManagementService(
    firebase_service=firebase_service
)

statistics_service = StatisticsService(
    firebase_service
)


# ============================================================
# FUNCIONES SEGURAS PARA TAREAS EN SEGUNDO PLANO
# ============================================================

def crear_notificacion_segura(
    usuario_id: str,
    titulo: str,
    mensaje: str,
    tipo: str
):
    try:
        firebase_service.crear_notificacion(
            usuario_id,
            titulo,
            mensaje,
            tipo
        )
    except Exception as error:
        print(
            "ERROR CREANDO NOTIFICACIÓN:",
            repr(error)
        )


def terminar_ruta_segura(
    usuario_id: str,
    ruta_id: str
):
    try:
        firebase_service.terminar_ruta(
            ruta_id=ruta_id
        )

        firebase_service.crear_notificacion(
            usuario_id,
            "Ruta terminada",
            (
                "La ruta se marcó como terminada "
                "correctamente."
            ),
            "ruta"
        )
    except Exception as error:
        print(
            "ERROR TERMINANDO RUTA EN FIREBASE:",
            repr(error)
        )


def apagar_alerta_firebase_segura(
    usuario_id: str,
    ruta_id: str
):
    try:
        firebase_service.apagar_ultima_alerta(
            usuario_id=usuario_id,
            ruta_id=ruta_id
        )
    except Exception as error:
        print(
            "ERROR APAGANDO ALERTA EN FIREBASE:",
            repr(error)
        )


# ============================================================
# CICLO DE VIDA DE FASTAPI
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("SOMNIX API iniciada")

    yield

    print("Cerrando servicios de SOMNIX")

    try:
        monitoring_service.cerrar()
    except Exception as error:
        print(
            "ERROR CERRANDO MONITOREO:",
            repr(error)
        )

    try:
        frame_analysis_service.cerrar()
    except Exception as error:
        print(
            "ERROR CERRANDO DETECTORES:",
            repr(error)
        )


app = FastAPI(
    title="SOMNIX API Python",
    lifespan=lifespan
)


# ============================================================
# MODELOS DE SOLICITUD
# ============================================================

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


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================

@app.get("/")
def home():
    return {
        "ok": True,
        "mensaje": "Servidor SOMNIX Python activo",
        "arquitectura": {
            "camara": "Android CameraX",
            "analisis": "MediaPipe por sesión",
            "bluetooth": "Android BLE",
            "persistencia": "Firebase controlada"
        }
    }


# ============================================================
# CONTROL DEL VIAJE
# ============================================================

@app.post("/api/viaje/iniciar")
def iniciar_viaje(
    request: IniciarViajeRequest,
    background_tasks: BackgroundTasks
):
    usuario_id = request.usuarioId.strip()
    ruta_id = request.rutaId.strip()

    if not usuario_id or not ruta_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "El usuarioId y el rutaId "
                "son obligatorios."
            )
        )

    resultado = monitoring_service.iniciar(
        usuario_id=usuario_id,
        ruta_id=ruta_id,
        nombre_ruta=request.nombreRuta
    )

    if resultado.get("ok", False):
        reutilizado = resultado.get(
            "reutilizado",
            False
        )

        if not reutilizado:
            # Elimina cualquier estado anterior de esa sesión.
            frame_analysis_service.eliminar_detector(
                usuario_id,
                ruta_id
            )

            monitoring_persistence_service.descartar_sesion(
                usuario_id,
                ruta_id
            )

            alert_management_service.limpiar_sesion(
                usuario_id,
                ruta_id
            )

            background_tasks.add_task(
                crear_notificacion_segura,
                usuario_id,
                "Monitoreo iniciado",
                (
                    "El monitoreo de la ruta "
                    f"{request.nombreRuta or ruta_id} "
                    "ha comenzado."
                ),
                "monitoreo"
            )

    return resultado


@app.post("/api/viaje/pausar")
def pausar_viaje(
    background_tasks: BackgroundTasks
):
    estado_anterior = monitoring_service.estado()

    resultado = monitoring_service.pausar()

    if resultado.get("ok", False):
        usuario_id = estado_anterior.get(
            "usuarioId"
        )

        if usuario_id:
            background_tasks.add_task(
                crear_notificacion_segura,
                usuario_id,
                "Viaje pausado",
                (
                    "El monitoreo del viaje "
                    "se encuentra pausado."
                ),
                "monitoreo"
            )

    return resultado


@app.post("/api/viaje/reanudar")
def reanudar_viaje(
    background_tasks: BackgroundTasks
):
    resultado = monitoring_service.reanudar()

    if resultado.get("ok", False):
        estado_actual = monitoring_service.estado()

        usuario_id = estado_actual.get(
            "usuarioId"
        )

        if usuario_id:
            background_tasks.add_task(
                crear_notificacion_segura,
                usuario_id,
                "Viaje reanudado",
                (
                    "El monitoreo del viaje "
                    "se encuentra activo nuevamente."
                ),
                "monitoreo"
            )

    return resultado


@app.post("/api/viaje/terminar")
async def terminar_viaje(
    request: TerminarViajeRequest,
    background_tasks: BackgroundTasks
):
    usuario_id = request.usuarioId.strip()
    ruta_id = request.rutaId.strip()

    resultado = monitoring_service.detener()

    # Guarda el último resultado pendiente antes de limpiar.
    resultado_persistencia = await run_in_threadpool(
        monitoring_persistence_service.finalizar_sesion,
        usuario_id,
        ruta_id
    )

    # Cierra MediaPipe y elimina el estado de esa sesión.
    await run_in_threadpool(
        frame_analysis_service.eliminar_detector,
        usuario_id,
        ruta_id
    )

    alert_management_service.limpiar_sesion(
        usuario_id,
        ruta_id
    )

    background_tasks.add_task(
        terminar_ruta_segura,
        usuario_id,
        ruta_id
    )

    resultado["persistenciaFinal"] = (
        resultado_persistencia
    )

    return resultado


@app.get("/api/monitoreo/estado")
def estado_monitoreo():
    return monitoring_service.estado()


# ============================================================
# APAGAR ALARMA
# ============================================================

@app.post("/api/alarma/apagar")
def apagar_alarma(
    request: ApagarAlarmaRequest,
    background_tasks: BackgroundTasks
):
    resultado_gorra = (
        monitoring_service.apagar_alarma()
    )

    # Firebase no bloquea la respuesta del botón.
    background_tasks.add_task(
        apagar_alerta_firebase_segura,
        request.usuarioId,
        request.rutaId
    )

    return {
        "ok": True,
        "mensaje": (
            "La solicitud para apagar la alarma "
            "fue procesada."
        ),
        "gorra": resultado_gorra
    }


# ============================================================
# NECESIDADES DEL CONDUCTOR
# ============================================================

@app.post("/api/conductor/necesidad")
async def registrar_necesidad(
    request: NecesidadConductorRequest
):
    try:
        return await run_in_threadpool(
            firebase_service.registrar_necesidad_conductor,
            request.usuarioId,
            request.rutaId,
            request.tipo,
            request.mensaje
        )
    except Exception as error:
        print(
            "ERROR REGISTRANDO NECESIDAD:",
            repr(error)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "No fue posible registrar "
                "la necesidad del conductor."
            )
        )


# ============================================================
# ANÁLISIS DE FRAMES
# ============================================================

@app.post("/api/monitoreo/frame")
async def analizar_frame(
    usuarioId: str,
    rutaId: str,
    file: UploadFile = File(...)
):
    usuario_id = usuarioId.strip()
    ruta_id = rutaId.strip()

    permitido, mensaje_validacion = (
        monitoring_service.validar_frame(
            usuario_id,
            ruta_id
        )
    )

    if not permitido:
        return {
            "ok": False,
            "ignorado": True,
            "mensaje": mensaje_validacion
        }

    tipos_permitidos = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "application/octet-stream"
    }

    if (
        file.content_type
        and file.content_type not in tipos_permitidos
    ):
        raise HTTPException(
            status_code=415,
            detail=(
                "El archivo recibido no es "
                "una imagen compatible."
            )
        )

    try:
        # Se lee un byte adicional para detectar archivos
        # mayores al límite de 5 MB.
        contenido = await file.read(
            (5 * 1024 * 1024) + 1
        )

        resultado = await run_in_threadpool(
            frame_analysis_service.analizar,
            usuario_id,
            ruta_id,
            contenido
        )

        # El viaje pudo pausarse mientras MediaPipe
        # estaba procesando la imagen.
        permitido, mensaje_validacion = (
            monitoring_service.validar_frame(
                usuario_id,
                ruta_id
            )
        )

        if not permitido:
            return {
                "ok": False,
                "ignorado": True,
                "mensaje": mensaje_validacion
            }

        monitoring_service.registrar_frame()

        resultado_persistencia = (
            await run_in_threadpool(
                monitoring_persistence_service
                .procesar_resultado,
                usuario_id,
                ruta_id,
                resultado
            )
        )

        resultado_alertas = (
            await run_in_threadpool(
                alert_management_service
                .procesar_resultado,
                usuario_id,
                ruta_id,
                resultado
            )
        )

        return {
            "ok": True,
            "estado": resultado.get(
                "estado",
                "NORMAL"
            ),
            "fatiga": int(
                resultado.get("fatiga", 0)
            ),
            "ojosCerrados": bool(
                resultado.get(
                    "ojos_cerrados",
                    False
                )
            ),
            "bostezos": int(
                resultado.get("bostezos", 0)
            ),
            "parpadeos": int(
                resultado.get("parpadeos", 0)
            ),
            "cabeceos": int(
                resultado.get("cabeceos", 0)
            ),
            "tipoAlerta": resultado.get(
                "tipo_alerta"
            ),
            "mensaje": resultado.get(
                "mensaje",
                "Frame analizado correctamente"
            ),
            "nivel": resultado.get(
                "nivel",
                "bajo"
            ),
            "ear": resultado.get("ear", 0),
            "mar": resultado.get("mar", 0),
            "perclos": resultado.get(
                "perclos",
                0
            ),
            "rostroDetectado": resultado.get(
                "rostro_detectado",
                True
            ),
            "tiempoOjosCerrados": resultado.get(
                "tiempo_ojos_cerrados",
                0
            ),
            "calidad": resultado.get(
                "calidad",
                {}
            ),
            "procesamientoMs": resultado.get(
                "procesamiento_ms",
                0
            ),
            "persistencia": resultado_persistencia,
            "alertas": resultado_alertas
        }

    except FrameAnalysisError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except HTTPException:
        raise

    except Exception as error:
        print(
            "ERROR ANALIZANDO FRAME:",
            repr(error)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Ocurrió un error procesando "
                "el frame de la cámara."
            )
        )

    finally:
        await file.close()


# ============================================================
# ESTADÍSTICAS
# ============================================================

@app.get(
    "/api/estadisticas/usuario/{usuario_id}"
)
async def obtener_estadisticas_usuario(
    usuario_id: str
):
    try:
        return await run_in_threadpool(
            statistics_service
            .obtener_estadisticas_usuario,
            usuario_id
        )
    except Exception as error:
        print(
            "ERROR ESTADÍSTICAS:",
            repr(error)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Error al generar estadísticas: "
                f"{str(error)}"
            )
        )