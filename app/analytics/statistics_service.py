from collections import Counter


class StatisticsService:
    def __init__(self, firebase_service):
        self.firebase = firebase_service

    def obtener_estadisticas_usuario(self, usuario_id: str):
        rutas = self.firebase.obtener_rutas_por_usuario(usuario_id)
        viajes = self.firebase.obtener_viajes_por_usuario(usuario_id)
        alertas = self.firebase.obtener_alertas_por_usuario(usuario_id)
        monitoreos = self.firebase.obtener_monitoreo_por_usuario(usuario_id)
        respuestas = self.firebase.obtener_respuestas_por_usuario(usuario_id)
        estadisticas_viaje = self.firebase.obtener_estadisticas_viaje_por_usuario(usuario_id)

        total_rutas = len(rutas)
        total_viajes = len(viajes)
        total_alertas = len(alertas)

        fatigas = []

        for m in monitoreos:
            fatigas.append(int(m.get("FatigaDetectada", 0)))

        for e in estadisticas_viaje:
            fatigas.append(int(e.get("FatigaMaxima", 0)))
            fatigas.append(int(e.get("FatigaPromedio", 0)))

        fatigas_validas = [f for f in fatigas if f > 0]

        fatiga_maxima = max(fatigas_validas) if fatigas_validas else 0
        fatiga_promedio = round(sum(fatigas_validas) / len(fatigas_validas), 1) if fatigas_validas else 0

        niveles = [a.get("Nivel", "sin nivel") for a in alertas if a.get("Nivel")]
        nivel_mas_frecuente = Counter(niveles).most_common(1)[0][0] if niveles else "Sin datos"

        tipos_necesidad = [r.get("Tipo", "") for r in respuestas if r.get("Tipo")]
        necesidad_mas_solicitada = self.formatear_necesidad(
            Counter(tipos_necesidad).most_common(1)[0][0]
        ) if tipos_necesidad else "Sin datos"

        bostezos_totales = sum(int(e.get("BostezosTotales", 0)) for e in estadisticas_viaje)
        ojos_cerrados_totales = sum(int(e.get("OjosCerradosTotales", 0)) for e in estadisticas_viaje)

        ruta_mayor_riesgo_id = self.obtener_ruta_mayor_riesgo(alertas, estadisticas_viaje)
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

    def obtener_ruta_mayor_riesgo(self, alertas, estadisticas_viaje):
        contador = Counter()

        for alerta in alertas:
            ruta_id = alerta.get("RutaId")
            if ruta_id:
                contador[ruta_id] += 1

        for estadistica in estadisticas_viaje:
            ruta_id = estadistica.get("RutaId")
            fatiga_max = int(estadistica.get("FatigaMaxima", 0))

            if ruta_id:
                contador[ruta_id] += fatiga_max / 20

        if not contador:
            return None

        return contador.most_common(1)[0][0]

    def obtener_nombre_ruta(self, rutas, ruta_id):
        if not ruta_id:
            return "Sin datos"

        for ruta in rutas:
            if ruta.get("Id") == ruta_id:
                return ruta.get("Nombre", "Ruta sin nombre")

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

        return mapa.get(tipo, tipo.replace("_", " ").capitalize())