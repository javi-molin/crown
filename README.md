# 👑 CROWN

Panel en vivo para una cuenta de TikTok/Instagram sobre concursos de belleza.

**Ver el panel:** https://javi-molin.github.io/crown/

## Qué hay adentro

| Pestaña | Para qué sirve |
|---|---|
| En vivo | Cuenta regresiva, agenda en hora Chile, feed de noticias etiquetado (concurso, candidata, polémica, looks, resultados), resultados en vivo desde Wikipedia, candidatas más mencionadas |
| Concursos | Ficha de cada concurso 2026: sede, fechas, formato, dónde verlo, ganadoras, polémicas con fuente |
| Candidatas | Todas las candidatas de Miss Universe y Miss International por país, con accesos a IG, TikTok, looks, YouTube, noticias, X y Pinterest. Favoritas y ranking propio |
| Looks y videos | Últimos videos de canales oficiales y de YouTube en general, transmisión en vivo, TikTok oficial, accesos a hashtags |
| Polémicas | Polémicas documentadas + las detectadas automáticamente en noticias |
| Estudio del nicho | Auditoría de cuentas de concursos (qué publican, qué funciona) |
| Contenido | Calendario, banco de ideas con guion, y guiones automáticos con las noticias del día |
| Grabar | Teleprompter (velocidad, tamaño, espejo, pantalla completa) |
| Fuentes | Estado de cada fuente consultada por el robot |

## Cómo se actualiza

- `scripts/update.py` corre en **GitHub Actions cada ~10 minutos** (`.github/workflows/update.yml`) y escribe los JSON de `data/`.
- El panel vuelve a leer `data/` cada 60 segundos.
- Para forzar una actualización: **Actions → Actualizar datos CROWN → Run workflow**.

## Editar datos a mano

- `data/pageants.json`: concursos, fechas, polémicas.
- `data/contestants.json`: candidatas. Para agregar el Instagram de una candidata, añade `"ig": "usuario"` en su ficha.
- `data/estudio.json` y `data/contenido.json`: estudio del nicho e ideas de contenido.
