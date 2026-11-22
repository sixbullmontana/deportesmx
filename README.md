# Liga MX Analytics

Dashboard estático para GitHub Pages con una base de datos propia que se actualiza sola.

## Estructura
- `index.html`: la página (lee `data/*.json` y, si falta algo, consulta ESPN en vivo).
- `scripts/build_data.py`: genera la base de datos (solo librería estándar de Python).
- `.github/workflows/update-data.yml`: ejecuta el script cada día a las 09:00 UTC y guarda los cambios.
- `data/`: resultado generado (`matches.json`, `teams.json`, `details.json`, `meta.json`).
- `data/raw/`: aquí puedes soltar CSV propios de resultados (por ejemplo el dataset CC0 "LigaMX" de Kaggle).

## Puesta en marcha
1. Sube todo el contenido de esta carpeta a tu repositorio (incluida la carpeta oculta `.github`).
2. En Settings → Pages elige la rama `main`, carpeta `/ (root)`.
3. En Settings → Actions → General activa "Read and write permissions" para el flujo de trabajo.
4. En la pestaña Actions abre "Actualizar datos Liga MX" y pulsa Run workflow. Tarda unos minutos la primera vez.
5. Cuando termine verás los archivos en `data/` y la pestaña Históricos de la página con datos.

## Qué contiene la base de datos
- **Resultados históricos:** CSV abiertos de footballcsv (licencia CC0) y los que pongas en `data/raw/`.
- **Torneos recientes (desde 2024):** ESPN, con formaciones, estadísticas de equipo y de jugador por partido.
- Para cambiar el año inicial de ESPN define la variable `ESPN_FROM_YEAR`; para usar otro repositorio de CSV, `CSV_REPOS` (separados por coma).

## Límites
- Los CSV históricos traen marcadores, no jugadores ni tarjetas. El detalle por jugador existe solo para los torneos tomados de ESPN.
- ESPN no es una API oficial y puede cambiar sin aviso.
- No hay datos de "potencial" ni de jugadas ensayadas en ninguna fuente abierta.
