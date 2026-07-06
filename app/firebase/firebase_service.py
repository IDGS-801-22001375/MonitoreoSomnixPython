from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
from app.config import FIREBASE_CREDENTIALS, FIREBASE_DATABASE_URL


class FirebaseService:
    def __init__(self):
        if not firebase_admin._apps:
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