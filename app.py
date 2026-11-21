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
SUBIR_NIVEL = {"06": "03", "03": "07", "07": "02", "02": "01", "01": "01"}

PALABRAS_ZONA = [
    ("popular", "Z-MED-01"),
    ("santo domingo", "Z-MED-01"),
    ("santa cruz", "Z-MED-02"),
    ("manrique", "Z-MED-03"),
    ("campo valdes", "Z-MED-04"),
    ("aranjuez", "Z-MED-04"),
    ("moravia", "Z-MED-04"),
    ("castilla", "Z-MED-05"),
    ("doce de octubre", "Z-MED-06"),
    ("12 de octubre", "Z-MED-06"),
    ("robledo", "Z-MED-07"),
    ("pajarito", "Z-MED-07"),
    ("villa hermosa", "Z-MED-08"),
    ("enciso", "Z-MED-08"),
    ("buenos aires", "Z-MED-09"),
    ("milagrosa", "Z-MED-09"),
    ("candelaria", "Z-MED-10"),
    ("centro", "Z-MED-10"),
    ("prado", "Z-MED-10"),
    ("laureles", "Z-MED-11"),
    ("estadio", "Z-MED-11"),
    ("conquistadores", "Z-MED-11"),
    ("america", "Z-MED-12"),
    ("floresta", "Z-MED-12"),
    ("calasanz", "Z-MED-12"),
    ("san javier", "Z-MED-13"),
    ("poblado", "Z-MED-14"),
    ("provenza", "Z-MED-14"),
    ("castropol", "Z-MED-14"),
    ("patriarca", "Z-MED-14"),
    ("guayabal", "Z-MED-15"),
    ("cristo rey", "Z-MED-15"),
    ("belen", "Z-MED-16"),
    ("rosales", "Z-MED-16"),
    ("fatima", "Z-MED-16"),
    ("bello", "Z-BEL"),
    ("niquia", "Z-BEL"),
    ("envigado", "Z-ENV"),
    ("itagui", "Z-ITA"),
    ("sabaneta", "Z-SAB"),
    ("estrella", "Z-EST"),
    ("caldas", "Z-CAL"),
    ("copacabana", "Z-COP"),
    ("girardota", "Z-GIR"),
    ("barbosa", "Z-BAR"),
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


def detectar_zona_desde_direccion(direccion, mundo):
    if not direccion or not direccion.strip():
        return None
    texto = _normalizar(direccion)
    zonas_disponibles = list(mundo.nombre_zona.keys())

    for z in zonas_disponibles:
        if _normalizar(z) in texto:
            return z

    for clave, prefijo in PALABRAS_ZONA:
        if clave in texto:
            candidatas = sorted([z for z in zonas_disponibles if z.startswith(prefijo)])
            if candidatas:
                return candidatas[0]

    for z, nombre in mundo.nombre_zona.items():
        nombre_limpio = _normalizar(nombre.split("(")[0])
        palabras = [p for p in re.split(r"[\s\-]+", nombre_limpio) if len(p) > 3]
        if any(p in texto for p in palabras):
            return z

    m_cll = re.search(r"\b(?:cll|cl|calle)\s*(\d+)", texto)
    m_cra = re.search(r"\b(?:cra|cr|carrera|kr)\s*(\d+)", texto)
    if m_cll:
        num_cll = int(m_cll.group(1))
        num_cra = int(m_cra.group(1)) if m_cra else 50
        if "sur" in texto or num_cll <= 18:
            pref = "Z-MED-14" if num_cra < 50 else "Z-MED-15"
        elif num_cll <= 45:
            pref = "Z-MED-16" if num_cra >= 65 else ("Z-MED-09" if num_cra < 45 else "Z-MED-10")
        elif num_cll <= 65:
            pref = "Z-MED-11" if num_cra >= 65 else ("Z-MED-08" if num_cra < 45 else "Z-MED-10")
        elif num_cll <= 90:
            pref = "Z-MED-07" if num_cra >= 65 else "Z-MED-04"
        else:
            pref = "Z-MED-05" if num_cra >= 65 else "Z-MED-02"
        candidatas = sorted([z for z in zonas_disponibles if z.startswith(pref)])
        if candidatas:
            return candidatas[0]

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


def iniciar(modo, id_esc, fecha, hora):
    prog = []
    if modo == "Turno nuevo (flota en sus bases)":
        ts0 = pd.Timestamp(f"{fecha} {hora}")
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


def pedir_recomendacion(sol):
    motor.actualizar_flota(ss.flota, ss.ahora)
    ss.sol = sol
    ss.rec = motor.recomendar(sol, ss.flota, ss.ahora, ss.ts0, mundo, predictor)


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
        "Móviles": " + ".join(f"{a['movil']} ({ROL_TEXTO[a['rol']]})" for a in plan["asignaciones"]),
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


st.sidebar.title("AURA")
st.sidebar.caption("Simulación académica con datos ficticios. Sin conexión a sistemas reales.")
modo = st.sidebar.radio("Modo", ["Turno nuevo (flota en sus bases)", "Cargar un escenario"])
id_esc, fecha, hora = None, None, None
if modo.startswith("Cargar"):
    ids = list(esc["escenarios"].id_escenario)
    nombres = dict(zip(esc["escenarios"].id_escenario, esc["escenarios"].nombre))
    id_esc = st.sidebar.selectbox("Escenario", ids, format_func=lambda i: f"{i} - {nombres[i]}")
else:
    fecha = st.sidebar.date_input("Fecha simulada", value=pd.Timestamp("2026-04-20"))
    hora = st.sidebar.time_input("Hora simulada", value=pd.Timestamp("2026-04-20 08:00"))

if st.sidebar.button("Iniciar / reiniciar simulación") or "flota" not in ss:
    iniciar(modo, id_esc, fecha, hora)

ahora_ts = ss.ts0 + pd.Timedelta(minutes=ss.ahora)
st.sidebar.metric("Reloj simulado", ahora_ts.strftime("%d/%m %H:%M"), f"minuto {ss.ahora}")
c1, c2, c3 = st.sidebar.columns(3)
c1.button("+5 min", on_click=avanzar, args=(5,))
c2.button("+15 min", on_click=avanzar, args=(15,))
c3.button("+30 min", on_click=avanzar, args=(30,))

if ss.prog:
    sig = ss.prog[0]
    st.sidebar.button(
        f"Siguiente solicitud del escenario ({sig['id']}, min {sig['llegada']})",
        on_click=siguiente_del_escenario,
    )

st.sidebar.subheader(f"Cola de espera ({len(ss.cola)})")
for s in sorted(ss.cola, key=lambda s: (PRIORIDAD[s["clase"]], s["llegada"])):
    ico = MANCHESTER[s["clase"]]["emoji"]
    st.sidebar.write(
        f"- {ico} **{s['id']}** Clase {s['clase']} — {mundo.nombre_zona[s['zona']]} "
        f"({s.get('paciente', 'Sin nombre')})"
    )
if ss.cola:
    st.sidebar.button("Reintentar la cola", on_click=reintentar_cola)

st.title("AURA — Asignación inteligente de móviles")
tab1, tab2, tab3, tab4 = st.tabs(["Despacho", "Flota y Reclasificación", "Historial", "Resultados"])

with tab1:
    if ss.mensaje:
        st.success(ss.mensaje)

    st.markdown("**1. Datos del afiliado y ubicación exacta**")
    u1, u2, u3, u4, u5 = st.columns([2, 1.1, 1.1, 0.8, 0.9])
    paciente = u1.text_input("Nombre completo del paciente", placeholder="Ej: Ana María Gómez")
    documento = u2.text_input("Documento / ID", placeholder="Ej: CC 43.512.890")
    telefono = u3.text_input("Teléfono", placeholder="Ej: 300 456 7890")
    edad = u4.number_input("Edad (años)", min_value=0, max_value=115, value=35, step=1)
    canal = u5.selectbox("Canal", CANALES)

    d1, d2 = st.columns([2.6, 1.4])
    direccion = d1.text_input(
        "Dirección exacta y punto de referencia (detecta zona automáticamente)",
        placeholder="Ej: Cra 43A # 14-25, El Poblado, Apto 402 (presione Enter tras escribir)",
    )

    zona_detectada = detectar_zona_desde_direccion(direccion, mundo)
    idx_zona = None
    if zona_detectada and zona_detectada in mundo.nombre_zona:
        nombre_det = mundo.nombre_zona[zona_detectada]
        if nombre_det in OPCIONES_ZONA:
            idx_zona = OPCIONES_ZONA.index(nombre_det)

    zona_txt = d2.selectbox(
        "Zona / Comuna (automática o búsqueda manual)",
        options=OPCIONES_ZONA,
        index=idx_zona,
        placeholder="Se completa con la dirección o escriba para buscar...",
    )
    if zona_detectada and direccion.strip():
        st.caption(f"📍 Zona detectada automáticamente: **{mundo.nombre_zona[zona_detectada]}**")

    st.markdown("**2. Triaje automático (sin conocimientos médicos)**")
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
            st.warning("Por favor seleccione o verifique la **Zona del paciente** y el **Motivo de consulta**.")
        elif motivo == "Otro" and not motivo_otro.strip():
            st.warning("Por favor escriba la descripción de lo que le ocurre al paciente.")
        elif not direccion.strip():
            st.warning("Ingrese la **Dirección exacta** para el despacho de la tripulación.")
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
                "direccion": direccion.strip(),
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
            texto_extra=f"Solicitud {sol['id']} — {mundo.nombre_zona[sol['zona']]}",
        )
        st.caption(
            f"**Paciente:** {sol.get('paciente', 'N/A')} ({sol.get('documento', 'N/A')}) | "
            f"**Tel:** {sol.get('telefono', 'N/A')} | **Dirección:** {sol.get('direccion', 'N/A')} | "
            f"**Motivo:** {sol.get('motivo', '')} | **Modificador:** {sol.get('modificador', 'Ninguno')}"
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
        dir_destino_url = urllib.parse.quote(f"{sol['direccion']}, Medellín, Antioquia")
        dir_origen_url = urllib.parse.quote(f"{origen_zona_nombre}, Medellín, Antioquia")
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
                col.metric(f"{x['movil']} {x['tipo']}", f"{x['eta_total']:.0f} min", ROL_TEXTO[x["rol"]])
            st.info(plan["explicacion"])
            for adv in plan["advertencias"]:
                st.warning(adv)

            if plan["ranking"]:
                st.caption("Las 3 mejores alternativas (menor puntaje = mejor):")
                tabla = pd.DataFrame([
                    {
                        "Móvil": o["movil"],
                        "Tipo": o["tipo"],
                        "Opción": o["tipo_opcion"],
                        "Llega en (min)": round(o["eta_total"], 1),
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