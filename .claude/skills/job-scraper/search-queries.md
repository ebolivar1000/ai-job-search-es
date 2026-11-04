# Search Queries for Job Scraper - Everth Bolivar

## Estrategia de Búsqueda y Portales

Este archivo define las búsquedas para `/scrape`. Prioriza vacantes **100% remotas** en español o con inglés técnico escrito/lectura (A2), orientadas a **Senior Data Engineer**, **Analytics Engineer**, **Backend / Full Stack Developer (Python/FastAPI/SQL)** y **ETL / Cloud Data**.

**Reglas de Plataformas:**
- **Plataformas Activas y Confiables:** LinkedIn Jobs, Get on Board (GetOnBrd), Tecnoempleo (Teletrabajo), We Work Remotely, Torre.
- **Plataformas Excluidas:** NO utilizar Upwork, Workana, Freelancer ni bolsas de micro-tareas de baja calidad.

---

## 1. Portales de Búsqueda Principales

- **LinkedIn Jobs:** Cubierto por el CLI `.agents/skills/linkedin-search` y búsquedas WebSearch.
  - Ubicaciones objetivo: `Remote`, `Argentina`, `Latin America`, `Spain`.
- **Get on Board:** `getonbrd.com/jobs` - Portal referente para tecnología en Latinoamérica con roles remotos reales y empresas serias.
- **Tecnoempleo:** `tecnoempleo.com` - Ofertas tech en español con filtro de 100% teletrabajo.
- **We Work Remotely:** `weworkremotely.com` - Plataforma global de empleo remoto directo en ingeniería y datos.

---

## 2. Categorías de Búsqueda por Prioridad

### Prioridad 1: Data Engineering, Cloud & Pipelines ETL (Core)
*Vacantes orientadas a la especialidad principal: arquitecturas de datos, pipelines distribuidos, ETL/ELT y plataformas Cloud.*

#### Consultas LinkedIn CLI:
```bash
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Data Engineer" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Data Engineer" -l "Argentina" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Ingeniero de Datos" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Analytics Engineer" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "ETL Developer" -l "Remote" --remote remote --jobage 14 --format json
```

#### Consultas WebSearch (Get on Board, Tecnoempleo, LinkedIn):
```
site:getonbrd.com/jobs/data-science-analytics "Data Engineer" remoto
site:getonbrd.com/jobs/data-science-analytics "Ingeniero de Datos"
site:getonbrd.com/jobs "AWS" "Data" remoto
site:linkedin.com/jobs "Senior Data Engineer" "Remote" Argentina OR LATAM
site:linkedin.com/jobs "Data Engineer" ("Snowflake" OR "Databricks" OR "Glue" OR "Airflow") remote
site:tecnoempleo.com "Data Engineer" teletrabajo
```

---

### Prioridad 2: Backend Development, Python & APIs (FastAPI / SQL)
*Vacantes de desarrollo backend, APIs RESTful y aplicaciones de datos basadas en Python, SQL avanzado y servicios Cloud.*

#### Consultas LinkedIn CLI:
```bash
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Python Developer" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Python FastAPI" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Backend Developer Python" -l "Argentina" --remote remote --jobage 14 --format json
```

#### Consultas WebSearch (Get on Board & LinkedIn):
```
site:getonbrd.com/jobs/programming "Python" "FastAPI" remoto
site:getonbrd.com/jobs/programming "Backend" "Python" remoto
site:linkedin.com/jobs "Python Backend Developer" "FastAPI" "Remote"
site:linkedin.com/jobs "Full Stack Developer" "Python" "React" remote Argentina
site:weworkremotely.com "Python" "Data" remote
```

---

### Prioridad 3: Big Data, Data Warehousing & Plataformas Corporativas
*Roles especializados en arquitecturas empresariales de datos: Snowflake, Databricks, Redshift, Teradata, Airflow y PowerCenter.*

#### Consultas LinkedIn CLI:
```bash
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Snowflake Data Engineer" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Databricks Engineer" -l "Remote" --remote remote --jobage 14 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Data Warehouse Architect" -l "Remote" --remote remote --jobage 14 --format json
```

#### Consultas WebSearch:
```
site:linkedin.com/jobs "Data Warehouse" ("Redshift" OR "Snowflake" OR "Teradata") remote
site:linkedin.com/jobs "Informatica PowerCenter" remote
site:getonbrd.com/jobs "Data" ("Airflow" OR "Spark") remoto
```

---

## 3. Filtros y Criterios de Selección

- **Modalidad:** 100% Remoto (Home Office permanente).
- **Idioma de Trabajo:** Español o bilingüe técnico con inglés enfocado en lectura/escritura (A2/B1 técnico). Descartar vacantes que exijan inglés C1/C2 nativo hablado fluido con clientes internacionales angloparlantes de forma diaria.
- **Tipo de Contratación:** Empleo directo por la empresa o intermediario corporativo serio (relación de dependencia, contratación de servicios/contractor a mediano/largo plazo).
- **Exclusiones:** Se descartan proyectos de micro-freelance por hora en plataformas estilo Upwork/Workana.
