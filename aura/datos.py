"""
datos.py - Carga de archivos, limpieza y construcción de la tabla de entrenamiento.

Idea clave (analogía): la "matriz de tiempos" es como el Google Maps del mapa vacío.
El tráfico y el tipo de móvil cambian ese tiempo. Aquí armamos la tabla que luego
le enseña al modelo cuánto cambia.
"""
import json
import pandas as pd

from .config import (ARCH_SERVICIOS, ARCH_FLOTA, ARCH_ZONAS, UMBRAL_ATIPICO_MIN, HORAS_CARGA)


# --------------------------------------------------------------------------
# 1. El "mundo": zonas, tiempos, tráfico y flota
# --------------------------------------------------------------------------
class Mundo:
    """Guarda todo lo geográfico y la flota base. Se crea una vez y se reutiliza."""

    def __init__(self):
        x = pd.ExcelFile(ARCH_ZONAS)
        zonas = pd.read_excel(x, "zonas")
        matriz = pd.read_excel(x, "matriz_tiempos")
        factor = pd.read_excel(x, "factor_trafico")

        self.zonas = zonas
        self.demanda = dict(zip(zonas.id_zona, zonas.demanda_relativa))
        self.nombre_zona = {r.id_zona: f"{r.comuna} ({r.id_zona})" for r in zonas.itertuples()}
        self.tiempo_valle = {(r.zona_origen, r.zona_destino): r.tiempo_valle_min
                             for r in matriz.itertuples()}
        self.distancia = {(r.zona_origen, r.zona_destino): r.distancia_km
                          for r in matriz.itertuples()}
        self.factores = {(r.tipo_dia, int(r.hora_inicio[:2])): r.factor
                         for r in factor.itertuples()}
        self.zonas_alta = [z for z, d in self.demanda.items() if d == "ALTA"]

        with open(ARCH_FLOTA, encoding="utf-8") as f:
            flota = json.load(f)
        self.bases = {b["id_base"]: b for b in flota["bases"]}
        self.moviles = pd.DataFrame(flota["moviles"])

    # ---- tiempo / tráfico ----
    @staticmethod
    def tipo_dia(ts):
        """Lunes-viernes, sábado o domingo/festivo (festivos no incluidos: mejora pendiente)."""
        if ts.dayofweek == 6:
            return "DOMINGO_FESTIVO"
        if ts.dayofweek == 5:
            return "SABADO"
        return "LUNES_A_VIERNES"

    def factor(self, ts):
        return self.factores[(self.tipo_dia(ts), ts.hour)]

    def eta_matriz(self, zona_o, zona_d, ts):
        """Fórmula oficial del README: tiempo_valle x factor_tráfico."""
        return self.tiempo_valle[(zona_o, zona_d)] * self.factor(ts)

    def km(self, zona_o, zona_d):
        return self.distancia[(zona_o, zona_d)]


# --------------------------------------------------------------------------
# 2. Histórico de servicios
# --------------------------------------------------------------------------
def cargar_servicios():
    with open(ARCH_SERVICIOS, encoding="utf-8") as f:
        return json.load(f)["servicios"]


def tabla_viajes(mundo, servicios=None):
    """
    Una fila por servicio con su primera móvil que llegó (COMPLETADO).
    Calcula el tiempo real de viaje = llegada - salida  (NO el tiempo_respuesta,
    que incluye la espera y los errores de registro).
    Marca los atípicos (errores de registro) en la columna 'atipico'.
    """
    servicios = servicios or cargar_servicios()
    filas = []
    for s in servicios:
        if not s["moviles"]:
            continue
        m = s["moviles"][0]
        if m["estado"] != "COMPLETADO" or not m["fecha_hora_llegada"] or not m["fecha_hora_salida"]:
            continue
        salida = pd.Timestamp(m["fecha_hora_salida"])
        llegada = pd.Timestamp(m["fecha_hora_llegada"])
        zo, zd = m["zona_origen_movil"], s["id_zona"]
        filas.append({
            "id_servicio": s["id_servicio"],
            "id_movil": m["id_movil"],
            "tipo_movil": m["tipo_movil"],
            "clase": s["clasificacion_inicial"],
            "zona_origen": zo,
            "zona_destino": zd,
            "salida": salida,
            "asignacion": pd.Timestamp(m["fecha_hora_asignacion"]),
            "llegada": llegada,
            "liberacion": pd.Timestamp(m["fecha_hora_liberacion"]),
            "viaje_real_min": (llegada - salida).total_seconds() / 60,
            "eta_matriz": mundo.eta_matriz(zo, zd, salida),
        })
    df = pd.DataFrame(filas)
    # Un tiempo real que supera >45 min a lo que dice la matriz es un error de registro.
    df["atipico"] = (df.viaje_real_min - df.eta_matriz) > UMBRAL_ATIPICO_MIN
    return df


def duraciones_servicio(df_viajes):
    """
    Cuánto tiempo queda ocupada una móvil DESPUÉS de llegar (atención + traslado + espera).
    Mediana por (tipo de móvil, clasificación). La usa el simulador.
    """
    d = df_viajes[~df_viajes.atipico].copy()
    d["ocupada_min"] = (d.liberacion - d.llegada).dt.total_seconds() / 60
    med = d.groupby(["tipo_movil", "clase"]).ocupada_min.median()
    return {k: float(v) for k, v in med.items()}


def historial_asignaciones(servicios=None):
    """Lista de (id_movil, momento de asignación) para medir la carga reciente."""
    servicios = servicios or cargar_servicios()
    filas = []
    for s in servicios:
        for m in s["moviles"]:
            filas.append((m["id_movil"], pd.Timestamp(m["fecha_hora_asignacion"])))
    return pd.DataFrame(filas, columns=["id_movil", "asignacion"])


def carga_reciente(hist, ts, horas=HORAS_CARGA):
    """Servicios asignados a cada móvil en las últimas `horas` antes de `ts`."""
    desde = ts - pd.Timedelta(hours=horas)
    h = hist[(hist.asignacion >= desde) & (hist.asignacion < ts)]
    return h.groupby("id_movil").size().to_dict()
