"""
motor.py
Motor de decisión de AURA.
Implementa las reglas obligatorias (R01-R07) y deseables (D01-D08) respetando
estrictamente los tiempos de 05_zonas_y_tiempos.xlsx y PredictorETA.
"""

import pandas as pd
from .config import (
    COMPAT,
    PENAL_COMPAT,
    MOTIVOS_07_CON_TRASLADO,
    PESOS,
    OBJETIVO_MIN,
    COSTO_REF,
    ESPERA_NO_RECOMENDADA,
    PENAL_DESVIO,
    UMBRAL_EMPATE_MIN,
    VENTAJA_VMD_MIN,
    COBERTURA_MIN,
    ROL_TEXTO,
)

ESTADOS_LIBRES = ("DISPONIBLE", "RETORNANDO")


def crear_flota_base(mundo, carga_inicial=None):
    """Inicializa la lista de diccionarios de móviles a partir de Mundo."""
    carga_inicial = carga_inicial or {}
    flota = []
    for r in mundo.moviles.itertuples():
        base = mundo.bases[r.id_base]
        estado = "DISPONIBLE" if r.activo else "FUERA_SERVICIO"
        flota.append({
            "id": r.id_movil,
            "tipo": r.tipo_movil,
            "id_base": r.id_base,
            "zona_base": base["id_zona"],
            "zona": base["id_zona"],
            "costo_km": float(r.costo_km),
            "costo_hora": float(r.costo_hora),
            "estado": estado,
            "libre_en": 0.0,
            "llegada_en": 0.0,
            "asignado_a": None,
            "clase_asignada": None,
            "sol": None,
            "carga": int(carga_inicial.get(r.id_movil, 0)),
        })
    return flota


def actualizar_flota(flota, ahora):
    """Actualiza el estado de las móviles ocupadas cuando el reloj simulado avanza."""
    for m in flota:
        if m["estado"] in ("FUERA_SERVICIO", "DISPONIBLE"):
            continue
        if m["estado"] == "RETORNANDO":
            if ahora >= m["libre_en"]:
                m["estado"] = "DISPONIBLE"
                m["zona"] = m["zona_base"]
                m["libre_en"] = 0.0
            continue
        if ahora >= m["libre_en"]:
            m["estado"] = "DISPONIBLE"
            m["libre_en"] = 0.0
            m["llegada_en"] = 0.0
            m["asignado_a"] = None
            m["clase_asignada"] = None
            m["sol"] = None
        elif m["estado"] == "EN_RUTA" and ahora >= m["llegada_en"]:
            m["estado"] = "EN_ATENCION"


def _costo_servicio(movil, dist_km, eta_min):
    """Calcula el costo operativo estimado (km + tiempo de desplazamiento/atención)."""
    horas_est = (eta_min + 25.0) / 60.0
    return movil["costo_km"] * dist_km + movil["costo_hora"] * horas_est


def _zonas_altas_descubiertas(flota_sim, mundo, ts, excl_movil_id=None):
    """D03: cuenta cuántas zonas de demanda ALTA quedan sin ambulancia a <= COBERTURA_MIN."""
    ambulancias = [
        m for m in flota_sim
        if m["tipo"] in ("TAM", "TAB")
        and m["estado"] in ESTADOS_LIBRES
        and m["id"] != excl_movil_id
    ]
    descubiertas = 0
    for z_alta in mundo.zonas_alta:
        cubierta = any(
            mundo.eta_matriz(m["zona"], z_alta, ts) <= COBERTURA_MIN
            for m in ambulancias
        )
        if not cubierta:
            descubiertas += 1
    return descubiertas


def _evaluar_candidatas(sol, flota, ahora, ts0, mundo, predictor, solo_ambulancias=False):
    """Evalúa todas las móviles elegibles según compatibilidad, reglas R01-R07 y deseables."""
    clase = sol["clase"]
    zona_dest = sol["zona"]
    motivo = sol.get("motivo", "")
    espera_min = max(0.0, ahora - sol.get("llegada", ahora))
    obj_min = OBJETIVO_MIN[clase]
    ts_actual = ts0 + pd.Timedelta(minutes=float(ahora))

    pesos = PESOS[clase]
    opciones = []

    for m in flota:
        if m["estado"] == "FUERA_SERVICIO":
            continue

        tipo = m["tipo"]
        if solo_ambulancias and tipo not in ("TAM", "TAB"):
            continue

        regla_compat = COMPAT[clase][tipo]
        if regla_compat == "NO_PERMITIDA":
            continue

        if regla_compat == "NO_RECOMENDADA" and espera_min < obj_min * ESPERA_NO_RECOMENDADA:
            continue

        tipo_opcion = "DIRECTA"
        demora_liberacion = 0.0

        if m["estado"] in ESTADOS_LIBRES:
            tipo_opcion = "DIRECTA"
        elif m["estado"] == "EN_RUTA":
            if clase in ("01", "02") and m.get("clase_asignada") in ("03", "06"):
                tipo_opcion = "DESVIO"
            else:
                continue
        elif m["estado"] in ("EN_ATENCION", "EN_TRASLADO"):
            if clase in ("01", "02"):
                tipo_opcion = "PREASIGNACION"
                demora_liberacion = max(1.0, m["libre_en"] - ahora)
            else:
                continue
        else:
            continue

        # D01: ETA oficial basado en 05_zonas_y_tiempos.xlsx (matriz_tiempos * factor_trafico) + ML
        eta_viaje = float(predictor.predecir(m["zona"], zona_dest, tipo, clase, ts_actual))
        eta_total = demora_liberacion + eta_viaje
        dist_km = mundo.km(m["zona"], zona_dest)
        costo = _costo_servicio(m, dist_km, eta_viaje)

        penal_compat = PENAL_COMPAT.get(regla_compat, 0.0)
        if clase == "07" and tipo == "TAB" and motivo in MOTIVOS_07_CON_TRASLADO:
            penal_compat = max(0.0, penal_compat - 0.15)

        penal_desvio = PENAL_DESVIO if tipo_opcion == "DESVIO" else 0.0
        zonas_desc = (
            _zonas_altas_descubiertas(flota, mundo, ts_actual, excl_movil_id=m["id"])
            if tipo in ("TAM", "TAB") and tipo_opcion == "DIRECTA"
            else 0
        )

        puntaje = (
            pesos["tiempo"] * (eta_total / obj_min)
            + pesos["costo"] * (costo / COSTO_REF)
            + pesos["carga"] * (m["carga"] / 5.0)
            + pesos["cobertura"] * zonas_desc
            + penal_compat
            + penal_desvio
        )

        opciones.append({
            "movil": m["id"],
            "tipo": tipo,
            "zona_origen": m["zona"],
            "tipo_opcion": tipo_opcion,
            "regla_compat": regla_compat,
            "eta_total": round(eta_total, 2),
            "dist_km": round(dist_km, 2),
            "costo": round(costo, 0),
            "carga": m["carga"],
            "zonas_descubiertas": zonas_desc,
            "puntaje": round(puntaje, 4),
        })

    opciones.sort(key=lambda x: x["puntaje"])
    if len(opciones) >= 2:
        primera, segunda = opciones[0], opciones[1]
        if (
            abs(primera["eta_total"] - segunda["eta_total"]) < UMBRAL_EMPATE_MIN
            and segunda["costo"] < primera["costo"]
            and segunda["regla_compat"] != "ESTABILIZACION"
        ):
            opciones[0], opciones[1] = segunda, primera

    return opciones


def recomendar(sol, flota, ahora, ts0, mundo, predictor):
    """Genera el plan de asignación para una solicitud 'sol'."""
    clase = sol["clase"]
    obj_min = OBJETIVO_MIN[clase]
    es_traslado_sitio = sol.get("es_traslado_reclasificacion", False)

    opciones = _evaluar_candidatas(
        sol, flota, ahora, ts0, mundo, predictor, solo_ambulancias=es_traslado_sitio
    )

    if not opciones:
        return {
            "estado": "EN_COLA",
            "asignaciones": [],
            "ranking": [],
            "explicacion": f"No hay móviles elegibles disponibles para {sol['id']}.",
            "advertencias": ["Flota sin disponibilidad compatible en este momento."],
        }

    advertencias = []
    asignaciones = []

    ambs = [o for o in opciones if o["tipo"] in ("TAM", "TAB")]
    vmds = [o for o in opciones if o["tipo"] == "VMD"]

    if es_traslado_sitio:
        if not ambs:
            return {
                "estado": "EN_COLA",
                "asignaciones": [],
                "ranking": opciones[:3],
                "explicacion": f"Sin ambulancia disponible para traslado de {sol['id']}.",
                "advertencias": ["R03: Solo ambulancias TAM/TAB pueden trasladar."],
            }
        asignaciones.append(dict(ambs[0], rol="TRASLADO"))

    elif clase in ("01", "02"):
        mejor_amb = ambs[0] if ambs else None
        mejor_vmd = vmds[0] if vmds else None
        necesita_vmd_r04 = False

        if mejor_vmd and mejor_vmd["tipo_opcion"] == "DIRECTA":
            if mejor_amb is None:
                necesita_vmd_r04 = True
            elif mejor_amb["tipo_opcion"] == "PREASIGNACION":
                necesita_vmd_r04 = True
            elif (
                mejor_amb["eta_total"] > obj_min
                and (mejor_amb["eta_total"] - mejor_vmd["eta_total"]) >= VENTAJA_VMD_MIN
            ):
                necesita_vmd_r04 = True

        if necesita_vmd_r04:
            vmd_asig = dict(mejor_vmd, rol="PRIMER_RESPONDIENTE_ESTABILIZACION")
            asignaciones.append(vmd_asig)
            advertencias.append(
                f"R04: Se envía {vmd_asig['movil']} (VMD) como primer respondiente "
                f"({vmd_asig['eta_total']:.0f} min) por ausencia o lejanía de ambulancia."
            )
            if mejor_amb:
                asignaciones.append(dict(mejor_amb, rol="ATENCION_Y_TRASLADO"))
            else:
                advertencias.append("Sin ambulancia en flota activa para preasignar traslado.")
        elif mejor_amb:
            rol = "ATENCION_Y_TRASLADO" if clase == "01" else "ATENCION"
            amb_asig = dict(mejor_amb, rol=rol)
            asignaciones.append(amb_asig)

            if (
                clase == "01"
                and mejor_amb["tipo"] == "TAB"
                and mejor_vmd
                and mejor_vmd["tipo_opcion"] == "DIRECTA"
                and mejor_vmd["eta_total"] <= obj_min
            ):
                asignaciones.append(dict(mejor_vmd, rol="APOYO_MEDICO"))
                advertencias.append(
                    f"D07: Se envía {mejor_vmd['movil']} (VMD) como apoyo médico avanzado."
                )
        else:
            return {
                "estado": "EN_COLA",
                "asignaciones": [],
                "ranking": opciones[:3],
                "explicacion": f"No hay ambulancias ni VMD en ruta rápida para {sol['id']}.",
                "advertencias": ["R03: Solo ambulancias pueden trasladar."],
            }
    else:
        directas = [o for o in opciones if o["tipo_opcion"] == "DIRECTA"]
        if not directas:
            return {
                "estado": "EN_COLA",
                "asignaciones": [],
                "ranking": opciones[:3],
                "explicacion": f"Todas las móviles compatibles están ocupadas; {sol['id']} pasa a cola.",
                "advertencias": [],
            }
        asignaciones.append(dict(directas[0], rol="ATENCION"))

    for a in asignaciones:
        if a["tipo_opcion"] == "DESVIO":
            advertencias.append(
                f"R06: Se desvía {a['movil']} de un servicio de baja prioridad; el caso anterior vuelve a cola."
            )
        if a["zonas_descubiertas"] > 0:
            advertencias.append(
                f"D03: Esta asignación deja {a['zonas_descubiertas']} zona(s) de alta demanda descubierta(s)."
            )
        if a["eta_total"] > obj_min and a["rol"] != "ATENCION_Y_TRASLADO":
            advertencias.append(
                f"ETA estimado ({a['eta_total']:.0f} min) supera el tiempo objetivo ({obj_min} min)."
            )

    principal = asignaciones[0]
    explicacion = (
        f"Se recomienda {principal['movil']} ({principal['tipo']}) desde {principal['zona_origen']} "
        f"como {ROL_TEXTO.get(principal['rol'], principal['rol'])}: llega en ~{principal['eta_total']:.0f} min "
        f"(objetivo {obj_min} min), costo estimado ${principal['costo']:,.0f} COP y "
        f"{principal['carga']} servicios recientes."
    )

    return {
        "estado": "ASIGNAR",
        "asignaciones": asignaciones,
        "ranking": opciones[:3],
        "explicacion": explicacion,
        "advertencias": advertencias,
    }


def aplicar_plan(plan, sol, flota, ahora, duraciones):
    """Aplica el plan recomendado sobre 'flota' mutando estados y retornando devueltos a cola."""
    devueltos_a_cola = []
    if plan["estado"] != "ASIGNAR":
        return devueltos_a_cola

    for asig in plan["asignaciones"]:
        m = next(x for x in flota if x["id"] == asig["movil"])
        if m["estado"] == "EN_RUTA" and m.get("sol"):
            devueltos_a_cola.append(m["sol"])

        dur_atencion = duraciones.get((m["tipo"], sol["clase"]), 35.0)
        eta = asig["eta_total"]

        m["zona"] = sol["zona"]
        m["asignado_a"] = sol["id"]
        m["clase_asignada"] = sol["clase"]
        m["sol"] = sol
        m["carga"] += 1

        if asig["tipo_opcion"] == "PREASIGNACION":
            m["estado"] = "EN_ATENCION"
            m["llegada_en"] = ahora + eta
            m["libre_en"] = ahora + eta + dur_atencion
        else:
            m["estado"] = "EN_RUTA"
            m["llegada_en"] = ahora + eta
            m["libre_en"] = ahora + eta + dur_atencion

    return devueltos_a_cola