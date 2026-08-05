import requests


class GorraService:

    def __init__(self):
        # API .NET que recibe y distribuye los comandos.
        self.base_url = (
            "https://somnixappkotlinbackend.onrender.com/api"
        )

    def iniciar_gorra(
        self,
        usuario_id=None,
        ruta_id=None
    ):
        return self.enviar_comando(
            "VIAJE_INICIAR"
        )

    def pausar_gorra(
        self,
        usuario_id=None,
        ruta_id=None
    ):
        return self.enviar_comando(
            "VIAJE_PAUSAR"
        )

    def reanudar_gorra(
        self,
        usuario_id=None,
        ruta_id=None
    ):
        return self.enviar_comando(
            "VIAJE_REANUDAR"
        )

    def detener_gorra(
        self,
        usuario_id=None,
        ruta_id=None
    ):
        return self.enviar_comando(
            "VIAJE_TERMINAR"
        )

    def apagar_alarma(self):
        return self.enviar_comando(
            "STOP_ALERT"
        )

    def sincronizar_gorra(self):
        return self.enviar_comando(
            "SYNC"
        )

    def enviar_comando(
        self,
        comando: str
    ):
        comando_seguro = str(
            comando or ""
        ).strip().upper()

        if not comando_seguro:
            return {
                "ok": False,
                "status": 0,
                "mensaje": "El comando está vacío."
            }

        try:
            response = requests.post(
                (
                    f"{self.base_url}"
                    "/Telemetria/ForzarComando"
                ),
                # .NET recibe [FromBody] string,
                # por eso se manda una cadena JSON.
                json=comando_seguro,
                timeout=10
            )

            try:
                data = (
                    response.json()
                    if response.content
                    else {}
                )
            except ValueError:
                data = {
                    "respuesta": response.text
                }

            return {
                "ok": response.ok,
                "status": response.status_code,
                "comando": comando_seguro,
                "data": data
            }

        except requests.Timeout:
            return {
                "ok": False,
                "status": 0,
                "comando": comando_seguro,
                "mensaje": (
                    "La API .NET tardó demasiado "
                    "en responder."
                )
            }

        except requests.RequestException as error:
            return {
                "ok": False,
                "status": 0,
                "comando": comando_seguro,
                "mensaje": str(error)
            }

        except Exception as error:
            return {
                "ok": False,
                "status": 0,
                "comando": comando_seguro,
                "mensaje": str(error)
            }