import requests


class GorraService:

    def __init__(self):
        # Cambiar cuando tu compañero entregue la API
        self.base_url = "http://localhost:5000/api"

    def iniciar_gorra(self, usuario_id, ruta_id):

        try:

            response = requests.post(
                f"{self.base_url}/gorra/iniciar",
                json={
                    "usuarioId": usuario_id,
                    "rutaId": ruta_id
                },
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

    def detener_gorra(self, usuario_id, ruta_id):

        try:

            response = requests.post(
                f"{self.base_url}/gorra/detener",
                json={
                    "usuarioId": usuario_id,
                    "rutaId": ruta_id
                },
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

    def obtener_estado(self):

        try:

            response = requests.get(
                f"{self.base_url}/gorra/estado",
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