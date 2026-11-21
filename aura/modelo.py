"""
modelo.py - Modelo de Machine Learning que predice el tiempo de viaje de una móvil.

Analogía: la fórmula de la matriz es un mapa de papel. El modelo es un conductor con
experiencia que además sabe que las emergencias llegan más rápido (sirenas) y que cada
tipo de móvil maneja distinto. Aprende esos "ajustes" mirando el histórico.
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .config import MODELOS, PRIORIDAD, FECHA_CORTE_PRUEBA

TIPO_NUM = {"TAM": 0, "TAB": 1, "VMD": 2}
FEATURES = ["eta_matriz", "dist_km", "factor", "hora", "dia_semana",
            "tipo_num", "prioridad", "misma_zona"]


def vector_features(mundo, zona_o, zona_d, tipo_movil, clase, ts):
    """Convierte una situación (de dónde, a dónde, qué móvil, qué urgencia, cuándo) en números."""
    return [
        mundo.eta_matriz(zona_o, zona_d, ts),
        mundo.km(zona_o, zona_d),
        mundo.factor(ts),
        ts.hour,
        ts.dayofweek,
        TIPO_NUM[tipo_movil],
        PRIORIDAD[clase],
        int(zona_o == zona_d),
    ]


def _matriz_X(mundo, df):
    filas = [vector_features(mundo, r.zona_origen, r.zona_destino, r.tipo_movil, r.clase, r.salida)
             for r in df.itertuples()]
    return pd.DataFrame(filas, columns=FEATURES)


def _nuevo_modelo():
    # loss="absolute_error": optimiza el error medio en minutos, no se deja arrastrar por extremos.
    return HistGradientBoostingRegressor(loss="absolute_error", max_iter=300,
                                         learning_rate=0.05, random_state=0)


def entrenar_y_evaluar(mundo, df_viajes):
    """
    Entrena con lo ANTERIOR al corte y evalúa con lo POSTERIOR (datos que el modelo no vio).
    Compara tres opciones y devuelve (tabla_resultados, modelo_final_entrenado_con_todo).
    """
    limpio = df_viajes[~df_viajes.atipico].copy()
    entrena = limpio[limpio.salida < FECHA_CORTE_PRUEBA]
    prueba = limpio[limpio.salida >= FECHA_CORTE_PRUEBA]

    # Opción 1: fórmula del README tal cual
    mae_formula = (prueba.viaje_real_min - prueba.eta_matriz).abs().mean()

    # Opción 2: fórmula + corrección promedio por (tipo de móvil, clase)
    ajuste = (entrena.viaje_real_min - entrena.eta_matriz).groupby(
        [entrena.tipo_movil, entrena.clase]).median()
    corr = prueba.apply(lambda r: ajuste.get((r.tipo_movil, r.clase), 0.0), axis=1)
    mae_ajuste = (prueba.viaje_real_min - (prueba.eta_matriz + corr)).abs().mean()

    # Opción 3: Machine Learning
    modelo = _nuevo_modelo().fit(_matriz_X(mundo, entrena), entrena.viaje_real_min)
    pred = modelo.predict(_matriz_X(mundo, prueba))
    mae_ml = np.abs(prueba.viaje_real_min.values - pred).mean()

    tabla = pd.DataFrame({
        "modelo": ["1. Fórmula del README", "2. Fórmula + ajuste por tipo/clase", "3. Machine Learning"],
        "error_medio_min": [mae_formula, mae_ajuste, mae_ml],
    }).round(2)
    info = {"n_entrena": len(entrena), "n_prueba": len(prueba),
            "n_atipicos": int(df_viajes.atipico.sum()), "n_total": len(df_viajes)}

    # Modelo final: se reentrena con TODOS los datos limpios para usarlo en la app.
    final = _nuevo_modelo().fit(_matriz_X(mundo, limpio), limpio.viaje_real_min)
    return tabla, info, final


def guardar(modelo):
    MODELOS.mkdir(exist_ok=True)
    joblib.dump(modelo, MODELOS / "eta_modelo.joblib")


class PredictorETA:
    """Envoltorio fácil: predictor.predecir(zona_o, zona_d, tipo, clase, momento) -> minutos."""

    def __init__(self, mundo, modelo=None):
        self.mundo = mundo
        ruta = MODELOS / "eta_modelo.joblib"
        if modelo is None and ruta.exists():
            modelo = joblib.load(ruta)
        self.modelo = modelo          # si es None, se usa la fórmula del README
        self._memoria = {}            # para no recalcular lo mismo mil veces (más rápido)

    def predecir(self, zona_o, zona_d, tipo_movil, clase, ts):
        clave = (zona_o, zona_d, tipo_movil, clase, ts.hour, ts.dayofweek)
        if clave in self._memoria:
            return self._memoria[clave]
        if self.modelo is None:
            valor = self.mundo.eta_matriz(zona_o, zona_d, ts)
        else:
            x = pd.DataFrame([vector_features(self.mundo, zona_o, zona_d, tipo_movil, clase, ts)],
                             columns=FEATURES)
            valor = float(max(1.0, self.modelo.predict(x)[0]))
        self._memoria[clave] = valor
        return valor
