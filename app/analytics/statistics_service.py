from collections import Counter
from typing import Any, Dict, List, Optional


class StatisticsService:

    def __init__(self, firebase_service):
        self.firebase = firebase_service

    # ============================================================
    # MÉTODOS AUXILIARES
    # ============================================================

    def normalizar_coleccion(self, datos: Any) -> List[Dict[str, Any]]:
        """
        Convierte las respuestas de Firebase en una lista segura.

        Firebase puede devolver:
        - Una lista de objetos.
        - Un diccionario donde cada llave es el ID del registro.
        - None cuando no existen registros.
        """

        if datos is None:
            return []

        if isinstance(datos, list):
            return [
                elemento
                for elemento in datos
                if isinstance(elemento, dict)
            ]

        if isinstance(datos, dict):
            resultado = []

            for clave, valor in datos.items():
                if isinstance(valor, dict):
                    registro = valor.copy()

                    # Guarda el ID de Firebase en caso de que no venga
                    # dentro del contenido del registro.
                    if "firebaseId" not in registro:
                        registro["firebaseId"] = clave

                    resultado.append(registro)

            return resultado

        return []

    def get_valor(
        self,
        data: Any,
        *keys: str,
        default: Any = None
    ) -> Any:
        """
        Busca un valor utilizando distintas variantes del nombre del campo.
        """

        if not isinstance(data, dict):
            return default

        for key in keys:
            if key in data:
                value = data.get(key)

                if value is not None:
                    return value

        return default

    def to_int(self, value: Any) -> int:
        """
        Convierte cualquier valor numérico a entero.
        Cuando la conversión falla, devuelve cero.
        """

        try:
            if value is None or value == "":
                return 0

            return int(float(value))

        except (ValueError, TypeError):
            return 0

    def to_float(self, value: Any) -> float:
        """
        Convierte cualquier valor numérico a decimal.
        """

        try:
            if value is None or value == "":
                return 0.0

            return float(value)

        except (ValueError, TypeError):
            return 0.0

    def to_texto(
        self,
        value: Any,
        default: str = "Sin datos"
    ) -> str:
        """
        Convierte un valor a texto evitando valores None o vacíos.
        """

        if value is None:
            return default

        texto = str(value).strip()

        return texto if texto else default

    def normalizar_id(self, value: Any) -> Optional[str]:
        """
        Normaliza los IDs para poder comparar números y cadenas.
        Por ejemplo: 1, 1.0 y '1' se consideran el mismo ID.
        """

        if value is None:
            return None

        texto = str(value).strip()

        if not texto:
            return None

        try:
            numero = float(texto)

            if numero.is_integer():
                return str(int(numero))

        except (ValueError, TypeError):
            pass

        return texto

    # ============================================================
    # OBTENER ESTADÍSTICAS
    # ============================================================

    def obtener_estadisticas_usuario(
        self,
        usuario_id: str
    ) -> Dict[str, Any]:

        usuario_id_seguro = self.to_texto(
            usuario_id,
            default=""
        )

        if not usuario_id_seguro:
            return {
                "ok": False,
                "mensaje": "No se recibió un usuario válido.",
                "usuarioId": "",
                "totalRutas": 0,
                "totalViajes": 0,
                "totalAlertas": 0,
                "fatigaMaxima": 0,
                "fatigaPromedio": 0.0,
                "rutaMayorRiesgo": "Sin datos",
                "nivelMasFrecuente": "Sin datos",
                "necesidadMasSolicitada": "Sin datos",
                "bostezosTotales": 0,
                "ojosCerradosTotales": 0,
                "riesgoGeneral": "Bajo",
                "conocimientoExtraido":
                    "No fue posible identificar al usuario."
            }

        # Normalizamos las colecciones porque Firebase puede devolver
        # listas, diccionarios o valores nulos.
        rutas = self.normalizar_coleccion(
            self.firebase.obtener_rutas_por_usuario(
                usuario_id_seguro
            )
        )

        viajes = self.normalizar_coleccion(
            self.firebase.obtener_viajes_por_usuario(
                usuario_id_seguro
            )
        )

        alertas = self.normalizar_coleccion(
            self.firebase.obtener_alertas_por_usuario(
                usuario_id_seguro
            )
        )

        monitoreos = self.normalizar_coleccion(
            self.firebase.obtener_monitoreo_por_usuario(
                usuario_id_seguro
            )
        )

        respuestas = self.normalizar_coleccion(
            self.firebase.obtener_respuestas_por_usuario(
                usuario_id_seguro
            )
        )

        total_rutas = len(rutas)
        total_viajes = len(viajes)
        total_alertas = len(alertas)

        # ========================================================
        # FATIGA
        # ========================================================

        fatigas = []

        for monitoreo in monitoreos:
            fatiga = self.get_valor(
                monitoreo,
                "FatigaDetectada",
                "fatigaDetectada",
                "fatiga",
                "Fatiga",
                default=0
            )

            fatigas.append(self.to_int(fatiga))

        fatigas_validas = [
            fatiga
            for fatiga in fatigas
            if fatiga > 0
        ]

        fatiga_maxima = (
            max(fatigas_validas)
            if fatigas_validas
            else 0
        )

        fatiga_promedio = (
            round(
                sum(fatigas_validas) /
                len(fatigas_validas),
                1
            )
            if fatigas_validas
            else 0.0
        )

        # ========================================================
        # NIVEL MÁS FRECUENTE
        # ========================================================

        niveles = []

        for alerta in alertas:
            nivel = self.get_valor(
                alerta,
                "Nivel",
                "nivel",
                default=None
            )

            nivel_texto = self.to_texto(
                nivel,
                default=""
            )

            if nivel_texto:
                niveles.append(nivel_texto)

        nivel_mas_frecuente = (
            Counter(niveles).most_common(1)[0][0]
            if niveles
            else "Sin datos"
        )

        # ========================================================
        # NECESIDAD MÁS SOLICITADA
        # ========================================================

        tipos_necesidad = []

        for respuesta in respuestas:
            tipo = self.get_valor(
                respuesta,
                "Tipo",
                "tipo",
                default=None
            )

            tipo_texto = self.to_texto(
                tipo,
                default=""
            )

            if tipo_texto:
                tipos_necesidad.append(tipo_texto)

        necesidad_mas_solicitada = (
            self.formatear_necesidad(
                Counter(tipos_necesidad)
                .most_common(1)[0][0]
            )
            if tipos_necesidad
            else "Sin datos"
        )

        # ========================================================
        # BOSTEZOS Y OJOS CERRADOS
        # ========================================================

        bostezos_totales = 0
        ojos_cerrados_totales = 0

        for monitoreo in monitoreos:
            bostezos = self.get_valor(
                monitoreo,
                "BostezosTotales",
                "bostezosTotales",
                "bostezos",
                "Bostezos",
                default=0
            )

            ojos_cerrados = self.get_valor(
                monitoreo,
                "OjosCerradosTotales",
                "ojosCerradosTotales",
                "ojosCerrados",
                "ojos_cerrados",
                "OjosCerrados",
                default=0
            )

            bostezos_totales += self.to_int(bostezos)
            ojos_cerrados_totales += self.to_int(
                ojos_cerrados
            )

        # ========================================================
        # RUTA CON MAYOR RIESGO
        # ========================================================

        ruta_mayor_riesgo_id = (
            self.obtener_ruta_mayor_riesgo(
                alertas,
                monitoreos
            )
        )

        ruta_mayor_riesgo = self.obtener_nombre_ruta(
            rutas,
            ruta_mayor_riesgo_id
        )

        # ========================================================
        # RIESGO GENERAL Y CONOCIMIENTO
        # ========================================================

        riesgo_general = (
            self.calcular_riesgo(
                fatiga_maxima,
                total_alertas
            )
            or "Bajo"
        )

        conocimiento = self.generar_conocimiento(
            ruta_mayor_riesgo=ruta_mayor_riesgo,
            fatiga_maxima=fatiga_maxima,
            fatiga_promedio=fatiga_promedio,
            total_alertas=total_alertas,
            nivel_mas_frecuente=nivel_mas_frecuente,
            necesidad_mas_solicitada=(
                necesidad_mas_solicitada
            ),
            riesgo_general=riesgo_general
        )

        return {
            "ok": True,
            "usuarioId": usuario_id_seguro,
            "totalRutas": int(total_rutas),
            "totalViajes": int(total_viajes),
            "totalAlertas": int(total_alertas),
            "fatigaMaxima": int(fatiga_maxima),
            "fatigaPromedio": float(fatiga_promedio),
            "rutaMayorRiesgo": (
                ruta_mayor_riesgo or "Sin datos"
            ),
            "nivelMasFrecuente": (
                nivel_mas_frecuente or "Sin datos"
            ),
            "necesidadMasSolicitada": (
                necesidad_mas_solicitada or "Sin datos"
            ),
            "bostezosTotales": int(bostezos_totales),
            "ojosCerradosTotales": int(
                ojos_cerrados_totales
            ),
            "riesgoGeneral": (
                riesgo_general or "Bajo"
            ),
            "conocimientoExtraido": (
                conocimiento
                or "No existen suficientes datos."
            )
        }

    # ============================================================
    # RUTA CON MAYOR RIESGO
    # ============================================================

    def obtener_ruta_mayor_riesgo(
        self,
        alertas: List[Dict[str, Any]],
        monitoreos: List[Dict[str, Any]]
    ) -> Optional[str]:

        contador = Counter()

        # Cada alerta suma un punto de riesgo.
        for alerta in alertas:
            ruta_id = self.get_valor(
                alerta,
                "RutaId",
                "rutaId",
                "ruta_id",
                "IdRuta",
                "idRuta",
                default=None
            )

            ruta_id_normalizado = self.normalizar_id(
                ruta_id
            )

            if ruta_id_normalizado:
                contador[ruta_id_normalizado] += 1

        # La fatiga también suma puntos de riesgo.
        for monitoreo in monitoreos:
            ruta_id = self.get_valor(
                monitoreo,
                "RutaId",
                "rutaId",
                "ruta_id",
                "IdRuta",
                "idRuta",
                default=None
            )

            ruta_id_normalizado = self.normalizar_id(
                ruta_id
            )

            fatiga = self.to_int(
                self.get_valor(
                    monitoreo,
                    "FatigaDetectada",
                    "fatigaDetectada",
                    "fatiga",
                    "Fatiga",
                    default=0
                )
            )

            if ruta_id_normalizado:
                contador[ruta_id_normalizado] += (
                    fatiga / 20.0
                )

        if not contador:
            return None

        return contador.most_common(1)[0][0]

    def obtener_nombre_ruta(
        self,
        rutas: List[Dict[str, Any]],
        ruta_id: Optional[str]
    ) -> str:

        ruta_id_normalizado = self.normalizar_id(
            ruta_id
        )

        if not ruta_id_normalizado:
            return "Sin datos"

        for ruta in rutas:
            id_ruta = self.get_valor(
                ruta,
                "Id",
                "id",
                "RutaId",
                "rutaId",
                "ruta_id",
                default=None
            )

            id_ruta_normalizado = self.normalizar_id(
                id_ruta
            )

            if id_ruta_normalizado == ruta_id_normalizado:
                nombre = self.get_valor(
                    ruta,
                    "Nombre",
                    "nombre",
                    "NombreRuta",
                    "nombreRuta",
                    default="Ruta sin nombre"
                )

                return self.to_texto(
                    nombre,
                    default="Ruta sin nombre"
                )

        return "Ruta no encontrada"

    # ============================================================
    # CÁLCULO DEL RIESGO
    # ============================================================

    def calcular_riesgo(
        self,
        fatiga_maxima: int,
        total_alertas: int
    ) -> str:

        fatiga = self.to_int(fatiga_maxima)
        alertas = self.to_int(total_alertas)

        if fatiga >= 75 or alertas >= 8:
            return "Alto"

        if fatiga >= 50 or alertas >= 4:
            return "Medio"

        return "Bajo"

    # ============================================================
    # CONOCIMIENTO EXTRAÍDO
    # ============================================================

    def generar_conocimiento(
        self,
        ruta_mayor_riesgo: Any,
        fatiga_maxima: Any,
        fatiga_promedio: Any,
        total_alertas: Any,
        nivel_mas_frecuente: Any,
        necesidad_mas_solicitada: Any,
        riesgo_general: Any
    ) -> str:

        ruta_texto = self.to_texto(
            ruta_mayor_riesgo,
            default="Sin datos"
        )

        nivel_texto = self.to_texto(
            nivel_mas_frecuente,
            default="Sin datos"
        )

        necesidad_texto = self.to_texto(
            necesidad_mas_solicitada,
            default="Sin datos"
        )

        riesgo_texto = self.to_texto(
            riesgo_general,
            default="Bajo"
        ).lower()

        fatiga_maxima_segura = self.to_int(
            fatiga_maxima
        )

        fatiga_promedio_segura = round(
            self.to_float(fatiga_promedio),
            1
        )

        total_alertas_seguro = self.to_int(
            total_alertas
        )

        if (
            total_alertas_seguro == 0
            and fatiga_maxima_segura == 0
        ):
            return (
                "Aún no existen suficientes datos para "
                "extraer un patrón de riesgo del conductor."
            )

        return (
            f"El análisis del usuario indica un riesgo "
            f"general {riesgo_texto}. "
            f"La ruta con mayor concentración de riesgo es "
            f"{ruta_texto}. "
            f"Se registró una fatiga máxima de "
            f"{fatiga_maxima_segura}% y una fatiga promedio "
            f"de {fatiga_promedio_segura}%. "
            f"El nivel de alerta más frecuente fue "
            f"{nivel_texto}. "
            f"La necesidad más solicitada por el conductor "
            f"fue {necesidad_texto}. "
            f"Con base en estos datos, se recomienda "
            f"programar descansos preventivos antes o "
            f"durante rutas similares."
        )

    # ============================================================
    # FORMATEAR NECESIDADES
    # ============================================================

    def formatear_necesidad(self, tipo: Any) -> str:

        tipo_seguro = self.to_texto(
            tipo,
            default=""
        ).strip().lower()

        if not tipo_seguro:
            return "Sin datos"

        mapa = {
            "necesito_descansar": "Descansar",
            "necesito_agua": "Tomar agua",
            "necesito_comer": "Comer",
            "necesito_estirar": "Estirarse",
            "necesito_dormir": "Dormir",
            "dejar_manejar": "Dejar de manejar"
        }

        return mapa.get(
            tipo_seguro,
            tipo_seguro
            .replace("_", " ")
            .capitalize()
        )