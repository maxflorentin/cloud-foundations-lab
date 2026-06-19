# Decision log

## Formato

```text
Decision:
Contexto:
Alternativas:
Tradeoff:
Resultado:
```

## Decisiones

### 001 - Laboratorios locales

Decision: usar Docker Compose, MinIO y LocalStack en lugar de cuentas AWS personales.

Contexto: evitar costos accidentales y reducir friccion de setup.

Tradeoff: no se practica consola AWS real en profundidad.

Resultado: los labs son reproducibles y reutilizables.

### 003 - Formato de eventos crudos

Decision: JSONL (JSON Lines) para data/raw/events.jsonl.

Contexto: los eventos se generan uno por vez. JSONL permite procesar con streaming
sin cargar todo el archivo en memoria, y es fácil de appender.

Alternativas: JSON array, CSV, Parquet.

Tradeoff: JSONL no es legible de un vistazo como un JSON array formateado.
Parquet sería más eficiente a escala, pero requiere dependencias externas.

Resultado: JSONL para raw. CSV para processed (compatibilidad analítica máxima).

### 004 - Pipeline de procesamiento

Decision: script Python (process_events.py) lee JSONL y escribe JSON filtrado.

Contexto: necesitamos filtrar un subconjunto de eventos GitHub Archive para análisis.
El script es reproducible: misma entrada, misma salida, sin efectos secundarios.

Tradeoff: un script por transformación vs una sola función general.
Elegimos un script por transformación: más legible, más fácil de testear.

Resultado: process_events.py → data/processed/push_events.json (filtra PushEvent)

### 002 - Entorno de desarrollo

Decision: GitHub Codespaces.

Contexto: el grupo no tiene instalaciones homogéneas (mix de macOS, Windows y Linux).
Codespaces ofrece el mismo entorno para todos sin configuración local.

Alternativas: Docker Desktop local, WSL2, máquina virtual.

Tradeoff: depende de conectividad y de los free-tier hours disponibles (60 hs/mes por cuenta).
Con Docker local se trabaja offline y sin límite de tiempo.

Resultado: Codespaces para las clases, Docker local como fallback documentado en el README.
### 005 - DuckDB sobre archivo JSON vs carga en PostgreSQL

Decision: Consultar el archivo de eventos directamente con DuckDB en lugar de cargarlo en PostgreSQL.

Contexto: Una vez procesados los eventos de GitHub, necesitamos analizarlos para ver qué repositorios tuvieron más actividad. Los datos ya están guardados en un archivo JSON en nuestra computadora.

Alternativas:
- Levantar PostgreSQL, crear una tabla, cargar el archivo y recién ahí consultarlo.
- Usar DuckDB que lee el archivo directo, como si fuera una planilla de Excel, sin pasos previos.

Tradeoff: PostgreSQL es más potente y escala mejor para grandes volúmenes, pero requiere más pasos y tener el servicio corriendo. DuckDB es más simple y rápido para explorar datos, pero no es ideal si los datos crecen mucho.

Resultado: Para explorar archivos de datos de forma rápida y sin infraestructura, DuckDB es la mejor opción. En AWS esto sería equivalente a usar Athena para consultar archivos guardados en S3, sin necesidad de cargar nada en una base de datos.