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

    def crear_monitoreo(self, usuario_id, ruta_id, ojos_cerrados, fatiga, bostezos, estado_camara):
        ref = self.root.child("monitoreoCamara").push()
        monitoreo_id = ref.key

        data = {
            "Id": monitoreo_id,
            "UsuarioId": usuario_id,
            "RutaId": ruta_id,
            "OjosCerrados": ojos_cerrados,
            "FatigaDetectada": fatiga,
            "BostezosDetectados": bostezos,
            "EstadoCamara": estado_camara,
            "FechaRegistro": datetime.now().isoformat()
        }

        ref.set(data)
        print("Monitoreo guardado:", data)

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
        rutas = self.root.child("rutas").get() or {}

        return [
            ruta for ruta in rutas.values()
            if ruta.get("UsuarioId") == usuario_id
        ]

    def obtener_viajes_por_usuario(self, usuario_id):
        viajes = self.root.child("viajes").get() or {}

        return [
            viaje for viaje in viajes.values()
            if viaje.get("UsuarioId") == usuario_id
        ]

    def obtener_alertas_por_usuario(self, usuario_id):
        alertas = self.root.child("alertas").get() or {}

        return [
            alerta for alerta in alertas.values()
            if alerta.get("UsuarioId") == usuario_id
        ]

    def obtener_monitoreo_por_usuario(self, usuario_id):
        monitoreos = self.root.child("monitoreoCamara").get() or {}

        return [
            monitoreo for monitoreo in monitoreos.values()
            if monitoreo.get("UsuarioId") == usuario_id
        ]

    def obtener_respuestas_por_usuario(self, usuario_id):
        respuestas = self.root.child("respuestasConductor").get() or {}

        return [
            respuesta for respuesta in respuestas.values()
            if respuesta.get("UsuarioId") == usuario_id
        ]

    def obtener_estadisticas_viaje_por_usuario(self, usuario_id):
        estadisticas = self.root.child("estadisticasViaje").get() or {}

        return [
            estadistica for estadistica in estadisticas.values()
            if estadistica.get("UsuarioId") == usuario_id
        ]