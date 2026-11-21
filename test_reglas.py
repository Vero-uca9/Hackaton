"""
PRUEBAS AUTOMÁTICAS de las reglas obligatorias.  Ejecutar:  python test_reglas.py
Cada prueba arma una situación pequeña y verifica que AURA haga lo que dicen las reglas.
Si todo está bien, imprime OK en cada línea.
"""
import pandas as pd
from aura.datos import Mundo
from aura.modelo import PredictorETA
from aura import motor

mundo = Mundo()
pred = PredictorETA(mundo)
T0 = pd.Timestamp("2026-04-14 10:00")            # un martes en la mañana


def flota_ocupada():
    """Flota donde TODAS las móviles activas están ocupadas (para armar casos de prueba)."""
    f = motor.crear_flota_base(mundo)
    for m in f:
        if m["estado"] != "FUERA_SERVICIO":
            m["estado"], m["libre_en"] = "EN_ATENCION", 60
    return f


def liberar(flota, id_movil):
    m = next(x for x in flota if x["id"] == id_movil)
    m["estado"], m["libre_en"] = "DISPONIBLE", 0
    return m


# --- 1. Un 06 (consulta banal) nunca recibe ambulancia ---
f = motor.crear_flota_base(mundo)
plan = motor.recomendar({"id": "T1", "clase": "06", "zona": "Z-MED-10-02"}, f, 0, T0, mundo, pred)
assert plan["estado"] == "ASIGNAR" and all(a["tipo"] == "VMD" for a in plan["asignaciones"])
print("OK 1  un 06 solo recibe VMD")

# --- 2. Una móvil FUERA_SERVICIO jamás se asigna (R05) ---
f = motor.crear_flota_base(mundo)
fuera = [m["id"] for m in f if m["estado"] == "FUERA_SERVICIO"]
assert fuera, "debería haber móviles en mantenimiento en el archivo 02"
for z in list(mundo.zonas.id_zona)[:20]:
    plan = motor.recomendar({"id": "T2", "clase": "03", "zona": z}, f, 0, T0, mundo, pred)
    assert not any(a["movil"] in fuera for a in plan["asignaciones"])
print("OK 2  nunca se asigna una móvil fuera de servicio:", fuera)

# --- 3. Un 01 con TODAS las ambulancias ocupadas: VMD primero + ambulancia preasignada (R04) ---
f = flota_ocupada()
liberar(f, "MOV-015")                                             # una VMD libre en Base Norte
plan = motor.recomendar({"id": "T3", "clase": "01", "zona": "Z-MED-03-02"}, f, 0, T0, mundo, pred)
roles = [a["rol"] for a in plan["asignaciones"]]
assert roles[0] == "PRIMER_RESPONDIENTE_ESTABILIZACION" and "ATENCION_Y_TRASLADO" in roles
print("OK 3  sin ambulancia libre -> VMD estabiliza y se preasigna una ambulancia:", roles)

# --- 4. Un 01 donde no hay NADA disponible queda en cola (R01) ---
f = motor.crear_flota_base(mundo)
for m in f:
    m["estado"] = "FUERA_SERVICIO"
plan = motor.recomendar({"id": "T4", "clase": "01", "zona": "Z-MED-03-02"}, f, 0, T0, mundo, pred)
assert plan["estado"] == "EN_COLA"
print("OK 4  sin móviles elegibles -> el servicio queda en cola")

# --- 5. Desvío (R06): una VMD que va a una consulta se desvía a una urgencia cercana ---
f = flota_ocupada()
vmd = liberar(f, "MOV-015")
consulta = {"id": "CONSULTA-X", "clase": "03", "zona": "Z-MED-04-02"}
vmd.update({"estado": "EN_RUTA", "llegada_en": 25, "libre_en": 60, "asignado_a": "CONSULTA-X",
            "clase_asignada": "03", "sol": consulta})
plan = motor.recomendar({"id": "T5", "clase": "02", "zona": "Z-MED-04-01"}, f, 5, T0, mundo, pred)
assert plan["asignaciones"][0]["tipo_opcion"] == "DESVIO"
a_cola = motor.aplicar_plan(plan, {"id": "T5", "clase": "02", "zona": "Z-MED-04-01"}, f, 5, {})
assert a_cola and a_cola[0]["id"] == "CONSULTA-X"
print("OK 5  desvío en ruta: la consulta original vuelve a la cola")

# --- 6. Confirmar un despacho cambia el estado y aumenta la carga ---
f = motor.crear_flota_base(mundo)
sol = {"id": "T6", "clase": "03", "zona": "Z-MED-10-02"}
plan = motor.recomendar(sol, f, 0, T0, mundo, pred)
elegida = plan["asignaciones"][0]["movil"]
motor.aplicar_plan(plan, sol, f, 0, {})
m = next(x for x in f if x["id"] == elegida)
assert m["estado"] == "EN_RUTA" and m["carga"] == 1
motor.actualizar_flota(f, 500)                                    # mucho después: vuelve a quedar libre
assert m["estado"] == "DISPONIBLE" and m["zona"] == "Z-MED-10-02"
print("OK 6  al confirmar, la móvil pasa a EN_RUTA; luego queda DISPONIBLE en la zona del servicio")

print("\nTodas las pruebas pasaron.")
