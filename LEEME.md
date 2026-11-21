# AURA - Asignación inteligente de móviles (prototipo académico)

Simulación aislada con datos FICTICIOS del reto EstudIA (Grupo EMI - Falck). No se conecta a ningún sistema real.
NO subir este proyecto ni los datos a un repositorio público (ver acuerdo de confidencialidad del reto).

## Instalación (una sola vez)
1. Instalar Python 3.10 o superior (marcar "Add Python to PATH" en Windows).
2. Abrir una terminal EN ESTA CARPETA y ejecutar:
       python -m venv venv
       venv\Scripts\activate          (Windows)      |   source venv/bin/activate   (Mac/Linux)
       pip install -r requirements.txt
3. Copiar a la carpeta `data/` los archivos del reto (están en el zip que les entregaron):
       01_servicios_historicos.json   02_moviles_y_bases.json
       05_zonas_y_tiempos.xlsx        06_escenarios_referencia.xlsx

## Uso (en este orden)
    python 01_preparar_y_entrenar.py     # limpia datos, entrena el modelo de tiempos, lo compara con la fórmula
    python test_reglas.py                # pruebas automáticas de las reglas obligatorias
    python 02_evaluar_escenarios.py      # AURA vs despachador en los 14 escenarios
    streamlit run app.py                 # abre la aplicación en el navegador

## Estructura
    aura/config.py      reglas de negocio y pesos (aquí se ajusta todo)
    aura/datos.py       carga y limpieza de datos
    aura/modelo.py      modelo de Machine Learning para el tiempo de viaje
    aura/motor.py       reglas obligatorias, puntaje, recomendación y explicación
    aura/simulador.py   repetición de los 14 escenarios y comparación
    app.py              aplicación Streamlit
