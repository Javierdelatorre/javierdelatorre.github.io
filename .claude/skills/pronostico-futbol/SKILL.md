---
name: pronostico-futbol
description: Pronósticos de fútbol y análisis de apuestas con modelo estadístico (Poisson bivariante con corrección Dixon-Coles) para Champions League, Europa League, Conference League, ligas nacionales y selecciones, cubriendo todos los mercados que ofrecen las casas - 1X2, doble oportunidad, empate no válido, hándicap asiático y europeo, over/under, goles por equipo, ambos marcan, marcador exacto, descanso/final, primera y segunda parte, gana a cero, par/impar, margen de victoria, primer goleador y goleadores, córners, tarjetas y clasificación en eliminatorias. Usa esta skill siempre que el usuario pida un pronóstico, predicción, pick, "quién gana", probabilidad, cuota justa, value bet, stake, análisis previo, combinada, "qué apostar" o "cómo ves el partido" para cualquier partido, jornada o competición de fútbol, aunque no mencione la palabra apuesta. Incluye la calculadora determinista scripts/mercados.py, que debe usarse para todas las probabilidades en vez de estimarlas a ojo.
---

# Pronóstico de fútbol: todos los mercados, un solo modelo

## Idea central

Todo pronóstico de esta skill sale de dos números por partido: los **goles esperados a 90
minutos** de cada equipo (λ local y λ visitante). Con ellos, `scripts/mercados.py` construye la
distribución conjunta de marcadores (Poisson bivariante con corrección Dixon-Coles para los
marcadores bajos) y de ahí deriva **todos** los mercados de una vez: 1X2, hándicaps, totales,
ambos marcan, marcador exacto, descanso/final, mitades, goleadores, clasificación en
eliminatorias... La ventaja de hacerlo así es la coherencia: si el modelo dice 48 % de victoria
local, el hándicap -0.5, el "gana a cero" y el marcador exacto están alineados con ese 48 %, y
el usuario puede cruzar cualquier mercado con cualquier otro sin contradicciones.

El trabajo del analista (tú) no es "adivinar el resultado", sino **estimar bien esas λ,
compararlas con lo que el mercado ya descuenta y decidir si hay valor**. Una apuesta tiene
valor cuando `probabilidad × cuota > 1` con margen suficiente; el resultado de un partido
concreto no dice nada sobre la calidad del pronóstico, la muestra larga sí.

## Principios que no se negocian

- **Probabilidades, nunca certezas.** No existen "fijas" ni "apuestas seguras"; si el usuario
  las pide, explica por qué no existen y ofrécele lo que sí hay: estimaciones calibradas y
  valor esperado. No infles la confianza para sonar más útil.
- **El mercado es el punto de partida.** Las cuotas de cierre de las casas grandes están entre
  los mejores pronosticadores que existen. Cuando haya cuotas, úsalas para calibrar
  (`--desde-cuotas`) o mezclarlas (`--peso-mercado`) y busca el valor en lo que el mercado
  suele descontar peor: mercados secundarios, noticias de última hora (alineaciones, bajas,
  rotaciones europeas), diferencias entre casas y líneas asiáticas de cuarto.
- **Cada ajuste, explicado y acotado.** Todo cambio sobre el λ base (bajas, rotación,
  motivación, ida/vuelta) se aplica con `--factor-local/--factor-visitante`, se justifica en
  una línea y no supera en total ±25 %. Si te ves aplicando más, es que el λ base está mal.
- **Fuentes y fecha.** Indica siempre de qué fecha son los datos y qué no has podido
  comprobar (por ejemplo, alineaciones no confirmadas). Un pronóstico sin fecha es inútil dos
  días después.
- **Gestión de banca conservadora.** Kelly fraccional (0.25 por defecto), stake máximo 3 % de la
  banca y solo selecciones con EV ≥ 3 %. Recuerda al usuario que apostar tiene riesgo real de
  pérdida y que el registro de resultados (CLV) es la única forma de saber si el proceso
  funciona.

## Flujo de trabajo

### 1. Encuadrar el partido

Antes de buscar nada, fija: competición y fase, fecha y hora, sede real (neutral en finales),
y **cómo se liquida cada mercado**. En Champions/Europa/Conference League:

| Fase | 1X2, O/U, hándicaps, etc. | Mercados de clasificación |
|---|---|---|
| Fase liga (8 jornadas, 36 equipos) | 90 minutos + descuento | No aplica |
| Play-off y eliminatorias a ida y vuelta | 90 minutos del partido | Global tras 180' + prórroga + penaltis. **Sin gol de visitante** (UEFA lo abolió en 2021-22) |
| Final | 90 minutos | Prórroga + penaltis (`--eliminatoria unico`) |

Detalle que cambia λ en la fase liga: desde la jornada 6-7 hay equipos ya clasificados
(rotan) y equipos sin opciones, y las posiciones 1-8 (pase directo) frente a 9-24 (play-off)
crean incentivos muy distintos. Mira la tabla antes de fijar factores.

### 2. Recopilar datos (lee `references/fuentes.md` para URLs y comandos)

Qué necesitas, por orden de impacto en el pronóstico:

1. **Cuotas actuales** (1X2, O/U 2.5, hándicap asiático principal, ambos marcan) de al menos
   una casa grande o Pinnacle. Son la mejor referencia de fuerza relativa.
2. **Rating de fuerza**: Elo de club (ClubElo) o xG a favor/en contra por partido en la
   temporada (FBref/Understat/Sofascore) y la media de la competición.
3. **Alineaciones probables, bajas y sanciones** (Transfermarkt, prensa del día, WebSearch).
4. **Contexto**: descanso desde el último partido, viaje, importancia del partido para cada uno,
   resultado de la ida, estilo (ritmo de córners y tarjetas si vas a esos mercados).
5. **Forma reciente** con xG, no con resultados: cinco partidos de resultados son ruido.

**Modo restringido.** Si `WebFetch`/`curl` están bloqueados (pasa en entornos remotos con
red limitada; en la sesión donde se creó esta skill solo funcionaban `WebSearch` y
`raw.githubusercontent.com`), trabaja con: `WebSearch` para cuotas, bajas y noticias
(los fragmentos de resultados suelen incluir cuotas 1X2 y O/U), los ficheros de
openfootball para calendario y resultados, los datos que aporte el usuario, y tu propio
conocimiento de la fuerza relativa (dilo explícitamente y con una fecha de referencia). Nunca
inventes una cuota ni una alineación: si no la tienes, deja el hueco y pide el dato.

### 3. Estimar λ (lee `references/modelo.md` si dudas sobre parámetros)

Elige la vía según lo que tengas, de mejor a peor:

| Situación | Comando base | Notas |
|---|---|---|
| Tienes cuotas 1X2 (+ O/U) de una casa fiable | `--desde-cuotas O1 OX O2 --cuotas-ou OV UN --linea-ou 2.5` | Invierte el mercado y obtiene λ ya calibradas. Después aplica solo ajustes por información que el mercado aún no descuente (noticias de última hora) |
| Tienes Elo de ambos | `--elo-local E1 --elo-visitante E2 --total T` | Ventaja local por defecto 65 puntos (~+0.3 goles). `--total` = goles medios de la competición ajustados al perfil del cruce (ver modelo.md) |
| Tienes xG a favor/en contra y la media de la liga | `--fuerzas ATA_L DEF_L ATA_V DEF_V --media-local ML --media-visitante MV` | Fuerzas relativas: ataque = xG a favor por partido / media; defensa = xG en contra / media. Usa medias local/visitante de la competición |
| Tienes λ de un modelo propio o de otra fuente | `--xg-local --xg-visitante` | Di de dónde salen |

Ajustes contextuales orientativos (multiplican λ; anótalos siempre en el informe):

| Factor | Efecto típico |
|---|---|
| Baja del máximo goleador o creador principal | ataque ×0.90-0.95 |
| Baja del portero o del central titular | defensa rival ×1.05-1.10 (es decir, λ del rival sube) |
| Rotación amplia (≥5 cambios) por prioridad de otra competición | ataque ×0.85-0.92, λ rival ×1.05 |
| Vuelta con eliminatoria sentenciada (3+ goles) | ambos ×0.85-0.95 y menos supremacía |
| Necesidad de marcar (vuelta, última jornada) | total ×1.05-1.10; supremacía hacia quien necesita |
| Viaje largo + menos de 72 h de descanso | ×0.95 |
| Final en sede neutral | ventaja local 0 (Elo: `--ventaja-local 0`) |

Los ajustes se justifican con hechos verificables (una lista de bajas con fuente), no con
narrativas del tipo "llegan motivados". Si ya has partido de las cuotas, el mercado normalmente
ya incluye las bajas conocidas desde hace días; solo ajusta por lo nuevo.

### 4. Ejecutar la calculadora

```bash
python3 .claude/skills/pronostico-futbol/scripts/mercados.py \
  --desde-cuotas 2.10 3.50 3.60 --cuotas-ou 1.90 1.95 \
  --factor-local 0.95 \
  --local "Atlético" --visitante "Man United" \
  --cuotas '{"1x2.1":2.10,"1x2.X":3.50,"1x2.2":3.60,"ou.2.5.over":1.90,"ou.2.5.under":1.95,"btts.si":1.75,"btts.no":2.05,"ah.local.-0.25":1.95,"ah.visitante.+0.25":1.95}' \
  --banca 1000 --kelly 0.25 --ev-min 0.03
```

- La salida Markdown (`--formato md`, por defecto) ya está lista para pegar en el informe;
  `--formato json` sirve para procesar. `--solo 1x2,ah,ou,btts` limita los grupos y
  `--todas-lineas` muestra también las líneas extremas.
- Las claves de las cuotas son las que imprime la columna **Clave** (`1x2.1`, `ou.2.5.over`,
  `ah.local.-0.75`, `tt.visitante.1.5.over`, `htft.1/1`, `cs.2-1`...). Pasa siempre todas las
  cuotas de un mismo mercado (los tres del 1X2, over y under...) para que el script pueda
  quitar el margen de la casa y calcular la probabilidad justa del mercado.
- `--eliminatoria vuelta --ida 1-2` añade clasificación, prórroga y penaltis; la ida se escribe
  como goles del local de hoy - goles del visitante de hoy en aquel partido.
- Córners y tarjetas no se derivan de los goles: pásales medias por equipo o total
  (`--corners-local 5.8 --corners-visitante 4.4 --tarjetas-total 4.6`) estimadas a partir de
  los datos de ambos equipos y del árbitro. Goleadores: `--goleadores-local "Nombre:cuota_goles:minutos"`
  donde cuota_goles es la fracción de los goles del equipo que marca ese jugador y minutos los
  que se espera que juegue (prefijo `+` si sale desde el banquillo).
- Ejecuta el script siempre; no estimes probabilidades de cabeza ni las redondees "a ojo".
  Si vas a analizar una jornada entera, lanza un comando por partido y resume.

### 5. Decidir el valor y el stake

- Una selección se recomienda si **EV ≥ 3 %** (`--ev-min`) y probabilidad del modelo ≥ 5 %.
  Con cuotas altas (> 4.0) exige más EV (≥ 6 %): el error del modelo pesa más ahí.
- Stake = Kelly × fracción (0.25) con tope del 3 % de la banca. Dos selecciones del mismo
  partido están correlacionadas: si recomiendas varias, reduce cada stake o quédate con la de
  mayor EV.
- Cuando el usuario no aporta cuotas, entrega la **cuota mínima** de cada mercado (columna
  "Cuota mín.") para que compare él con su casa. Cuando las aporta, compáralas también con la
  probabilidad justa del mercado (columna "Prob. mercado"): si el modelo se separa más de 10
  puntos del mercado en el 1X2, sospecha del modelo antes que de la casa y revisa λ.
- Combinadas: multiplica probabilidades solo si los eventos son de partidos distintos; dentro
  del mismo partido usa la matriz (por ejemplo "1 y más de 2.5" ya está en `res_ou`). El margen
  de la casa se multiplica en cada tramo, así que casi nunca hay valor en combinadas largas.

### 6. Escribir el informe

Usa esta estructura (en el idioma del usuario) y no la infles con relleno:

```
# [Local] vs [Visitante] — [competición, fase, fecha, hora, sede]

## Datos usados
- Fecha de consulta y fuentes (con enlaces si los hay). Qué falta o no está confirmado.
- Cuotas de referencia (casa, hora de captura).

## Lectura del partido (5-8 líneas)
- Fuerza relativa (Elo/xG), bajas confirmadas, contexto de tabla o eliminatoria, estilo.
- λ base, ajustes aplicados con su justificación y λ finales.

## Probabilidades del modelo
- Resumen: 1X2, marcador más probable, más de 2.5, ambos marcan (tabla corta).
- Tablas de mercados relevantes para lo que pidió el usuario (pega la salida del script,
  recortada con --solo si no pidió "todos").

## Selecciones con valor
| Mercado | Selección | Cuota | Prob. modelo | EV | Stake |
- Si no hay valor con las cuotas dadas, dilo y ofrece las cuotas mínimas.

## Riesgos y por qué podría fallar
- Dos o tres factores concretos (alineación pendiente, mercado muy eficiente, muestra corta).

## Aviso
Una frase: estimaciones probabilísticas, apostar implica riesgo real, solo dinero que se
pueda perder, registrar y evaluar por cuota de cierre.
```

Para una **jornada completa**, haz una tabla resumen (partido, 1X2 modelo, cuota, EV de la
mejor selección) y desarrolla solo los dos o tres partidos con más valor o los que el usuario
pida; el resto, en la tabla.

### 7. Registrar y aprender

Propón al usuario un registro (`apuestas.csv`: fecha, partido, mercado, selección, cuota
tomada, cuota de cierre, stake, resultado, beneficio). El **CLV** (cuota tomada frente a cuota
de cierre) es la señal más rápida de si el proceso gana valor; el beneficio a corto plazo es
casi todo varianza. Si el usuario ya tiene registro, revisa calibración (Brier/log-loss por
tramo de probabilidad) antes de cambiar el modelo.

## Cuándo abstenerse o rebajar la confianza

- Alineaciones sin confirmar en un partido con rotaciones probables (fase liga con equipos ya
  clasificados, ida de eliminatoria con derbi el fin de semana).
- Cuotas muy alejadas del modelo (más de 10 puntos en el 1X2) sin una explicación que puedas
  verificar: casi siempre es información que el mercado tiene y tú no.
- Mercados con poca liquidez y margen alto (marcador exacto, goleadores, tarjetas): el EV
  aparente suele ser margen de error del modelo. Exige EV mayor y stake menor.
- Muestras cortas de temporada (primeras 3-4 jornadas): pondera Elo y xG de la temporada
  anterior más que la forma actual.
- Partidos de equipos que no conoces bien (rivales de fases previas, ligas pequeñas): sé
  explícito con la incertidumbre y apóyate en el mercado.

## Referencias de la skill

- `references/mercados.md`: catálogo de todos los mercados, reglas de liquidación (líneas de
  cuarto, devoluciones, prórroga) y cómo los calcula el script. Léelo cuando el usuario pregunte
  por un mercado concreto o poco habitual.
- `references/modelo.md`: fundamentos del modelo (Poisson, Dixon-Coles y ρ, Elo a λ, xG a
  fuerzas, mitades, prórroga y penaltis, córners y tarjetas, goleadores), valores por defecto y
  cómo calibrar y validar. Léelo antes de cambiar parámetros o cuando necesites justificar el
  método.
- `references/fuentes.md`: dónde conseguir cada dato (URLs, APIs con y sin clave, comandos
  `curl`, qué funciona en entornos con red restringida) y consultas de `WebSearch` que
  devuelven cuotas y bajas. Léelo al empezar la recopilación de datos.
- `scripts/mercados.py --help`: todas las opciones de la calculadora.
