"""
simulador.py - Carga y ejecución comparativa de los 14 escenarios de referencia (archivo 06).
"""
import json
import pandas as pd

from .config import ARCH_ESCENARIOS, MODELOS, OBJETIVO_MIN, COMPAT, PRIORIDAD
from . import motor


def cargar_duraciones():
    """Carga las medianas de duración de servicio guardadas por 01_preparar_y_entrenar.py."""
    ruta = MODELOS / "duraciones.json"
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as f:
        raw = json.load(f)
    res = {}
    for k, v in raw.items():
        tipo, clase = k.split("|")
        res[(tipo, clase)] = float(v)
    return res


def cargar_escenarios():
    """Lee todas las hojas relevantes de 06_escenarios_referencia.xlsx de forma tolerante."""
    xls = pd.ExcelFile(ARCH_ESCENARIOS)
    hojas = {h.lower(): h for h in xls.sheet_names}

    def leer(nombre_clave, fallback_idx):
        if nombre_clave in hojas:
            return pd.read_excel(xls, hojas[nombre_clave])
        return pd.read_excel(xls, xls.sheet_names[fallback_idx])

    escenarios = leer("escenarios", 0)
    estado = leer("estado_flota", 1) if "estado_flota" in hojas else leer("estado", 1)
    solicitudes = leer("solicitudes", 2)
    eventos = leer("eventos", 3) if len(xls.sheet_names) > 3 else pd.DataFrame()

    # Normalizar códigos de clase a 2 dígitos ('01', '02', '07', '03', '06')
    for df in (solicitudes, estado):
        for col in df.columns:
            if "clasif" in col or "clase" in col:
                df[col] = df[col].astype(str).str.strip().str.zfill(2).replace("0nan", "")

    return {
        "escenarios": escenarios,
        "estado": estado,
        "solicitudes": solicitudes,
        "eventos": eventos,
    }


def flota_de_escenario(mundo, df_estado, carga_inicial=None):
    """Construye la flota inicial de un escenario combinando archivo 02 y estado del archivo 06."""
    flota = motor.crear_flota_base(mundo, carga_inicial)
    por_id = {m["id"]: m for m in flota}

    for r in df_estado.itertuples():
        mid = getattr(r, "id_movil", None)
        if mid not in por_id:
            continue
        m = por_id[mid]
        est = str(getattr(r, "estado", m["estado"])).strip().upper()
        m["estado"] = est
        zona_act = getattr(r, "id_zona_actual", None) or getattr(r, "zona_actual", None)
        if pd.notna(zona_act) and str(zona_act).strip():
            m["zona"] = str(zona_act).strip()
        libre_en = getattr(r, "minuto_liberacion", None) or getattr(r, "libre_en_min", 0)
        m["libre_en"] = float(libre_en) if pd.notna(libre_en) else 0.0
        llegada_en = getattr(r, "minuto_llegada", None) or getattr(r, "llegada_en_min", 0)
        m["llegada_en"] = float(llegada_en) if pd.notna(llegada_en) else 0.0
        clase_asig = getattr(r, "clasificacion_actual", "")
        if pd.notna(clase_asig) and str(clase_asig).strip() not in ("", "nan", "None"):
            m["clase_asignada"] = str(clase_asig).strip().zfill(2)

    return flota


def _verificar_reglas(sol, plan, flota_antes):
    """Verifica que la recomendación de AURA no viole ninguna regla obligatoria R01-R07."""
    violaciones = []
    if plan["estado"] != "ASIGNAR":
        return violaciones

    por_id = {m["id"]: m for m in flota_antes}
    clase = sol["clase"]

    for asig in plan["asignaciones"]:
        m = por_id[asig["movil"]]
        # R05: nunca asignar móvil fuera de servicio
        if m["estado"] == "FUERA_SERVICIO":
            violaciones.append(f"R05 violada en {sol['id']}: móvil {m['id']} FUERA_SERVICIO")
        # R03: VMD nunca puede tener rol de traslado
        if m["tipo"] == "VMD" and "TRASLADO" in asig["rol"]:
            violaciones.append(f"R03 violada en {sol['id']}: VMD {m['id']} asignada con rol {asig['rol']}")
        # Compatibilidad estricta
        if COMPAT[clase][m["tipo"]] == "NO_PERMITIDA":
            violaciones.append(f"Compatibilidad violada en {sol['id']}: {m['tipo']} en clase {clase}")

    return violaciones


def correr_todo(mundo, predictor, duraciones, hist, ids_filtro=None):
    """Ejecuta todos los escenarios (o los filtrados en `ids_filtro`) y compara AURA vs Despachador."""
    esc = cargar_escenarios()
    df_esc = esc["escenarios"]
    if ids_filtro:
        df_esc = df_esc[df_esc["id_escenario"].isin(ids_filtro)]

    registros = []
    violaciones = []

    for e in df_esc.itertuples():
        id_esc = e.id_escenario
        ts0 = pd.Timestamp(e.fecha_hora_inicio)
        estado_df = esc["estado"][esc["estado"]["id_escenario"] == id_esc]
        flota = flota_de_escenario(mundo, estado_df)

        sols_df = esc["solicitudes"][esc["solicitudes"]["id_escenario"] == id_esc].copy()
        sols_df["prio"] = sols_df["clasificacion_inicial"].map(PRIORIDAD)
        sols_df = sols_df.sort_values(["minuto_llegada", "prio"])

        for s in sols_df.itertuples():
            ahora = int(getattr(s, "minuto_llegada", 0))
            motor.actualizar_flota(flota, ahora)

            sol = {
                "id": s.id_solicitud,
                "clase": str(s.clasificacion_inicial).zfill(2),
                "zona": s.id_zona,
                "motivo": getattr(s, "motivo_consulta", ""),
                "llegada": ahora,
            }

            flota_snapshot = [dict(m) for m in flota]
            plan = motor.recomendar(sol, flota, ahora, ts0, mundo, predictor)
            violaciones.extend(_verificar_reglas(sol, plan, flota_snapshot))

            # Métricas de AURA
            if plan["estado"] == "ASIGNAR":
                prim = plan["asignaciones"][0]
                aura_movil = " + ".join(a["movil"] for a in plan["asignaciones"])
                aura_tr = prim["eta_total"]
                aura_costo = sum(a["costo"] for a in plan["asignaciones"])
                aura_km = sum(a["dist_km"] for a in plan["asignaciones"])
                motor.aplicar_plan(plan, sol, flota, ahora, duraciones)
            else:
                aura_movil = "EN_COLA"
                aura_tr = None
                aura_costo = None
                aura_km = None

            # Métricas del despachador (desde columnas del archivo 06)
            desp_movil = getattr(s, "movil_despachador", None) or getattr(s, "id_movil_asignado", None)
            desp_tr = getattr(s, "tiempo_respuesta_desp_min", None) or getattr(s, "eta_despachador_min", None)
            if pd.isna(desp_tr) and pd.notna(desp_movil) and str(desp_movil).strip() in {m["id"] for m in flota_snapshot}:
                m_desp = next(m for m in flota_snapshot if m["id"] == str(desp_movil).strip())
                desp_tr = predictor.predecir(m_desp["zona"], sol["zona"], m_desp["tipo"], sol["clase"], ts0 + pd.Timedelta(minutes=ahora))
                desp_km = mundo.km(m_desp["zona"], sol["zona"])
                desp_costo = m_desp["costo_km"] * desp_km + m_desp["costo_hora"] * ((desp_tr + 25.0) / 60.0)
            else:
                desp_tr = float(desp_tr) if pd.notna(desp_tr) else None
                desp_km = float(getattr(s, "km_despachador", 0)) if pd.notna(getattr(s, "km_despachador", None)) else None
                desp_costo = float(getattr(s, "costo_despachador", 0)) if pd.notna(getattr(s, "costo_despachador", None)) else None

            registros.append({
                "escenario": id_esc,
                "solicitud": sol["id"],
                "clase": sol["clase"],
                "zona": sol["zona"],
                "objetivo_min": OBJETIVO_MIN[sol["clase"]],
                "desp_movil": desp_movil,
                "desp_tr_min": round(desp_tr, 1) if desp_tr is not None else None,
                "desp_costo": round(desp_costo, 0) if desp_costo is not None else None,
                "desp_km": round(desp_km, 1) if desp_km is not None else None,
                "aura_movil": aura_movil,
                "aura_tr_min": round(aura_tr, 1) if aura_tr is not None else None,
                "aura_costo": round(aura_costo, 0) if aura_costo is not None else None,
                "aura_km": round(aura_km, 1) if aura_km is not None else None,
                "aura_explicacion": plan["explicacion"],
            })

    return pd.DataFrame(registros), violaciones


def resumen(df):
    """Genera la tabla comparativa agrupada por clasificación EMI."""
    d = df.dropna(subset=["aura_tr_min"]).copy()
    d["desp_cumple"] = d["desp_tr_min"] <= d["objetivo_min"]
    d["aura_cumple"] = d["aura_tr_min"] <= d["objetivo_min"]

    g = d.groupby("clase").agg(
        servicios=("solicitud", "count"),
        objetivo_min=("objetivo_min", "first"),
        desp_tr_min=("desp_tr_min", "mean"),
        aura_tr_min=("aura_tr_min", "mean"),
        desp_cumple_pct=("desp_cumple", lambda x: 100 * x.mean()),
        aura_cumple_pct=("aura_cumple", lambda x: 100 * x.mean()),
        desp_costo_cop=("desp_costo", "mean"),
        aura_costo_cop=("aura_costo", "mean"),
        desp_km=("desp_km", "mean"),
        aura_km=("aura_km", "mean"),
    ).round(1)
    return g
