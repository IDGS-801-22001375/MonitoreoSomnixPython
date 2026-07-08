import requests


class GorraService:

    def __init__(self):
        # URL de la API .NET de tu compañero
        self.base_url = "https://somnixappkotlinbackend.onrender.com/api"

    def iniciar_gorra(self, usuario_id, ruta_id):
        return self.enviar_comando("INICIAR_VIAJE")

    def detener_gorra(self, usuario_id, ruta_id):
        return self.enviar_comando("DETENER_VIAJE")

    def apagar_alarma(self):
        return self.enviar_comando("APAGAR_ALARMA")

    def enviar_comando(self, comando):
        try:
            response = requests.post(
                f"{self.base_url}/Telemetria/ForzarComando",
                json=comando,
                timeout=10
            )

            return {
                "ok": response.ok,
                "status": response.status_code,
                "data": response.json() if response.content else {}
            }

        except Exception as e:
            return {
                "ok": False,
                "mensaje": str(e)
            }