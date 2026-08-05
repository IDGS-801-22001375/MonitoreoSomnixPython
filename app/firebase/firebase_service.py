from datetime import datetime
import json
import firebase_admin
from firebase_admin import credentials, db
from app.config import FIREBASE_CREDENTIALS, FIREBASE_CREDENTIALS_JSON, FIREBASE_DATABASE_URL


class FirebaseService:
    def __init__(self):
        if not firebase_admin._apps:
            if FIREBASE_CREDENTIALS_JSON:
                cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
                cred = credentials.Certificate(cred_dict)
            else:
                cred = credentials.Certificate(FIREBASE_CREDENTIALS)

            firebase_admin.initialize_app(cred, {
                "databaseURL": FIREBASE_DATABASE_URL
            })

        self.root = db.reference("somnix")

    def obtener_ruta_activa(self):
        rutas = self.root.child("rutas").get()

        if not rutas:
            raise Exception("No hay rutas registradas en Firebase")

        for ruta_id, ruta in rutas.items():
            estado = ruta.get("Estado", "").lower()

            if estado in ["activa", "pendiente"]:
                return {
                    "RutaId": ruta_id,
                    "UsuarioId": ruta.get("UsuarioId"),
                    "Nombre": ruta.get("Nombre"),
                    "Estado": ruta.get("Estado")
                }

        raise Exception("No hay ruta activa o pendiente")

    def crear_monitoreo(
        self,
        usuario_id,
        ruta_id,
        ojos_cerrados,
        fatiga,
        bostezos,
        estado_camara,
        parpadeos=0,
        cabeceos=0,
        perclos=0.0,
        ear=0.0,
        mar=0.0,
        estado_detector="SIN_DATOS",
        rostro_detectado=True,
        tiempo_ojos_cerrados=0.0,
        procesamiento_ms=0.0,
        calidad_frame="sin_datos"
    ):
        """
        Guarda una muestra consolidada del monitoreo.

        Los primeros seis parámetros conservan compatibilidad con
        las llamadas anteriores del sistema.
        """

        ref = self.root.child(
            "monitoreoCamara"
        ).push()

        monitoreo_id = ref.key

        try:
            fatiga_segura = max(
                0,
                min(int(float(fatiga)), 100)
            )
        except (TypeError, ValueError):
            fatiga_segura = 0

        try:
            bostezos_seguros = max(
                int(float(bostezos)),
                0
            )
        except (TypeError, ValueError):
            bostezos_seguros = 0

        try:
            parpadeos_seguros = max(
                int(float(parpadeos)),
                0
            )
        except (TypeError, ValueError):
            parpadeos_seguros = 0

        try:
            cabeceos_seguros = max(
                int(float(cabeceos)),
                0
            )
        except (TypeError, ValueError):
            cabeceos_seguros = 0

        try:
            perclos_seguro = max(
                0.0,
                min(float(perclos), 1.0)
            )
        except (TypeError, ValueError):
            perclos_seguro = 0.0

        try:
            ear_seguro = max(
                float(ear),
                0.0
            )
        except (TypeError, ValueError):
            ear_seguro = 0.0

        try:
            mar_seguro = max(
                float(mar),
                0.0
            )
        except (TypeError, ValueError):
            mar_seguro = 0.0

        try:
            tiempo_cerrado_seguro = max(
                float(tiempo_ojos_cerrados),
                0.0
            )
        except (TypeError, ValueError):
            tiempo_cerrado_seguro = 0.0

        try:
            procesamiento_seguro = max(
                float(procesamiento_ms),
                0.0
            )
        except (TypeError, ValueError):
            procesamiento_seguro = 0.0

        data = {
            "Id": monitoreo_id,
            "UsuarioId": str(
                usuario_id or ""
            ).strip(),
            "RutaId": str(
                ruta_id or ""
            ).strip(),

            "OjosCerrados": bool(
                ojos_cerrados
            ),
            "RostroDetectado": bool(
                rostro_detectado
            ),

            "FatigaDetectada": fatiga_segura,

            """
            * Estos contadores son acumulados durante el viaje.
            * StatisticsService se ajustará posteriormente para usar
            * el máximo, no sumar cada muestra acumulada.
            """
            
            "BostezosDetectados": (
                bostezos_seguros
            ),
            "BostezosTotales": (
                bostezos_seguros
            ),
            "ParpadeosTotales": (
                parpadeos_seguros
            ),
            "CabeceosTotales": (
                cabeceos_seguros
            ),

            "TiempoOjosCerrados": round(
                tiempo_cerrado_seguro,
                2
            ),
            "PERCLOS": round(
                perclos_seguro,
                4
            ),
            "EAR": round(
                ear_seguro,
                4
            ),
            "MAR": round(
                mar_seguro,
                4
            ),

            "EstadoDetector": str(
                estado_detector or "SIN_DATOS"
            ).strip(),

            "EstadoCamara": str(
                estado_camara or "desconocida"
            ).strip(),

            "ProcesamientoMs": round(
                procesamiento_seguro,
                1
            ),

            "CalidadFrame": str(
                calidad_frame or "sin_datos"
            ).strip(),

            "FechaRegistro": (
                datetime.now().isoformat()
            )
        }

        ref.set(data)

        print(
            "Monitoreo consolidado guardado:",
            monitoreo_id
        )

        return data

    def crear_alerta(self, usuario_id, ruta_id, tipo, mensaje, nivel):
        ref = self.root.child("alertas").push()
        alerta_id = ref.key

        data = {
            "Id": alerta_id,
            "UsuarioId": usuario_id,
            "RutaId": ruta_id,
            "Tipo": tipo,
            "Mensaje": mensaje,
            "Nivel": nivel,
            "Atendida": False,
            "FechaRegistro": datetime.now().isoformat()
        }

        ref.set(data)
        print("Alerta guardada:", data)

    def crear_notificacion(self, usuario_id, titulo, mensaje, tipo):
        ref = self.root.child("notificaciones").push()
        notificacion_id = ref.key

        data = {
            "Id": notificacion_id,
            "UsuarioId": usuario_id,
            "Titulo": titulo,
            "Mensaje": mensaje,
            "Tipo": tipo,
            "Leida": False,
            "FechaEnvio": datetime.now().isoformat()
        }

        ref.set(data)
        print("Notificación guardada:", data)

    def apagar_ultima_alerta(self, usuario_id, ruta_id):
        alertas = self.root.child("alertas").get()

        if not alertas:
            return {
                "ok": False,
                "mensaje": "No hay alertas registradas"
            }

        ultima_alerta_id = None
        ultima_fecha = ""

        for alerta_id, alerta in alertas.items():
            if (
                alerta.get("UsuarioId") == usuario_id
                and alerta.get("RutaId") == ruta_id
                and alerta.get("Atendida") == False
            ):
                fecha = alerta.get("FechaRegistro", "")

                if fecha > ultima_fecha:
                    ultima_fecha = fecha
                    ultima_alerta_id = alerta_id

        if not ultima_alerta_id:
            return {
                "ok": False,
                "mensaje": "No hay alertas pendientes"
            }

        self.root.child("alertas").child(ultima_alerta_id).update({
            "Atendida": True
        })

        return {
            "ok": True,
            "mensaje": "Alarma apagada correctamente",
            "alertaId": ultima_alerta_id
        }

    def registrar_necesidad_conductor(self, usuario_id, ruta_id, tipo, mensaje):
        ref = self.root.child("respuestasConductor").push()
        respuesta_id = ref.key

        data = {
            "Id": respuesta_id,
            "UsuarioId": usuario_id,
            "RutaId": ruta_id,
            "Tipo": tipo,
            "Mensaje": mensaje,
            "Atendida": False,
            "FechaRegistro": datetime.now().isoformat()
        }

        ref.set(data)

        self.crear_alerta(
            usuario_id,
            ruta_id,
            tipo,
            mensaje,
            "medio"
        )

        self.crear_notificacion(
            usuario_id,
            "Necesidad del conductor",
            mensaje,
            "necesidad"
        )

        return {
            "ok": True,
            "mensaje": "Necesidad registrada correctamente",
            "data": data
        }

    def terminar_ruta(self, ruta_id):
        self.root.child("rutas").child(ruta_id).update({
            "Estado": "terminada",
            "FechaTerminada": datetime.now().isoformat()
        })

        return {
            "ok": True,
            "mensaje": "Ruta marcada como terminada"
        }
    
    def obtener_rutas_por_usuario(self, usuario_id):
        return self.filtrar_por_usuario(
            "rutas",
            usuario_id
        )

    def obtener_viajes_por_usuario(self, usuario_id):
        return self.filtrar_por_usuario(
            "viajes",
            usuario_id
        )

    def obtener_alertas_por_usuario(self, usuario_id):
        return self.filtrar_por_usuario(
            "alertas",
            usuario_id
        )

    def obtener_monitoreo_por_usuario(self, usuario_id):
        return self.filtrar_por_usuario(
            "monitoreoCamara",
            usuario_id
        )

    def obtener_respuestas_por_usuario(self, usuario_id):
        return self.filtrar_por_usuario(
            "respuestasConductor",
            usuario_id
        )

    def obtener_estadisticas_viaje_por_usuario(self, usuario_id):
        return self.filtrar_por_usuario(
            "estadisticasViaje",
            usuario_id
        )

    def filtrar_por_usuario(self, nodo: str, usuario_id: str):
        datos = self.root.child(nodo).get() or {}

        if not isinstance(datos, dict):
            print(f"El nodo {nodo} no es un diccionario")
            return []

        usuario_id = str(usuario_id).strip()
        registros = []

        for registro_id, registro in datos.items():

            # Ignora registros vacíos, textos y datos dañados
            if not isinstance(registro, dict):
                print(
                    f"Registro ignorado en {nodo}/{registro_id}: "
                    f"tipo={type(registro).__name__}, valor={registro}"
                )
                continue

            registro_usuario_id = str(
                registro.get("UsuarioId", "")
            ).strip()

            if registro_usuario_id == usuario_id:
                registros.append(registro)

        return registros