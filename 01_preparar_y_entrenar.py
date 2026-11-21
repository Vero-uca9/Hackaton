"""
PASO 1 y 2: limpia los datos, entrena el modelo de tiempos y lo compara con la fórmula.
Ejecutar:  python 01_preparar_y_entrenar.py
"""
import json
from aura.config import MODELOS
from aura.datos import Mundo, tabla_viajes, duraciones_servicio
from aura import modelo

mundo = Mundo()
viajes = tabla_viajes(mundo)
print(f"Viajes analizados: {len(viajes)}")
print(f"Errores de registro detectados (atípicos): {viajes.atipico.sum()} "
      f"({viajes.atipico.mean():.1%})  -> se excluyen del entrenamiento")

tabla, info, final = modelo.entrenar_y_evaluar(mundo, viajes)
print(f"\nEntrenado con {info['n_entrena']} viajes, probado con {info['n_prueba']} que NO vio.\n")
print(tabla.to_string(index=False))

mejor = tabla.iloc[2].error_medio_min < tabla.iloc[0].error_medio_min
print("\nConclusión:", "el ML mejora a la fórmula del README." if mejor
      else "el ML NO supera a la fórmula; usar la fórmula con ajuste.")

modelo.guardar(final)
MODELOS.mkdir(exist_ok=True)
dur = duraciones_servicio(viajes)
with open(MODELOS / "duraciones.json", "w") as f:
    json.dump({f"{k[0]}|{k[1]}": round(v, 1) for k, v in dur.items()}, f, indent=1)
tabla.to_csv(MODELOS / "resultados_modelo.csv", index=False)
print("\nGuardado en la carpeta 'modelos/'.")
