import re
import unicodedata
import urllib.parse
import pandas as pd
import streamlit as st

from aura.config import NOMBRE_CLASE, PRIORIDAD, RAIZ, ROL_TEXTO
from aura.datos import Mundo
from aura.modelo import PredictorETA
from aura import motor
from aura.simulador import cargar_duraciones, cargar_escenarios, flota_de_escenario

st.set_page_config(page_title="AURA Despacho inteligente", layout="wide")

MANCHESTER = {
    "01": {"color": "ROJO", "emoji": "🔴", "hex": "#D32F2F", "fondo": "#FFEBEE", "texto": "#B71C1C"},
    "02": {"color": "NARANJA", "emoji": "🟠", "hex": "#F57C00", "fondo": "#FFF3E0", "texto": "#E65100"},
    "07": {"color": "AMARILLO", "emoji": "🟡", "hex": "#FBC02D", "fondo": "#FFFDE7", "texto": "#F57F17"},
    "03": {"color": "VERDE", "emoji": "🟢", "hex": "#388E3C", "fondo": "#E8F5E9", "texto": "#1B5E20"},
    "06": {"color": "AZUL", "emoji": "🔵", "hex": "#1976D2", "fondo": "#E3F2FD", "texto": "#0D47A1"},
}

TRIAJE_CATALOGO = {
    "Paro / colapso (no responde, sin pulso)": ("Sin pulso / compromiso vital", "01"),
    "Adulto con alteración de conciencia (desmayado / no despierta)": ("Paciente que no responde", "01"),
    "Alergia severa (ahogo / hinchazón de garganta)": ("Compromiso de vía aérea", "01"),
    "Déficit neurológico (boca torcida / no mueve un lado / no habla)": ("Déficit neurológico agudo", "01"),
    "Hemorragia abundante (sangrado que no para)": ("Hemorragia exanguinante", "01"),
    "Dolor torácico (dolor fuerte en el pecho)": ("Dolor precordial o cardiaco", "02"),
    "Disnea en adulto (dificultad fuerte para respirar)": ("Dificultad respiratoria marcada", "02"),
    "Asma / disnea (crisis asmática / silbido al respirar)": ("Saturación baja / broncoespasmo", "02"),
    "Convulsiones (ataque / convulsionando)": ("Convulsión activa o reciente", "02"),
    "Desmayo / colapso (pérdida de conocimiento recuperada)": ("Alteración de conciencia transitoria", "02"),
    "Diabetes (baja o subida severa de azúcar)": ("Hipoglicemia / descompensación", "02"),
    "Intoxicación (envenenamiento / sobredosis)": ("Ingesta de alto riesgo", "02"),
    "Cefalea intensa (dolor de cabeza súbito y muy fuerte)": ("Inicio súbito y dolor intenso", "02"),
    "Caídas (golpe fuerte / posible fractura)": ("Deformidad o dolor moderado en extremidad", "07"),
    "Trauma craneal (golpe en la cabeza)": ("Pérdida de conciencia breve recuperada", "07"),
    "Heridas (cortada profunda que requiere sutura)": ("Sangrado no controlable con presión leve", "07"),
    "Hipertensión (presión arterial muy alta con síntomas)": ("Cifras elevadas con síntomas leves", "07"),
    "Dolor abdominal en adulto (dolor de estómago moderado)": ("Dolor moderado", "07"),
    "Diarrea y vómitos (con debilidad o deshidratación)": ("Signos de deshidratación", "07"),
    "Problema de salud mental (crisis de ansiedad / angustia)": ("Angustia marcada", "07"),
    "Adulto con mal estado general / fiebre": ("Fiebre / malestar agudo", "03"),
    "Dolor de espalda / lumbago": ("Dolor leve a moderado reciente", "03"),
    "Problemas en extremidades (torcedura / esguince leve)": ("Dolor leve tras torcedura", "03"),
    "Problemas urinarios (ardor o dolor al orinar)": ("Disuria", "03"),
    "Síntomas respiratorios (tos / congestión con malestar)": ("Tos y congestión sin dificultad respiratoria", "03"),
    "Erupciones cutáneas (brote / picazón en piel)": ("Prurito / alergia leve", "03"),
    "Consulta banal / resfriado leve sin fiebre": ("Síntomas leves sin alarma", "06"),
    "Gastritis / acidez o malestar digestivo leve": ("Malestar leve de larga evolución", "06"),
    "Problemas oculares leves (ojo rojo sin dolor ni pérdida visual)": ("Ojo rojo sin dolor ni pérdida visual", "06"),
    "Control médico / revisión de exámenes o medicamentos": ("Orientación médica general", "06"),
    "Solicitud administrativa (fórmula médica / incapacidad / certificado)": ("Renovación de fórmula / trámite", "06"),
    "Otro": ("Consulta banal / orientación general", "06"),
}

CANALES = ["TELEFONO", "APP", "WHATSAPP"]
MUNICIPIOS = [
    "Medellín", "Envigado", "Bello", "Itagüí", "Sabaneta",
    "La Estrella", "Caldas", "Copacabana", "Girardota", "Barbosa"
]
TIPOS_VIA = ["Carrera", "Calle", "Avenida", "Circular", "Diagonal", "Transversal"]
LETRAS_VIA = [""] + [chr(c) for c in range(ord("A"), ord("Z") + 1)] + ["AA", "BB", "CC", "DD"]
LETRAS_BIS = [""] + [chr(c) for c in range(ord("A"), ord("H") + 1)]
CUADRANTES = ["Ninguno", "Sur", "Norte", "Este", "Oeste"]
SUBIR_NIVEL = {"06": "03", "03": "07", "07": "02", "02": "01", "01": "01"}

BARRIOS_A_SECTOR = [
    ("popular", ["z-med-01", "popular", "comuna 1"]),
    ("santo domingo", ["z-med-01", "popular", "comuna 1"]),
    ("santa cruz", ["z-med-02", "santa cruz", "comuna 2"]),
    ("manrique", ["z-med-03", "manrique", "comuna 3"]),
    ("campo valdes", ["z-med-04", "aranjuez", "comuna 4"]),
    ("aranjuez", ["z-med-04", "aranjuez", "comuna 4"]),
    ("moravia", ["z-med-04", "aranjuez", "comuna 4"]),
    ("castilla", ["z-med-05", "castilla", "comuna 5"]),
    ("doce de octubre", ["z-med-06", "doce de octubre", "comuna 6"]),
    ("12 de octubre", ["z-med-06", "doce de octubre", "comuna 6"]),
    ("robledo", ["z-med-07", "robledo", "comuna 7"]),
    ("pajarito", ["z-med-07", "robledo", "comuna 7"]),
    ("villa hermosa", ["z-med-08", "villa hermosa", "comuna 8"]),
    ("enciso", ["z-med-08", "villa hermosa", "comuna 8"]),
    ("buenos aires", ["z-med-09", "buenos aires", "comuna 9"]),
    ("milagrosa", ["z-med-09", "buenos aires", "comuna 9"]),
    ("candelaria", ["z-med-10", "candelaria", "centro", "comuna 10"]),
    ("centro", ["z-med-10", "candelaria", "centro", "comuna 10"]),
    ("prado", ["z-med-10", "candelaria", "centro", "comuna 10"]),
    ("laureles", ["z-med-11", "laureles", "estadio", "comuna 11"]),
    ("estadio", ["z-med-11", "laureles", "estadio", "comuna 11"]),
    ("conquistadores", ["z-med-11", "laureles", "estadio", "comuna 11"]),
    ("america", ["z-med-12", "america", "comuna 12"]),
    ("floresta", ["z-med-12", "america", "comuna 12"]),
    ("calasanz", ["z-med-12", "america", "comuna 12"]),
    ("san javier", ["z-med-13", "san javier", "comuna 13"]),
    ("poblado", ["z-med-14", "poblado", "comuna 14"]),
    ("provenza", ["z-med-14", "poblado", "comuna 14"]),
    ("castropol", ["z-med-14", "poblado", "comuna 14"]),
    ("patriarca", ["z-med-14", "poblado", "comuna 14"]),
    ("aguacatala", ["z-med-14", "poblado", "comuna 14"]),
    ("guayabal", ["z-med-15", "guayabal", "comuna 15"]),
    ("cristo rey", ["z-med-15", "guayabal", "comuna 15"]),
    ("belen", ["z-med-16", "belen", "comuna 16"]),
    ("rosales", ["z-med-16", "belen", "comuna 16"]),
    ("fatima", ["z-med-16", "belen", "comuna 16"]),
    ("bello", ["z-bel", "bello"]),
    ("niquia", ["z-bel", "bello"]),
    ("envigado", ["z-env", "envigado"]),
    ("itagui", ["z-ita", "itagui"]),
    ("sabaneta", ["z-sab", "sabaneta"]),
    ("estrella", ["z-est", "estrella"]),
    ("caldas", ["z-cal", "caldas"]),
    ("copacabana", ["z-cop", "copacabana"]),
    ("girardota", ["z-gir", "girardota"]),
    ("barbosa", ["z-bar", "barbosa"]),
]


def _normalizar(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def evaluar_triaje_automatico(motivo, texto_libre, edad, embarazada):
    texto_completo = _normalizar(f"{motivo or ''} {texto_libre or ''}")

    if motivo and motivo != "Otro" and motivo in TRIAJE_CATALOGO:
        discriminador, codigo = TRIAJE_CATALOGO[motivo]
    else:
        discriminador = "Consulta banal / orientación general"
        codigo = "06"
        if any(p in texto_completo for p in ["paro", "no respira", "inconsciente", "no responde", "infarto", "hemorragia", "ahogo", "convulsion"]):
            discriminador = "Signo vital crítico detectado en relato"
            codigo = "01"
        elif any(p in texto_completo for p in ["pecho", "fuerte", "intenso", "desmayo", "azucar", "intoxic", "fractura", "sangr"]):
            discriminador = "Signo de alarma detectado en relato"
            codigo = "02"
        elif any(p in texto_completo for p in ["caida", "golpe", "presion", "vomito", "diarrea", "ansiedad", "herida"]):
            discriminador = "Requiere valoración médica pronta"
            codigo = "07"
        elif any(p in texto_completo for p in ["fiebre", "ardor", "orinar", "espalda", "lumbago", "torcedura", "brote", "alergia"]):
            discriminador = "Consulta médica general sin alarma"
            codigo = "03"
        elif any(p in texto_completo for p in ["banal", "leve", "resfriado", "gripa", "garganta", "acidez", "gastritis", "formula", "certificado", "incapacidad", "control", "examen", "ojo rojo"]):
            discriminador = "Consulta banal / orientación sin urgencia"
            codigo = "06"

    modificadores_detectados = []
    if edad is not None and edad > 0:
        if edad < 1:
            modificadores_detectados.append("Paciente < 1 año")
        elif edad >= 75:
            modificadores_detectados.append("Adulto mayor >= 75 años")
    if any(p in texto_completo for p in ["bebe", "recien nacido", "abuelo", "abuela", "anciano", "tercera edad"]):
        if not any("año" in m for m in modificadores_detectados):
            modificadores_detectados.append("Edad extrema detectada en relato")

    if embarazada or any(p in texto_completo for p in ["embaraz", "gestant", "parto"]):
        modificadores_detectados.append("Embarazo / gestación")

    if any(p in texto_completo for p in ["cardiopat", "epoc", "corazon", "oxigeno", "via publica", "accidente transito", "choque", "atropell"]):
        modificadores_detectados.append("Comorbilidad / trauma alta energía")

    if modificadores_detectados:
        codigo = SUBIR_NIVEL[codigo]
        mod_texto = " + ".join(modificadores_detectados)
    else:
        mod_texto = "Ninguno"

    return discriminador, mod_texto, codigo


def _buscar_zona_por_palabras(palabras_objetivo, mundo, solo_medellin=False):
    for z_id, z_nombre in sorted(mundo.nombre_zona.items()):
        if solo_medellin and not str(z_id).upper().startswith("Z-MED"):
            continue
        combinado = _normalizar(f"{z_id} {z_nombre}")
        for p in palabras_objetivo:
            if p in combinado:
                return z_id
    return None


def zona_desde_coordenada_vial(municipio, tipo_via, num_via, num_cruce, cuad_via, cuad_cruce, mundo):
    """Determina la zona exacta a partir del cruce vial (Calle, Carrera, Cuadrante Vía/Cruce y Municipio)."""
    mun_norm = _normalizar(municipio)
    if mun_norm != "medellin":
        return _buscar_zona_por_palabras([mun_norm, mun_norm[:3]], mundo, solo_medellin=False)

    if num_via <= 0 or num_cruce <= 0:
        return None

    # Normalizar cuál número es Calle (eje Norte-Sur) y cuál es Carrera (eje Oriente-Occidente)
    if tipo_via in ("Carrera", "Avenida", "Transversal"):
        num_cra = num_via
        num_cll = num_cruce
        es_sur = (cuad_cruce == "Sur") or (cuad_via == "Sur")
        es_oeste = (cuad_via == "Oeste") or (cuad_cruce == "Oeste")
    else:
        num_cll = num_via
        num_cra = num_cruce
        es_sur = (cuad_via == "Sur") or (cuad_cruce == "Sur")
        es_oeste = (cuad_cruce == "Oeste") or (cuad_via == "Oeste")

    # Mapeo espacial detallado de Medellín (estrictamente Z-MED-XX)
    if es_sur or num_cll <= 18:
        pistas = ["z-med-14", "poblado"] if (num_cra <= 50 and not es_oeste) else ["z-med-15", "guayabal"]
    elif num_cll <= 45:
        if num_cra >= 65 or es_oeste:
            pistas = ["z-med-16", "belen"]
        elif num_cra < 44:
            pistas = ["z-med-09", "buenos aires"]
        else:
            pistas = ["z-med-10", "candelaria"]
    elif num_cll <= 65:
        if num_cra >= 64 or es_oeste:
            pistas = ["z-med-11", "laureles"] if num_cra <= 79 else ["z-med-12", "america"]
        elif num_cra < 42:
            pistas = ["z-med-08", "villa hermosa"]
        else:
            pistas = ["z-med-10", "candelaria"]
    elif num_cll <= 92:
        if num_cra >= 64 or es_oeste:
            pistas = ["z-med-07", "robledo"]
        elif num_cra < 45:
            pistas = ["z-med-03", "manrique"]
        else:
            pistas = ["z-med-04", "aranjuez"]
    else:
        if num_cra >= 64 or es_oeste:
            pistas = ["z-med-05", "castilla"] if num_cll <= 105 else ["z-med-06", "doce de octubre"]
        elif num_cra <= 38:
            pistas = ["z-med-01", "popular"]
        else:
            pistas = ["z-med-02", "santa cruz"]

    return _buscar_zona_por_palabras(pistas, mundo, solo_medellin=True)


def zona_desde_barrio(barrio_ref, mundo, municipio="Medellín"):
    """Determina la zona correspondiente al texto escrito en Barrio / Referencia."""
    if not barrio_ref or not barrio_ref.strip():
        return None
    solo_med = _normalizar(municipio) == "medellin"
    barrio_norm = _normalizar(barrio_ref)
    for z_id, z_nombre in sorted(mundo.nombre_zona.items()):
        if solo_med and not str(z_id).upper().startswith("Z-MED"):
            continue
        nombre_limpio = _normalizar(re.sub(r"\([^)]*\)", "", z_nombre))
        tokens = [t for t in re.split(r"[\s\-_/]+", nombre_limpio) if len(t) > 3]
        if any(t in barrio_norm for t in tokens):
            return z_id
    for clave, pistas in BARRIOS_A_SECTOR:
        if clave in barrio_norm:
            encontrada = _buscar_zona_por_palabras(pistas, mundo, solo_medellin=solo_med)
            if encontrada:
                return encontrada
    return None


def badge_urgencia(codigo, texto_extra=""):
    m = MANCHESTER[codigo]
    etiqueta = f"{m['emoji']} {NOMBRE_CLASE[codigo]} - Manchester {m['color']}"
    if texto_extra:
        etiqueta += f" | {texto_extra}"
    st.markdown(
        f'<div style="background-color:{m["fondo"]};border-left:6px solid {m["hex"]};'
        f'color:{m["texto"]};padding:10px 14px;border-radius:6px;font-weight:600;margin:6px 0 12px 0;">'
        f"{etiqueta}</div>",
        unsafe_allow_html=True,
    )


def obtener_factor_trafico_actual(mundo, ts):
    zonas = list(mundo.nombre_zona.keys())
    if len(zonas) >= 2:
        z1, z2 = zonas[0], zonas[1]
        ts_valle = pd.Timestamp("2026-04-20 03:00")
        eta_valle = mundo.eta_matriz(z1, z2, ts_valle)
        eta_ahora = mundo.eta_matriz(z1, z2, ts)
        if eta_valle > 0:
            return round(eta_ahora / eta_valle, 2)
    return 1.0


@st.cache_resource
def cargar_base():
    mundo = Mundo()
    predictor = PredictorETA(mundo)
    duraciones = cargar_duraciones()
    esc = cargar_escenarios()
    return mundo, predictor, duraciones, esc


try:
    with st.spinner("Cargando AURA..."):
        mundo, predictor, duraciones, esc = cargar_base()
except Exception as e:
    st.error(f"Error al cargar recursos iniciales: {e}")
    st.stop()

ss = st.session_state

OPCIONES_CLASE = [f"{MANCHESTER[k]['emoji']} {v}" for k, v in NOMBRE_CLASE.items()]
TEXTO_A_CLASE = {f"{MANCHESTER[k]['emoji']} {v}": k for k, v in NOMBRE_CLASE.items()}
CLASE_A_TEXTO = {k: f"{MANCHESTER[k]['emoji']} {v}" for k, v in NOMBRE_CLASE.items()}

OPCIONES_ZONA = sorted(mundo.nombre_zona.values())
TEXTO_A_ZONA = {v: k for k, v in mundo.nombre_zona.items()}

MOTIVOS_BASE = sorted([m for m in TRIAJE_CATALOGO.keys() if m != "Otro"])
MOTIVOS = MOTIVOS_BASE + ["Otro"]


def pedir_recomendacion(sol):
    motor.actualizar_flota(ss.flota, ss.ahora)
    ss.sol = sol
    ss.rec = motor.recomendar(sol, ss.flota, ss.ahora, ss.ts0, mundo, predictor)


def sincronizar_reloj_turno():
    if ss.get("modo_sim") == "Turno nuevo (flota en sus bases)":
        f_sel = ss.get("fecha_sim", pd.Timestamp("2026-04-20").date())
        h_sel = ss.get("hora_sim", pd.Timestamp("2026-04-20 08:00").time())
        ss.ts0 = pd.Timestamp(f"{f_sel} {h_sel}")
        ss.ahora = 0
        if ss.get("sol") is not None:
            pedir_recomendacion(ss.sol)


def fijar_hora_rapida(hora_str):
    nueva_hora = pd.Timestamp(f"2026-04-20 {hora_str}").time()
    ss["hora_sim"] = nueva_hora
    sincronizar_reloj_turno()


def iniciar(modo, id_esc):
    prog = []
    if modo == "Turno nuevo (flota en sus bases)":
        f_sel = ss.get("fecha_sim", pd.Timestamp("2026-04-20").date())
        h_sel = ss.get("hora_sim", pd.Timestamp("2026-04-20 08:00").time())
        ts0 = pd.Timestamp(f"{f_sel} {h_sel}")
        flota = motor.crear_flota_base(mundo)
    else:
        e = esc["escenarios"].set_index("id_escenario").loc[id_esc]
        ts0 = pd.Timestamp(e.fecha_hora_inicio)
        estado = esc["estado"][esc["estado"].id_escenario == id_esc]
        flota = flota_de_escenario(mundo, estado)
        for r in esc["solicitudes"][esc["solicitudes"].id_escenario == id_esc].itertuples():
            prog.append({
                "id": r.id_solicitud,
                "clase": r.clasificacion_inicial,
                "zona": r.id_zona,
                "motivo": r.motivo_consulta,
                "discriminador": "Triaje escenario",
                "llegada": int(r.minuto_llegada),
                "paciente": "Paciente Escenario",
                "documento": "N/A",
                "telefono": "N/A",
                "direccion": f"Dirección simulada en {mundo.nombre_zona.get(r.id_zona, r.id_zona)}",
                "canal": "TELEFONO",
                "modificador": "Ninguno",
            })
    ss.update(
        flota=flota, ts0=ts0, ahora=0, rec=None, sol=None, log=[], cola=[], prog=prog,
        contador=1, mensaje=""
    )


def avanzar(minutos):
    ss.ahora += minutos
    motor.actualizar_flota(ss.flota, ss.ahora)
    if ss.get("sol") is not None:
        pedir_recomendacion(ss.sol)


def siguiente_del_escenario():
    sol = ss.prog.pop(0)
    if sol["llegada"] > ss.ahora:
        avanzar(sol["llegada"] - ss.ahora)
    pedir_recomendacion(sol)


def reintentar_cola():
    sol = sorted(ss.cola, key=lambda s: (PRIORIDAD[s["clase"]], s["llegada"]))[0]
    pedir_recomendacion(sol)


def confirmar():
    plan, sol = ss.rec, ss.sol
    a_cola = motor.aplicar_plan(plan, sol, ss.flota, ss.ahora, duraciones)
    ss.cola = [s for s in ss.cola if s["id"] != sol["id"]] + a_cola
    codigo = sol["clase"]
    ss.log.append({
        "Hora": (ss.ts0 + pd.Timedelta(minutes=ss.ahora)).strftime("%d/%m %H:%M"),
        "Servicio": sol["id"],
        "Prioridad": f"{MANCHESTER[codigo]['emoji']} {codigo} ({MANCHESTER[codigo]['color']})",
        "Canal": sol.get("canal", "TELEFONO"),
        "Paciente": sol.get("paciente", "Sin registrar"),
        "Documento": sol.get("documento", ""),
        "Teléfono": sol.get("telefono", ""),
        "Zona": mundo.nombre_zona[sol["zona"]],
        "Dirección": sol.get("direccion", ""),
        "Motivo": sol.get("motivo", ""),
        "Modificador": sol.get("modificador", "Ninguno"),
        "Móviles": " + ".join(
            f"{a['movil']} ({ROL_TEXTO[a['rol']]} • desde {mundo.nombre_zona.get(a['zona_origen'], a['zona_origen'])})"
            for a in plan["asignaciones"]
        ),
        "Llega en (min)": round(min(a["eta_total"] for a in plan["asignaciones"]), 1),
        "Costo estimado": int(sum(a["costo"] for a in plan["asignaciones"])),
    })
    ss.mensaje = (
        f"Despacho confirmado para {sol['id']} ({sol.get('paciente', '')})."
        + (f" Se devolvió a la cola: {', '.join(s['id'] for s in a_cola)}." if a_cola else "")
    )
    ss.rec = ss.sol = None


def resolver_telefonico():
    sol = ss.sol
    ss.cola = [s for s in ss.cola if s["id"] != sol["id"]]
    codigo = sol["clase"]
    ss.log.append({
        "Hora": (ss.ts0 + pd.Timedelta(minutes=ss.ahora)).strftime("%d/%m %H:%M"),
        "Servicio": sol["id"],
        "Prioridad": f"{MANCHESTER[codigo]['emoji']} {codigo} ({MANCHESTER[codigo]['color']})",
        "Canal": sol.get("canal", "TELEFONO"),
        "Paciente": sol.get("paciente", "Sin registrar"),
        "Documento": sol.get("documento", ""),
        "Teléfono": sol.get("telefono", ""),
        "Zona": mundo.nombre_zona[sol["zona"]],
        "Dirección": sol.get("direccion", ""),
        "Motivo": sol.get("motivo", ""),
        "Modificador": sol.get("modificador", "Ninguno"),
        "Móviles": "RESUELTO_TELEFONICAMENTE (Sin móvil)",
        "Llega en (min)": 0.0,
        "Costo estimado": 0,
    })
    ss.mensaje = f"Consulta banal {sol['id']} resuelta por orientación telefónica (0 móviles consumidas)."
    ss.rec = ss.sol = None


def a_cola():
    sol = ss.sol
    if all(s["id"] != sol["id"] for s in ss.cola):
        ss.cola.append(sol)
    ss.mensaje = f"{sol['id']} quedó en cola."
    ss.rec = ss.sol = None


def descartar():
    ss.rec = ss.sol = None


# ==========================================
# BARRA LATERAL OPTIMIZADA Y REACTIVA
# ==========================================
st.sidebar.title("AURA")
st.sidebar.caption("Simulación académica • Datos 05_zonas_y_tiempos.xlsx")

modo = st.sidebar.radio(
    "Modo de operación",
    ["Turno nuevo (flota en sus bases)", "Cargar un escenario"],
    key="modo_sim",
)

id_esc = None
if modo.startswith("Cargar"):
    ids = list(esc["escenarios"].id_escenario)
    nombres = dict(zip(esc["escenarios"].id_escenario, esc["escenarios"].nombre))
    id_esc = st.sidebar.selectbox("Escenario de referencia", ids, format_func=lambda i: f"{i} - {nombres[i]}")
    if st.sidebar.button("Cargar escenario seleccionado", use_container_width=True) or "flota" not in ss:
        iniciar(modo, id_esc)
else:
    if "flota" not in ss:
        iniciar(modo, None)
    f1, f2 = st.sidebar.columns(2)
    f1.date_input(
        "Fecha",
        value=pd.Timestamp("2026-04-20").date(),
        key="fecha_sim",
        on_change=sincronizar_reloj_turno,
    )
    f2.time_input(
        "Hora",
        value=pd.Timestamp("2026-04-20 08:00").time(),
        key="hora_sim",
        on_change=sincronizar_reloj_turno,
    )
    st.sidebar.caption("Atajos de franja horaria:")
    h1, h2, h3 = st.sidebar.columns(3)
    h1.button("Valle 02h", on_click=fijar_hora_rapida, args=("02:00",), use_container_width=True)
    h2.button("Pico 08h", on_click=fijar_hora_rapida, args=("08:00",), use_container_width=True)
    h3.button("Pico 18h", on_click=fijar_hora_rapida, args=("18:00",), use_container_width=True)

ahora_ts = ss.ts0 + pd.Timedelta(minutes=ss.ahora)
factor_trafico = obtener_factor_trafico_actual(mundo, ahora_ts)

if factor_trafico >= 1.25:
    estado_trafico = f"🔴 Hora Pico ({factor_trafico:.2f}x)"
elif factor_trafico > 1.05:
    estado_trafico = f"🟡 Tráfico Medio ({factor_trafico:.2f}x)"
else:
    estado_trafico = f"🟢 Hora Valle ({factor_trafico:.2f}x)"

st.sidebar.divider()
st.sidebar.metric(
    "Reloj activo del sistema",
    ahora_ts.strftime("%d/%m %H:%M"),
    f"{estado_trafico} • +{ss.ahora} min",
)

c1, c2, c3 = st.sidebar.columns(3)
c1.button("+5 min", on_click=avanzar, args=(5,), use_container_width=True)
c2.button("+15 min", on_click=avanzar, args=(15,), use_container_width=True)
c3.button("+30 min", on_click=avanzar, args=(30,), use_container_width=True)

if modo == "Turno nuevo (flota en sus bases)":
    if st.sidebar.button("🔄 Reiniciar turno y flota", use_container_width=True):
        iniciar(modo, None)

if ss.prog:
    sig = ss.prog[0]
    st.sidebar.button(
        f"▶️ Siguiente solicitud ({sig['id']}, min {sig['llegada']})",
        on_click=siguiente_del_escenario,
        use_container_width=True,
    )

st.sidebar.divider()
st.sidebar.subheader(f"Cola de espera ({len(ss.cola)})")
for s in sorted(ss.cola, key=lambda s: (PRIORIDAD[s["clase"]], s["llegada"])):
    ico = MANCHESTER[s["clase"]]["emoji"]
    st.sidebar.write(
        f"- {ico} **{s['id']}** Clase {s['clase']} — {mundo.nombre_zona[s['zona']]} "
        f"({s.get('paciente', 'Sin nombre')})"
    )
if ss.cola:
    st.sidebar.button("Reintentar la cola", on_click=reintentar_cola, use_container_width=True)

# ==========================================
# CUERPO PRINCIPAL
# ==========================================
st.title("AURA — Asignación inteligente de móviles")
tab1, tab2, tab3, tab4 = st.tabs(["Despacho", "Flota y Reclasificación", "Historial", "Resultados"])

with tab1:
    if ss.mensaje:
        st.success(ss.mensaje)

    st.markdown("**1. Datos del afiliado**")
    u1, u2, u3, u4, u5 = st.columns([2, 1.1, 1.1, 0.8, 0.9])
    paciente = u1.text_input("Nombre completo del paciente", placeholder="Ej: Ana María Gómez")
    documento = u2.text_input("Documento / ID", placeholder="Ej: CC 43.512.890")
    telefono = u3.text_input("Teléfono", placeholder="Ej: 300 456 7890")
    edad = u4.number_input("Edad (años)", min_value=0, max_value=115, value=35, step=1)
    canal = u5.selectbox("Canal", CANALES)

    st.markdown("**2. Ubicación exacta (Nomenclatura vial oficial + Validación de barrio)**")

    # Bloque 1: Vía Principal
    st.caption("Bloque 1 — Vía Principal (ej. Carrera 30A Bis Sur)")
    vp0, vp1, vp2, vp3, vp4, vp5, vp6 = st.columns([1.2, 1.1, 0.8, 0.75, 0.55, 0.75, 0.95])
    municipio = vp0.selectbox("Municipio", MUNICIPIOS, index=0)
    tipo_via = vp1.selectbox("Tipo de Vía", TIPOS_VIA, index=0)
    num_via = vp2.number_input("N° Vía", min_value=0, max_value=300, value=0, step=1)
    letra_via = vp3.selectbox("Letra Vía", LETRAS_VIA, index=0)
    bis_via = vp4.checkbox("Bis", value=False, key="bis_via")
    letra_bis_via = vp5.selectbox("Letra Bis", LETRAS_BIS, index=0, disabled=not bis_via, key="l_bis_via")
    cuad_via = vp6.selectbox("Cuadrante Vía", CUADRANTES, index=0)

    # Bloque 2: Cruce (Vía Generadora)
    st.caption("Bloque 2 — Cruce / Vía Generadora (ej. # 34B Bis Sur - 50)")
    vc1, vc2, vc3, vc4, vc5, vc6 = st.columns([0.9, 0.8, 0.65, 0.85, 0.9, 1.0])
    num_cruce = vc1.number_input("N° Cruce (#)", min_value=0, max_value=300, value=0, step=1)
    letra_cruce = vc2.selectbox("Letra Cruce", LETRAS_VIA, index=0, key="l_cruce")
    bis_cruce = vc3.checkbox("Bis Cruce", value=False, key="bis_cruce")
    letra_bis_cruce = vc4.selectbox("Letra Bis Cr.", LETRAS_BIS, index=0, disabled=not bis_cruce, key="l_bis_cruce")
    placa = vc5.text_input("Placa (-)", placeholder="Ej: 50")
    cuad_cruce = vc6.selectbox("Cuadrante Cruce", CUADRANTES, index=0)

    # Bloque 3: Barrio / Punto de referencia y Zona resultante
    b1_dir, b2_dir = st.columns([1.8, 2.2])
    barrio_ref = b1_dir.text_input(
        "Barrio / Urbanización / Punto de referencia",
        placeholder="Ej: El Poblado, Apto 302, frente al parque...",
    )

    zona_vial = zona_desde_coordenada_vial(
        municipio, tipo_via, num_via, num_cruce, cuad_via, cuad_cruce, mundo
    )
    zona_barrio = zona_desde_barrio(barrio_ref, mundo, municipio=municipio)

    # Prioridad: la coordenada vial manda si está completa; si no, usa el barrio escrito
    zona_detectada = zona_vial or zona_barrio
    idx_zona_auto = None
    if zona_detectada and zona_detectada in mundo.nombre_zona:
        nombre_det = mundo.nombre_zona[zona_detectada]
        if nombre_det in OPCIONES_ZONA:
            idx_zona_auto = OPCIONES_ZONA.index(nombre_det)

    clave_zona_widget = (
        f"zona_{municipio}_{tipo_via}_{num_via}_{letra_via}_{bis_via}_{letra_bis_via}_{cuad_via}_"
        f"{num_cruce}_{letra_cruce}_{bis_cruce}_{letra_bis_cruce}_{cuad_cruce}_{barrio_ref}"
    )
    zona_txt = b2_dir.selectbox(
        "Zona / Comuna asignada automáticamente (editable)",
        options=OPCIONES_ZONA,
        index=idx_zona_auto,
        key=clave_zona_widget,
        placeholder="Complete la nomenclatura o seleccione manualmente...",
    )

    # Alerta de coherencia si el barrio escrito no corresponde a la dirección vial
    if zona_vial and zona_barrio and zona_vial != zona_barrio:
        st.warning(
            f"⚠️ **Inconsistencia entre nomenclatura y barrio:** La dirección vial corresponde a "
            f"**{mundo.nombre_zona[zona_vial]}**, mientras que el barrio escrito pertenece a "
            f"**{mundo.nombre_zona[zona_barrio]}**. Se priorizó la ubicación vial."
        )
    elif zona_vial and zona_txt and TEXTO_A_ZONA.get(zona_txt) != zona_vial:
        st.warning(
            f"⚠️ **Verifica la zona seleccionada:** La nomenclatura vial corresponde a "
            f"**{mundo.nombre_zona[zona_vial]}**, pero seleccionaste **{zona_txt}**."
        )

    # Armar cadena estandarizada completa de la dirección
    partes_via = [tipo_via]
    if num_via > 0:
        num_via_str = f"{num_via}{letra_via}"
        if bis_via:
            num_via_str += f" Bis{(' ' + letra_bis_via) if letra_bis_via else ''}"
        if cuad_via != "Ninguno":
            num_via_str += f" {cuad_via}"
        partes_via.append(num_via_str)

    partes_cruce = []
    if num_cruce > 0:
        num_cruce_str = f"{num_cruce}{letra_cruce}"
        if bis_cruce:
            num_cruce_str += f" Bis{(' ' + letra_bis_cruce) if letra_bis_cruce else ''}"
        if placa.strip():
            num_cruce_str += f"-{placa.strip()}"
        if cuad_cruce != "Ninguno":
            num_cruce_str += f" {cuad_cruce}"
        partes_cruce.append(f"# {num_cruce_str}")

    ref_txt = f" ({barrio_ref.strip()})" if barrio_ref.strip() else ""
    if num_via > 0 and num_cruce > 0:
        direccion_armada = f"{' '.join(partes_via)} {' '.join(partes_cruce)}, {municipio}{ref_txt}"
    elif barrio_ref.strip():
        direccion_armada = f"{barrio_ref.strip()}, {municipio}"
    else:
        direccion_armada = ""

    if direccion_armada and zona_txt:
        st.caption(f"📍 **Dirección estandarizada:** {direccion_armada}  |  **Zona:** {zona_txt}")

    st.markdown("**3. Triaje automático (sin conocimientos médicos)**")
    t1, t2 = st.columns([3, 1])
    motivo = t1.selectbox(
        "Motivo de consulta (escriba síntoma o consulta banal, o elija 'Otro')",
        options=MOTIVOS,
        index=None,
        placeholder="Escriba qué tiene el paciente (ej. dolor pecho, consulta banal, fórmula, Otro...)",
    )
    embarazada = t2.checkbox("Paciente en embarazo", value=False)

    motivo_otro = ""
    if motivo == "Otro":
        motivo_otro = st.text_input(
            "Describa lo que le ocurre al paciente (AURA clasificará si es banal, consulta o urgencia)",
            placeholder="Ej: Resfriado leve sin fiebre, renovación de fórmula, o dolor fuerte en pecho...",
        )

    disc_auto, mod_auto, codigo_sugerido = evaluar_triaje_automatico(
        motivo, motivo_otro, edad, embarazada
    )

    c_urg1, c_urg2 = st.columns([1.4, 2.6])
    clase_txt = c_urg1.selectbox(
        "Urgencia EMI asignada automáticamente",
        options=OPCIONES_CLASE,
        index=OPCIONES_CLASE.index(CLASE_A_TEXTO[codigo_sugerido]),
    )
    codigo_final = TEXTO_A_CLASE[clase_txt]

    with c_urg2:
        st.write("")
        detalle_auto = f"Criterio: {disc_auto}"
        if mod_auto != "Ninguno":
            detalle_auto += f" | Modificador: {mod_auto}"
        badge_urgencia(codigo_final, texto_extra=detalle_auto)

    enviar = st.button("Obtener recomendación", type="primary")
    if enviar:
        if not zona_txt or not motivo:
            st.warning("Por favor complete la **Nomenclatura / Zona** y el **Motivo de consulta**.")
        elif motivo == "Otro" and not motivo_otro.strip():
            st.warning("Por favor escriba la descripción de lo que le ocurre al paciente.")
        elif not direccion_armada:
            st.warning("Ingrese el **N° Vía y N° Cruce** (o el barrio/referencia) para generar la dirección exacta.")
        else:
            motivo_final = f"Otro: {motivo_otro.strip()}" if motivo == "Otro" else motivo
            sol = {
                "id": f"SRV-{ss.contador:04d}",
                "clase": codigo_final,
                "zona": TEXTO_A_ZONA[zona_txt],
                "motivo": motivo_final,
                "discriminador": disc_auto,
                "paciente": paciente.strip() or "No reportado",
                "documento": documento.strip() or "No reportado",
                "telefono": telefono.strip() or "No reportado",
                "direccion": direccion_armada,
                "canal": canal,
                "modificador": mod_auto,
                "llegada": ss.ahora,
            }
            ss.contador += 1
            ss.mensaje = ""
            pedir_recomendacion(sol)

    plan, sol = ss.rec, ss.sol
    if plan and sol:
        st.divider()
        badge_urgencia(
            sol["clase"],
            texto_extra=f"Solicitud {sol['id']} — {mundo.nombre_zona[sol['zona']]} ({estado_trafico})",
        )
        st.caption(
            f"**Paciente:** {sol.get('paciente', 'N/A')} ({sol.get('documento', 'N/A')}) | "
            f"**Tel:** {sol.get('telefono', 'N/A')} | **Dirección:** {sol.get('direccion', 'N/A')} | "
            f"**Motivo:** {sol.get('motivo', '')} | **Modificador:** {sol.get('modificador', 'Ninguno')}"
        )

        if plan["asignaciones"]:
            flota_por_id = {m["id"]: m for m in ss.flota}
            for x in plan["asignaciones"]:
                m_info = flota_por_id.get(x["movil"], {})
                zona_nombre_origen = mundo.nombre_zona.get(x["zona_origen"], x["zona_origen"])
                estado_actual_mov = m_info.get("estado", "DISPONIBLE")
                st.success(
                    f"🚑 **Ubicación actual de {x['movil']} ({x['tipo']}):** "
                    f"**{zona_nombre_origen}** (Estado: `{estado_actual_mov}` • Distancia: `{x['dist_km']:.1f} km`)"
                )

        if sol["clase"] == "06":
            st.info(
                "💡 **Consulta banal / No urgente (06 - Azul):** Según el protocolo de despacho (Doc. 04 Sec. 4.2), "
                "este caso puede resolverse por **orientación médica telefónica** sin consumir móviles, "
                "o despachar una unidad VMD si el criterio médico lo amerita."
            )

        origen_zona_nombre = mundo.nombre_zona.get(
            plan["asignaciones"][0]["zona_origen"], "Medellín"
        ) if plan["asignaciones"] else "Medellín"
        dir_destino_url = urllib.parse.quote(f"{sol['direccion']}, Antioquia")
        dir_origen_url = urllib.parse.quote(f"{origen_zona_nombre}, Antioquia")
        url_gmaps = f"https://www.google.com/maps/dir/?api=1&origin={dir_origen_url}&destination={dir_destino_url}&travelmode=driving"
        st.markdown(f"🗺️ [Ver ruta con tráfico en vivo en Google Maps]({url_gmaps})")

        if plan["estado"] == "EN_COLA":
            st.warning(plan["explicacion"])
            c_q1, c_q2, _ = st.columns([1.2, 2, 3])
            c_q1.button("Poner en cola", on_click=a_cola)
            if sol["clase"] == "06":
                c_q2.button("Resolver por orientación telefónica", type="primary", on_click=resolver_telefonico)
        else:
            cols = st.columns(len(plan["asignaciones"]))
            for col, x in zip(cols, plan["asignaciones"]):
                zona_corto = mundo.nombre_zona.get(x["zona_origen"], x["zona_origen"]).split("(")[0].strip()
                col.metric(
                    f"{x['movil']} ({x['tipo']}) — {ROL_TEXTO[x['rol']]}",
                    f"{x['eta_total']:.1f} min",
                    f"📍 Desde: {zona_corto}",
                )
            st.info(plan["explicacion"])
            for adv in plan["advertencias"]:
                st.warning(adv)

            if plan["ranking"]:
                st.caption("Las 3 mejores alternativas (menor puntaje = mejor):")
                tabla = pd.DataFrame([
                    {
                        "Móvil": o["movil"],
                        "Tipo": o["tipo"],
                        "Ubicación actual": mundo.nombre_zona.get(o["zona_origen"], o["zona_origen"]),
                        "Opción": o["tipo_opcion"],
                        "Llega en (min)": round(o["eta_total"], 1),
                        "Distancia (km)": round(o["dist_km"], 1),
                        "Costo (COP)": int(o["costo"]),
                        "Servicios recientes": o["carga"],
                        "Zonas altas descubiertas": o["zonas_descubiertas"],
                        "Puntaje": round(o["puntaje"], 2),
                    }
                    for o in plan["ranking"]
                ])
                st.dataframe(tabla, hide_index=True)

            if sol["clase"] == "06":
                b1, b2, b3, _ = st.columns([1.8, 1.4, 1, 2])
                b1.button("Resolver por orientación telefónica", type="primary", on_click=resolver_telefonico)
                b2.button("Confirmar despacho móvil", on_click=confirmar)
                b3.button("Descartar", on_click=descartar)
            else:
                b1, b2, _ = st.columns([1, 1, 4])
                b1.button("Confirmar despacho", type="primary", on_click=confirmar)
                b2.button("Descartar", on_click=descartar)

with tab2:
    filas = []
    for m in ss.flota:
        ocupada = m["estado"] not in motor.ESTADOS_LIBRES + ("FUERA_SERVICIO",)
        c_asig = m.get("clase_asignada")
        prio_txt = f"{MANCHESTER[c_asig]['emoji']} {c_asig}" if c_asig in MANCHESTER else ""
        filas.append({
            "Móvil": m["id"],
            "Tipo": m["tipo"],
            "Estado": m["estado"],
            "Ubicación": mundo.nombre_zona[m["zona"]],
            "Libre en (min)": max(0, round(m["libre_en"] - ss.ahora)) if ocupada else 0,
            "Atiende": m["asignado_a"] or "",
            "Urgencia": prio_txt,
            "Servicios recientes": m["carga"],
        })
    df = pd.DataFrame(filas)
    k = st.columns(3)
    for col, tipo in zip(k, ["TAM", "TAB", "VMD"]):
        d = df[df.Tipo == tipo]
        col.metric(
            f"{tipo} disponibles",
            f"{(d.Estado.isin(motor.ESTADOS_LIBRES)).sum()} de {(d.Estado != 'FUERA_SERVICIO').sum()}",
        )
    st.dataframe(df, hide_index=True)

    st.divider()
    st.subheader("Reclasificación en sitio y solicitud de traslado (Regla R07)")
    activas = [m for m in ss.flota if m["estado"] in ("EN_RUTA", "EN_ATENCION") and m.get("sol")]
    if not activas:
        st.caption("No hay móviles en ruta o atención en este momento para reclasificar.")
    else:
        r1, r2, r3 = st.columns([2, 1.5, 1.5])
        mov_sel = r1.selectbox(
            "Móvil que reporta cambio clínico en sitio",
            options=[m["id"] for m in activas],
            format_func=lambda mid: next(
                f"{m['id']} ({m['tipo']}) — Atiende {m['asignado_a']} (Clase {m['clase_asignada']})"
                for m in activas if m["id"] == mid
            ),
        )
        nueva_clase_txt = r2.selectbox(
            "Nueva urgencia tras valoración en sitio",
            options=[CLASE_A_TEXTO["01"], CLASE_A_TEXTO["02"]],
        )
        requiere_traslado = r3.checkbox("Requiere ambulancia de TRASLADO (R03)", value=True)

        if st.button("Aplicar reclasificación en sitio", type="primary"):
            m_obj = next(m for m in activas if m["id"] == mov_sel)
            nueva_c = TEXTO_A_CLASE[nueva_clase_txt]
            m_obj["clase_asignada"] = nueva_c
            sol_orig = dict(m_obj["sol"])
            sol_orig["clase"] = nueva_c
            sol_orig["id"] = f"{sol_orig['id']}-TRAS"
            sol_orig["llegada"] = ss.ahora
            if requiere_traslado and m_obj["tipo"] == "VMD":
                sol_orig["es_traslado_reclasificacion"] = True
                pedir_recomendacion(sol_orig)
                st.success(
                    f"Servicio reclasificado a {nueva_clase_txt}. Vaya a la pestaña 'Despacho' para confirmar "
                    f"la ambulancia de traslado recomendada."
                )
            else:
                st.success(f"Servicio {m_obj['asignado_a']} actualizado a {nueva_clase_txt}.")

    st.divider()
    st.caption("Desgaste de la tripulación: servicios de las últimas 8 h + los del turno")
    st.bar_chart(df[df.Estado != "FUERA_SERVICIO"].set_index("Móvil")["Servicios recientes"])

with tab3:
    if ss.log:
        st.dataframe(pd.DataFrame(ss.log), hide_index=True)
        csv_hist = pd.DataFrame(ss.log).to_csv(index=False).encode("utf-8")
        st.download_button(
            "Descargar bitácora del turno (CSV)",
            data=csv_hist,
            file_name="bitacora_despacho_aura.csv",
            mime="text/csv",
        )
    else:
        st.write("Todavía no hay despachos confirmados.")

with tab4:
    ruta = RAIZ / "salidas" / "resumen_por_clase.csv"
    if ruta.exists():
        st.write(
            "AURA contra el despachador en los 14 escenarios (mismos tiempos estimados por el modelo). "
            "tr = tiempo de respuesta medio en min; cumple = % dentro del tiempo objetivo."
        )
        st.dataframe(pd.read_csv(ruta, dtype={"clase": str}), hide_index=True)
        det = RAIZ / "salidas" / "comparacion_por_solicitud.csv"
        if det.exists():
            st.dataframe(pd.read_csv(det, dtype={"clase": str}), hide_index=True)
    else:
        st.write("Ejecute python 02_evaluar_escenarios.py para generar esta tabla.")