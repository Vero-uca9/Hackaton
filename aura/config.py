"""
config.py - Todas las constantes y reglas de negocio en UN solo lugar.
Si quieren cambiar un peso o una regla, se cambia aquí y nada más.
"""
from pathlib import Path

# ---------- Rutas ----------
RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
MODELOS = RAIZ / "modelos"

ARCH_SERVICIOS = DATA / "01_servicios_historicos.json"
ARCH_FLOTA = DATA / "02_moviles_y_bases.json"
ARCH_ZONAS = DATA / "05_zonas_y_tiempos.xlsx"
ARCH_ESCENARIOS = DATA / "06_escenarios_referencia.xlsx"

# ---------- Clasificación EMI (documento 03) ----------
# Prioridad: 1 es lo más urgente. Tiempo objetivo de llegada en minutos.
PRIORIDAD = {"01": 1, "02": 2, "07": 3, "03": 4, "06": 5}
OBJETIVO_MIN = {"01": 15, "02": 20, "07": 45, "03": 90, "06": 180}
NOMBRE_CLASE = {
    "01": "01 - Emergencia (15 min)",
    "02": "02 - Urgencia (20 min)",
    "07": "07 - Priorizado (45 min)",
    "03": "03 - Consulta (90 min)",
    "06": "06 - Consulta banal (180 min)",
}

# ---------- Compatibilidad clasificación x tipo de móvil (documento 03, sección 4) ----------
COMPAT = {
    "01": {"TAM": "PREFERIDA", "TAB": "PERMITIDA", "VMD": "ESTABILIZACION"},
    "02": {"TAM": "RESERVADA", "TAB": "PREFERIDA", "VMD": "ESTABILIZACION"},
    "07": {"TAM": "NO_RECOMENDADA", "TAB": "PERMITIDA", "VMD": "PREFERIDA"},
    "03": {"TAM": "NO_PERMITIDA", "TAB": "NO_RECOMENDADA", "VMD": "PREFERIDA"},
    "06": {"TAM": "NO_PERMITIDA", "TAB": "NO_PERMITIDA", "VMD": "PREFERIDA"},
}
# Cuánto "castigamos" cada nivel de compatibilidad en el puntaje (menor puntaje = mejor)
# RESERVADA = D05: la TAM se guarda para emergencias (solo hay 4); en un 02 se usa si la TAB llega mucho después.
PENAL_COMPAT = {"PREFERIDA": 0.0, "PERMITIDA": 0.25, "RESERVADA": 0.60, "NO_RECOMENDADA": 1.5}

# D06: en un 07, la TAB solo tiene sentido si el caso puede requerir traslado.
MOTIVOS_07_CON_TRASLADO = {"Caídas", "Trauma craneal", "Diarrea y vómitos", "Heridas"}

# ---------- Pesos de la función de puntaje (ajustables) ----------
# puntaje = tiempo*(ETA/objetivo) + costo*(costo/COSTO_REF) + carga*(carga/5) + penalizaciones
# En 01 y 02 el tiempo manda casi por completo; en 03 y 06 pesan más costo y carga.
PESOS = {
    "01": {"tiempo": 1.00, "costo": 0.02, "carga": 0.05, "cobertura": 0.02},
    "02": {"tiempo": 1.00, "costo": 0.10, "carga": 0.10, "cobertura": 0.05},
    "07": {"tiempo": 0.60, "costo": 0.30, "carga": 0.20, "cobertura": 0.10},
    "03": {"tiempo": 0.40, "costo": 0.40, "carga": 0.30, "cobertura": 0.10},
    "06": {"tiempo": 0.30, "costo": 0.50, "carga": 0.30, "cobertura": 0.10},
}
COSTO_REF = 50_000          # COP: costo "típico" de un desplazamiento (para normalizar)
ESPERA_NO_RECOMENDADA = 0.5 # una combinación "no recomendada" (ej. TAB en un 03) solo se usa si el
                            # servicio ya esperó el 50 % de su tiempo objetivo. Así se reservan ambulancias.
PENAL_DESVIO = 0.30         # R06: desviar una móvil en ruta le hace daño al servicio original
UMBRAL_EMPATE_MIN = 3       # D02: si dos opciones difieren menos de 3 min, gana la más barata
VENTAJA_VMD_MIN = 12        # R04: VMD primero si llega 12 min o más antes que la ambulancia
COBERTURA_MIN = 20          # D03: una zona de demanda ALTA debe tener ambulancia a <= 20 min
HORAS_CARGA = 8             # ventana para contar "servicios recientes" de cada móvil

# ---------- Limpieza de datos ----------
# El README avisa de ~2 % de llegadas registradas 60-180 min tarde. Las detectamos así:
# si el tiempo real supera en más de 45 min al estimado por la matriz, es error de registro.
UMBRAL_ATIPICO_MIN = 45
FECHA_CORTE_PRUEBA = "2026-04-16"   # entrenamos con lo anterior, probamos con lo posterior

# ---------- Texto legible de los roles ----------
ROL_TEXTO = {
    "ATENCION": "atención",
    "ATENCION_Y_TRASLADO": "atención y traslado",
    "PRIMER_RESPONDIENTE_ESTABILIZACION": "primer respondiente (estabiliza)",
    "APOYO_MEDICO": "apoyo médico",
    "TRASLADO": "traslado",
}
