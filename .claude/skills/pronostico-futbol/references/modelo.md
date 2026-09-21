# El modelo: fundamentos, parámetros por defecto y cómo validarlo

Tabla de contenidos: [Por qué Poisson](#1-por-qué-una-poisson-bivariante-con-corrección-dixon-coles) ·
[ρ](#2-el-parámetro-ρ) · [Ventaja local y totales](#3-ventaja-local-y-goles-por-partido-de-referencia) ·
[Desde cuotas](#4-λ-desde-las-cuotas-del-mercado) · [Desde Elo](#5-λ-desde-elo) · [Desde xG](#6-λ-desde-xg-fuerzas-de-ataque-y-defensa) ·
[Ajustes](#7-ajustes-contextuales) · [Mitades](#8-mitades) · [Prórroga](#9-prórroga-y-penaltis) ·
[Córners y tarjetas](#10-córners-y-tarjetas) · [Goleadores](#11-goleadores) · [Valor y banca](#12-valor-margen-y-gestión-de-banca) ·
[Validación](#13-calibración-validación-y-cuánta-muestra-hace-falta) · [Límites](#14-límites-del-modelo)

## 1. Por qué una Poisson bivariante con corrección Dixon-Coles

Los goles de cada equipo se comportan aproximadamente como una Poisson con media igual a sus
goles esperados. Un modelo Poisson independiente (Maher, 1982) ya reproduce bien la mayoría de
mercados, pero infravalora el 0-0 y el 1-1 y sobrevalora el 1-0 y el 0-1. Dixon y Coles (1997)
corrigieron esas cuatro celdas con un factor τ que depende de un parámetro ρ:

```
P(x, y) = τ(x, y) · Poisson(x; λ_local) · Poisson(y; λ_visitante)
τ(0,0) = 1 - λ_l·λ_v·ρ     τ(0,1) = 1 + λ_l·ρ
τ(1,0) = 1 + λ_v·ρ         τ(1,1) = 1 - ρ        τ = 1 en el resto
```

Con ρ negativo suben el 0-0 y el 1-1 y bajan el 1-0 y el 0-1 (la suma total no cambia). Es el
modelo estándar de la industria para derivar todos los mercados de un partido a partir de dos λ,
y por eso las cuotas de una casa son internamente coherentes: hacen exactamente esto.

## 2. El parámetro ρ

- Por defecto `-0.06`. Los ajustes publicados sobre ligas europeas dan valores entre -0.03 y
  -0.13; en competiciones con muchos goles (fase liga de la Champions) el efecto es menor.
- Solo afecta a los marcadores 0-0, 1-0, 0-1 y 1-1; en la práctica mueve el empate 1-2 puntos y
  apenas toca los totales por encima de 2.5.
- El script recorta ρ automáticamente si con las λ dadas alguna probabilidad quedara negativa
  (avisa por `stderr`).
- Si tienes cuotas del mercado, puedes estimar el ρ implícito: ajusta ρ hasta que el 0-0 y el 1-1
  del modelo coincidan con las cuotas de marcador exacto de la casa (una vez quitado el margen).

## 3. Ventaja local y goles por partido de referencia

- Ventaja local en goles de supremacía: en las grandes ligas ronda +0.30/+0.40 goles; en
  Champions y Europa League es parecida pero varía mucho por club (estadios con público muy
  hostil, viajes largos al este de Europa). En puntos Elo equivale a unos 60-100; el script usa
  65 por defecto (`--ventaja-local`). En finales en sede neutral, 0.
- Goles por partido: la fase liga de la Champions ha promediado entre 3.1 y 3.3 goles en sus dos
  primeras ediciones; Europa League y Conference League suelen quedarse entre 2.8 y 3.0;
  las eliminatorias bajan a 2.6-2.9. **Comprueba el dato de la temporada en curso** antes de
  usar `--total` o las medias local/visitante; estos números son referencias, no verdades.
- Reparto local/visitante de esos goles: aproximadamente 55 % / 45 % (`--media-local 1.65
  --media-visitante 1.35` suman 3.0 con esa proporción).

## 4. λ desde las cuotas del mercado

`--desde-cuotas O1 OX O2 [--cuotas-ou OVER UNDER --linea-ou 2.5]` hace lo siguiente:

1. Quita el margen de las cuotas con el **método de la potencia** (por defecto): busca el
   exponente k tal que Σ (1/cuota)^k = 1. Frente al reparto proporcional, este método asigna
   más margen a las cuotas altas, que es lo que hacen las casas (sesgo favorito-longshot).
   `--metodo-margen multiplicativo` usa el reparto proporcional.
2. Convierte las probabilidades justas en una **expectativa** E = P(1) + 0.5·P(X) y busca la
   supremacía (λ_l - λ_v) que la reproduce.
3. Busca el total (λ_l + λ_v) que reproduce la probabilidad justa del over (o, si no hay
   cuotas O/U, la probabilidad de empate, que también depende del total).
4. Itera 2 y 3 hasta converger.

Úsalo con cuotas de una casa de margen bajo (Pinnacle, o el mejor precio del mercado) y lo más
cercanas posible al cierre. Las λ resultantes ya incluyen todo lo que el mercado sabe (bajas
anunciadas, rotaciones esperadas, motivación): solo ajusta por información posterior a las
cuotas capturadas. Si el modelo y el mercado difieren más de 10 puntos en el 1X2 después de tu
ajuste, lo más probable es que tu ajuste esté mal.

## 5. λ desde Elo

`--elo-local E1 --elo-visitante E2 --ventaja-local 65 --total T`:

- Expectativa Elo del local: `E = 1 / (1 + 10^(-(E1 + ventaja - E2) / 400))`.
- Se busca la supremacía que hace que P(1) + 0.5·P(X) = E con el total T fijo; de ahí salen
  λ_l = (T + s)/2 y λ_v = (T - s)/2.
- Elo de club (ClubElo) ya está calibrado entre ligas, lo que lo hace especialmente útil en
  competición europea, donde comparar xG de ligas distintas es engañoso. Diferencias de
  referencia: 100 puntos ≈ 64 % de expectativa; 200 ≈ 76 %; 300 ≈ 85 %.
- `--total` debería reflejar el perfil del cruce, no solo la media de la competición: dos
  equipos de ataque fuerte y defensa floja pueden justificar 3.4; un cruce de bloques bajos, 2.4.
  Una forma sencilla: `T = media_competición × (ataque_l·defensa_v + ataque_v·defensa_l) / 2`
  con las fuerzas relativas de la sección siguiente.

## 6. λ desde xG (fuerzas de ataque y defensa)

`--fuerzas ATA_L DEF_L ATA_V DEF_V --media-local ML --media-visitante MV`:

```
λ_local     = ML × ATA_L × DEF_V
λ_visitante = MV × ATA_V × DEF_L
ATA = xG a favor por partido del equipo / media de la competición
DEF = xG en contra por partido del equipo / media de la competición   (>1 = defensa peor que la media)
```

- Usa xG (Opta/StatsBomb en FBref, Understat en las cinco grandes ligas) en vez de goles: la
  varianza de los goles hace que 8-10 partidos de goles digan poco.
- Regresión a la media: con n partidos jugados, pondera la temporada actual con `n / (n + 10)` y
  el resto con la temporada anterior (o con Elo). Con 4 jornadas, la temporada actual pesa
  menos del 30 %.
- Al mezclar datos de liga y de Champions, corrige por nivel de la liga: un xG de 2.0 por partido
  en una liga menor no vale lo mismo que en la Premier. La forma limpia es apoyarse en Elo para
  la fuerza relativa y usar xG solo para el perfil (total de goles, ataque o defensa).
- Local/visitante: si tienes desglose (xG en casa y fuera), úsalo; si no, las medias ML y MV de la
  competición ya aportan la ventaja local media.

## 7. Ajustes contextuales

Se aplican con `--factor-local` y `--factor-visitante` sobre las λ base y siempre se documentan.
Rangos razonables (multiplicativos):

| Situación | Ataque propio | λ del rival |
|---|---|---|
| Baja del máximo goleador o del creador principal | ×0.90-0.95 | — |
| Bajas de dos o más titulares defensivos o del portero | — | ×1.05-1.10 |
| Rotación amplia (≥5 titulares fuera) | ×0.85-0.92 | ×1.05 |
| Menos de 72 h de descanso o viaje largo | ×0.95 | — |
| Eliminatoria sentenciada en la ida (3+ goles) | ×0.85-0.95 | ×0.85-0.95 |
| Necesita marcar (vuelta, última jornada) | ×1.05-1.10 | ×1.05 (se abre el partido) |
| Fase liga: ya clasificado o ya eliminado | ×0.90-0.95 | ×1.05 |
| Nuevo entrenador (primeros 2-3 partidos) | ×0.95-1.05 según el caso, avisando de la incertidumbre | |

Tope total de ±25 % entre todos los ajustes. Un ajuste sin un hecho verificable detrás es ruido;
si partes de cuotas, la mayoría de estos factores ya están dentro y solo caben los posteriores a
la captura de las cuotas (alineación oficial una hora antes, lesión en el calentamiento).

## 8. Mitades

- El 45 % de los goles cae en la primera parte (`--ht-fraccion 0.45`); el segundo tiempo tiene
  más goles por cansancio, cambios y descuento más largo.
- El script trata las mitades como independientes y sin corrección Dixon-Coles. Esto sobrestima
  ligeramente las remontadas (`htft.2/1`, `htft.1/2`) y subestima un poco el "gestiona la
  ventaja". Para mercados de descanso/final con cuotas altas, exige más EV.

## 9. Prórroga y penaltis

- Prórroga = 30 minutos: `λ_prórroga = λ_90 × (30/90) × --factor-prorroga` (1.0 por defecto;
  hay evidencia de ritmos algo menores por cansancio y algo mayores por el descuento y las
  defensas rotas; se compensan). Sin corrección Dixon-Coles.
- Penaltis: 50 % (`--pen-local`). Cambia solo con evidencia concreta (portero con historial
  claro, tanda en casa con público, especialistas ausentes).
- Sin gol de visitante en competiciones UEFA desde 2021-22: el global empatado va a prórroga.

## 10. Córners y tarjetas

- Ambos se modelan con una binomial negativa con media μ y ratio varianza/media r
  (`--dispersion-corners 1.3`, `--dispersion-tarjetas 1.15`; r = 1 equivale a Poisson).
- Córners: media por equipo ≈ (córners a favor del equipo + córners en contra del rival) / 2,
  corregida por dominio esperado. Los córners no son independientes de los goles, pero la
  correlación es débil (un equipo que va ganando saca menos córners): no combines córners con
  resultado multiplicando probabilidades sin avisar.
- Tarjetas: media ≈ 0.5 × (tarjetas que ve el equipo + tarjetas que provoca el rival) por
  equipo, escalada por el árbitro (ratio tarjetas del árbitro / media de la competición) y por
  el contexto (derbi, eliminatoria: +10-20 %).

## 11. Goleadores

`μ_jugador = λ_equipo × cuota_goles × minutos/90`, con Poisson: P(marca) = 1 - e^{-μ};
P(2+) = 1 - e^{-μ}(1 + μ). Primer/último goleador: cuota_goles × P(su equipo marca primero/último)
limitado a la ventana de minutos en la que está en el campo (para un suplente, solo el tramo
final). La cuota de goles se estima mezclando su parte de goles y de xG del equipo, con extra si
lanza los penaltis. Las casas cargan un 20-30 % de margen en goleadores: exige EV alto.

## 12. Valor, margen y gestión de banca

- **EV** por unidad apostada: `P(ganar) × (cuota - 1) - P(perder)`; con devolución (líneas
  enteras/cuarto) la parte devuelta no suma ni resta.
- **Kelly**: `f* = (P(ganar) × (cuota - 1) - P(perder)) / ((cuota - 1) × (P(ganar) + P(perder)))`.
  El script aplica una fracción (`--kelly 0.25`) y un tope (`--stake-max 0.03` de la banca). Kelly
  pleno maximiza el crecimiento solo si las probabilidades fueran exactas; con error de modelo,
  un cuarto de Kelly conserva casi todo el crecimiento con una fracción de la varianza.
- **Mezcla con el mercado** (`--peso-mercado w`): probabilidad final = (1 - w)·modelo +
  w·mercado (probabilidad justa una vez quitado el margen). Con w = 0.5 en el 1X2 y O/U de casas
  grandes te acercas a la mejor estimación disponible; deja w = 0 solo cuando tu información sea
  claramente mejor que la del mercado (casi nunca en el 1X2, a veces en secundarios).
- **Umbrales**: EV ≥ 3 % (`--ev-min`) y probabilidad ≥ 5 % (`--prob-min`). Sube el EV mínimo
  con cuotas altas (≥ 6 % por encima de 4.0) y en mercados de margen alto.
- **Correlación** entre selecciones del mismo partido: reduce stakes o quédate con una.

## 13. Calibración, validación y cuánta muestra hace falta

- **Calibración**: agrupa pronósticos por tramos de probabilidad (0-10 %, 10-20 %...) y compara
  la frecuencia real. Un modelo calibrado acierta el 30 % de las veces que dice 30 %.
- **Métricas**: Brier (`media de (p - resultado)²`, menor es mejor; 0.25 es lanzar una moneda en
  un mercado a dos vías) y log-loss. Compara siempre contra la referencia del mercado (las
  probabilidades justas de cierre): si no bates al mercado en log-loss, no hay valor que
  explotar por mucho que "aciertes".
- **CLV** (closing line value): cuota tomada frente a cuota de cierre. Batir el cierre de forma
  sistemática es la señal más rápida (decenas de apuestas) de que el proceso funciona; el
  beneficio necesita miles. Con un 3 % de ventaja real y cuotas ~2.0, distinguir la ventaja de
  la suerte a dos desviaciones típicas exige del orden de 4 000 apuestas.
- **Backtesting**: los CSV de football-data.co.uk (ligas nacionales, con cuotas de apertura y
  cierre) permiten probar el proceso completo; para Champions/Europa League hay que combinar
  resultados (openfootball, FBref) con cuotas históricas (Oddsportal/BetExplorer).

## 14. Límites del modelo

- No sabe nada de alineaciones, estados de forma o motivación si no se lo dices a través de λ y
  los factores; no se inventa lo que no tiene.
- Independencia entre mitades, entre goles y córners/tarjetas, y entre los goles de ambos equipos
  (salvo la corrección Dixon-Coles). Los partidos reales tienen dinámica (marcador, expulsiones,
  cambios) que el modelo ignora.
- Sin sobredispersión en goles: partidos con probabilidad de expulsión alta o resultados
  abultados esperados (mismatch enorme) quedan algo mal representados en las colas.
- La calidad del pronóstico es la calidad de las λ: un script exacto sobre λ malas produce
  cuotas justas precisas... de un partido que no existe. Todo el esfuerzo debe ir a estimarlas y a
  compararlas con el mercado.
