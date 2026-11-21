"""
PASO 4: corre los 14 escenarios con AURA y compara contra el despachador.
Ejecutar:  python 02_evaluar_escenarios.py            (todos)
           python 02_evaluar_escenarios.py ESC-04     (uno solo, para ver el detalle)
Requiere haber ejecutado antes 01_preparar_y_entrenar.py
"""
import sys
import pandas as pd
from aura.config import RAIZ
from aura.datos import Mundo, historial_asignaciones
from aura.modelo import PredictorETA
from aura.simulador import cargar_duraciones, correr_todo, resumen

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 120)

mundo = Mundo()
predictor = PredictorETA(mundo)
ids = sys.argv[1:] or None
df, violaciones = correr_todo(mundo, predictor, cargar_duraciones(), historial_asignaciones(), ids)

salidas = RAIZ / "salidas"
salidas.mkdir(exist_ok=True)
df.to_csv(salidas / "comparacion_por_solicitud.csv", index=False)

if ids:  # detalle de un escenario
    cols = ["solicitud", "clase", "desp_movil", "desp_tr_min", "aura_movil", "aura_tr_min", "aura_explicacion"]
    print(df[cols].to_string(index=False))
    sys.exit()

r = resumen(df)
r.to_csv(salidas / "resumen_por_clase.csv")
print("\n=== AURA vs DESPACHADOR (tiempo de respuesta medio en min, % que cumple objetivo, costo COP, km) ===")
print(r.to_string())
d = df.dropna(subset=["aura_tr_min"])
print(f"\nSolicitudes comparadas: {len(d)} de {len(df)}")
print(f"Costo medio por servicio  -> despachador: {d.desp_costo.mean():,.0f}   AURA: {d.aura_costo.mean():,.0f}")
print(f"Km medios por servicio    -> despachador: {d.desp_km.mean():.1f}   AURA: {d.aura_km.mean():.1f}")
print(f"Violaciones de reglas obligatorias de AURA: {len(violaciones)}")
for v in violaciones:
    print("  ", v)
