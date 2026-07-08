from collections import Counter


class StatisticsService:
    def __init__(self, firebase_service):
        self.firebase = firebase_service

    def get_valor(self, data, *keys, default=None):
        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)
        return default

    def to_int(self, value):
        try:
            return int(float(value))
        except:
            return 0

    def obtener_estadisticas_usuario(self, usuario_id: str):
        rutas = self.firebase.obtener_rutas_por_usuario(usuario_id) or []
        viajes = self.firebase.obtener_viajes_por_usuario(usuario_id) or []
        alertas = self.firebase.obtener_alertas_por_usuario(usuario_id) or []
        monitoreos = self.firebase.obtener_monitoreo_por_usuario(usuario_id) or []
        respuestas = self.firebase.obtener_respuestas_por_usuario(usuario_id) or []

        total_rutas = len(rutas)
        total_viajes = len(viajes)
        total_alertas = len(alertas)

        fatigas = []

        for m in monitoreos:
            fatiga = self.get_valor(
                m,
                "FatigaDetectada",
                "fatigaDetectada",
                "fatiga",
                "Fatiga",
                default=0
            )
            fatigas.append(self.to_int(fatiga))

        fatigas_validas = [f for f in fatigas if f > 0]

        fatiga_maxima = max(fatigas_validas) if fatigas_validas else 0
        fatiga_promedio = round(sum(fatigas_validas) / len(fatigas_validas), 1) if fatigas_validas else 0

        niveles = []

        for alerta in alertas:
            nivel = self.get_valor(alerta, "Nivel", "nivel", default=None)
            if nivel:
                niveles.append(nivel)

        nivel_mas_frecuente = Counter(niveles).most_common(1)[0][0] if niveles else "Sin datos"

        tipos_necesidad = []

        for r in respuestas:
            tipo = self.get_valor(r, "Tipo", "tipo", default=None)
            if tipo:
                tipos_necesidad.append(tipo)

        necesidad_mas_solicitada = (
            self.formatear_necesidad(Counter(tipos_necesidad).most_common(1)[0][0])
            if tipos_necesidad else "Sin datos"
        )

        bostezos_totales = 0
        ojos_cerrados_totales = 0

        for m in monitoreos:
            bostezos_totales += self.to_int(
                self.get_valor(m, "BostezosTotales", "bostezosTotales", "bostezos", "Bostezos", default=0)
            )

            ojos_cerrados_totales += self.to_int(
                self.get_valor(m, "OjosCerradosTotales", "ojosCerradosTotales", "ojosCerrados", "ojos_cerrados", default=0)
            )

        ruta_mayor_riesgo_id = self.obtener_ruta_mayor_riesgo(alertas, monitoreos)
        ruta_mayor_riesgo = self.obtener_nombre_ruta(rutas, ruta_mayor_riesgo_id)

        riesgo_general = self.calcular_riesgo(fatiga_maxima, total_alertas)

        conocimiento = self.generar_conocimiento(
            ruta_mayor_riesgo,
            fatiga_maxima,
            fatiga_promedio,
            total_alertas,
            nivel_mas_frecuente,
            necesidad_mas_solicitada,
            riesgo_general
        )

        return {
            "ok": True,
            "usuarioId": usuario_id,
            "totalRutas": total_rutas,
            "totalViajes": total_viajes,
            "totalAlertas": total_alertas,
            "fatigaMaxima": fatiga_maxima,
            "fatigaPromedio": fatiga_promedio,
            "rutaMayorRiesgo": ruta_mayor_riesgo,
            "nivelMasFrecuente": nivel_mas_frecuente,
            "necesidadMasSolicitada": necesidad_mas_solicitada,
            "bostezosTotales": bostezos_totales,
            "ojosCerradosTotales": ojos_cerrados_totales,
            "riesgoGeneral": riesgo_general,
            "conocimientoExtraido": conocimiento
        }

    def obtener_ruta_mayor_riesgo(self, alertas, monitoreos):
        contador = Counter()

        for alerta in alertas:
            ruta_id = self.get_valor(alerta, "RutaId", "rutaId", "ruta_id", default=None)
            if ruta_id:
                contador[ruta_id] += 1

        for monitoreo in monitoreos:
            ruta_id = self.get_valor(monitoreo, "RutaId", "rutaId", "ruta_id", default=None)
            fatiga = self.to_int(
                self.get_valor(monitoreo, "FatigaDetectada", "fatigaDetectada", "fatiga", "Fatiga", default=0)
            )

            if ruta_id:
                contador[ruta_id] += fatiga / 20

        if not contador:
            return None

        return contador.most_common(1)[0][0]

    def obtener_nombre_ruta(self, rutas, ruta_id):
        if not ruta_id:
            return "Sin datos"

        for ruta in rutas:
            id_ruta = self.get_valor(ruta, "Id", "id", "rutaId", default=None)

            if id_ruta == ruta_id:
                return self.get_valor(ruta, "Nombre", "nombre", default="Ruta sin nombre")

        return "Ruta no encontrada"

    def calcular_riesgo(self, fatiga_maxima, total_alertas):
        if fatiga_maxima >= 75 or total_alertas >= 8:
            return "Alto"

        if fatiga_maxima >= 50 or total_alertas >= 4:
            return "Medio"

        return "Bajo"

    def generar_conocimiento(
        self,
        ruta_mayor_riesgo,
        fatiga_maxima,
        fatiga_promedio,
        total_alertas,
        nivel_mas_frecuente,
        necesidad_mas_solicitada,
        riesgo_general
    ):
        if total_alertas == 0 and fatiga_maxima == 0:
            return "Aún no existen suficientes datos para extraer un patrón de riesgo del conductor."

        return (
            f"El análisis del usuario indica un riesgo general {riesgo_general.lower()}. "
            f"La ruta con mayor concentración de riesgo es {ruta_mayor_riesgo}. "
            f"Se registró una fatiga máxima de {fatiga_maxima}% y una fatiga promedio de {fatiga_promedio}%. "
            f"El nivel de alerta más frecuente fue {nivel_mas_frecuente}. "
            f"La necesidad más solicitada por el conductor fue {necesidad_mas_solicitada}. "
            f"Con base en estos datos, se recomienda programar descansos preventivos antes o durante rutas similares."
        )

    def formatear_necesidad(self, tipo):
        mapa = {
            "necesito_descansar": "Descansar",
            "necesito_agua": "Tomar agua",
            "necesito_comer": "Comer",
            "necesito_estirar": "Estirarse",
            "necesito_dormir": "Dormir",
            "dejar_manejar": "Dejar de manejar"
        }

        return mapa.get(tipo, str(tipo).replace("_", " ").capitalize())