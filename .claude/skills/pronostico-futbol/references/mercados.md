# Catálogo de mercados: reglas de liquidación y cómo los calcula el script

Tabla de contenidos: [Convenciones](#convenciones) · [Resultado](#1-resultado-final-1x2) · [Doble oportunidad](#2-doble-oportunidad) ·
[DNB](#3-empate-no-válido-dnb) · [Hándicap asiático](#4-hándicap-asiático) · [Hándicap europeo](#5-hándicap-europeo-3-vías) ·
[Totales](#6-total-de-goles-overunder) · [Goles por equipo](#7-goles-por-equipo) · [Ambos marcan](#8-ambos-marcan-btts) ·
[Resultado + total](#9-resultado--total) · [Marcador exacto](#10-marcador-exacto) · [Descanso/final](#11-descansofinal) ·
[Mitades](#12-primera-y-segunda-parte-mitades) · [Gana a cero](#13-gana-a-cero-y-portería-a-cero) · [Par/impar](#14-parimpar) ·
[Margen](#15-margen-de-victoria) · [Goles exactos](#16-número-exacto-de-goles) · [Primer gol](#17-primer-y-último-equipo-en-marcar) ·
[Eliminatorias](#18-clasificación-campeón-prórroga-y-penaltis) · [Córners](#19-córners) · [Tarjetas](#20-tarjetas) ·
[Goleadores](#21-goleadores) · [Otros mercados](#22-otros-mercados-y-cómo-aproximarlos) · [Combinadas](#23-combinadas-y-bet-builders) ·
[En directo](#24-apuestas-en-directo)

## Convenciones

- Salvo que se diga lo contrario, todo se liquida a **90 minutos más el descuento**; la prórroga y
  los penaltis solo cuentan en los mercados de clasificación/campeón.
- El script devuelve por selección: **Prob.** (probabilidad de ganar la apuesta), **Devuelta**
  (probabilidad de que se devuelva el stake, solo en líneas enteras y de cuarto), **Cuota justa**
  = `1 + P(perder) / P(ganar)` (con devolución incluida) y **Cuota mín.** = la cuota a partir de la
  cual la apuesta tiene el EV mínimo exigido.
- Con cuotas de la casa (`--cuotas`), añade **Prob. mercado** (probabilidad implícita una vez
  retirado el margen, solo si se han pasado todas las selecciones del mercado), **EV**
  (`P(ganar) × (cuota - 1) - P(perder)`) y **Stake** (Kelly fraccional con tope).
- La **clave** de cada selección (`1x2.1`, `ou.2.5.over`, `ah.local.-0.75`...) es la que hay que
  usar para pasar cuotas; el script imprime la lista completa en cada ejecución.

## 1. Resultado final (1X2)

`1x2.1`, `1x2.X`, `1x2.2`. Es la suma directa de la matriz de marcadores. El empate es la
selección que más sensibilidad tiene al parámetro ρ de Dixon-Coles y al total de goles (a más
goles esperados, menos empates). Referencia: en un partido igualado con 2.7 goles esperados el
empate ronda el 26-28 %; con 3.3 goles baja al 22-24 %.

## 2. Doble oportunidad

`dc.1X`, `dc.X2`, `dc.12`. Sumas de dos resultados. Nunca tienen devolución. Se compara con el
hándicap asiático +0.5 (idéntico a 1X) y con DNB: si la casa ofrece los tres, elige el que pague
más por la misma cobertura.

## 3. Empate no válido (DNB)

`dnb.1`, `dnb.2`. Si hay empate se devuelve el stake. Probabilidad de ganar = P(1), de perder =
P(2), devuelta = P(X). Es exactamente el hándicap asiático 0 (`ah.local.0`).

## 4. Hándicap asiático

Claves `ah.local.<línea>` y `ah.visitante.<línea>`; la línea se aplica al equipo indicado, por
ejemplo `ah.local.-0.75` o `ah.visitante.+0.75` (siempre espejo). Líneas de -3 a +3 en pasos de
0.25; por defecto solo se imprimen las que tienen entre 10 % y 90 % de probabilidad de ganar
(`--todas-lineas` para verlas todas).

| Tipo de línea | Ejemplo | Liquidación |
|---|---|---|
| Media (x.5) | Local -0.5 | Gana si el local gana; pierde en empate o derrota. Nunca hay devolución |
| Entera (x.0) | Local -1 | Gana si gana por 2+, devuelta si gana por 1, pierde en el resto |
| Cuarto (x.25 / x.75) | Local -0.75 | Mitad del stake a -0.5 y mitad a -1: victoria por 1 gol = media ganada, media devuelta; victoria por 2+ = todo ganado; empate o derrota = todo perdido |

Equivalencias útiles: `ah.local.-0.5` = `1x2.1`; `ah.local.+0.5` = `dc.1X`; `ah.local.0` = `dnb.1`.
Cuando el mercado ofrece varias líneas del mismo partido, todas deben implicar la misma
supremacía; si una casa se descuelga en una línea de cuarto, suele haber valor ahí. Para las
líneas con devolución el script calcula la cuota justa con `1 + P(perder)/P(ganar)`, que ya
descuenta la parte devuelta.

## 5. Hándicap europeo (3 vías)

`eh.<línea>.1`, `eh.<línea>.X`, `eh.<línea>.2`, con líneas enteras aplicadas al local. Con
`eh.-1`: "1" = el local gana por 2 o más, "X" = el local gana por exactamente 1, "2" = empate o
victoria visitante. No hay devoluciones. Márgenes de casa más altos que en el asiático.

## 6. Total de goles (over/under)

`ou.<línea>.over`, `ou.<línea>.under`. Líneas de 0.5 a 6.5 en pasos de 0.25. Las enteras (2, 3,
4) devuelven el stake si el total coincide con la línea; las de cuarto reparten el stake entre
las dos líneas vecinas (over 2.75 = mitad a 2.5 y mitad a 3: con 3 goles, media ganada y media
devuelta). `--linea-total` fija la línea que se usa en los combinados resultado + total.

## 7. Goles por equipo

`tt.local.<línea>.over/under`, `tt.visitante.<línea>.over/under` con líneas 0.5, 1, 1.5, 2, 2.5
y 3.5. Se liquidan igual que los totales. Son mercados donde el margen de la casa es mayor y las
probabilidades dependen directamente de la λ de ese equipo: buen sitio para explotar una baja
defensiva rival que el mercado principal descuenta poco.

## 8. Ambos marcan (BTTS)

`btts.si`, `btts.no`, y combinados con el resultado en `res_btts.<1|X|2>.<si|no>` ("X y no" es
el 0-0; "1 y no" equivale a "local gana a cero"). También en primera parte: `1h.btts.si/no`.
BTTS depende de las dos λ por separado, no del total: dos equipos con 1.5 y 1.5 dan más BTTS que
2.4 y 0.6 aunque el total sea el mismo.

## 9. Resultado + total

`res_ou.1.over2.5`, `res_ou.1.under2.5`, `res_ou.X.over2.5`... (la línea cambia con
`--linea-total`). Un empate con más de 2.5 exige al menos un 2-2. Se calculan directamente de la
matriz, así que las correlaciones ya están incluidas: no multipliques P(1) por P(over).

## 10. Marcador exacto

`cs.<local>-<visitante>` para los N marcadores más probables (`--top-marcadores`, 12 por
defecto) y `cs.otro` para el resto. Los márgenes de las casas en este mercado son del 20-40 %,
así que el EV aparente tiene que ser grande para compensar el error del modelo. Para "grupos de
marcadores" (por ejemplo "cualquier 1-0, 2-0 o 2-1") suma las celdas correspondientes.

## 11. Descanso/final

`htft.<descanso>/<final>` con los nueve pares (`htft.1/1`, `htft.X/1`, `htft.2/1`...). El script
divide λ en dos mitades (45 % en la primera por defecto, `--ht-fraccion`), asume mitades
independientes y suma todos los caminos posibles. Las combinaciones "remontada" (`2/1`, `1/2`)
son las más sensibles a esa hipótesis y suelen estar sobrevaloradas por el modelo respecto al
mercado, porque un equipo que se pone por delante gestiona el partido. Úsalo con prudencia.

## 12. Primera y segunda parte (mitades)

`1h.1x2.<1|X|2>`, `1h.ou.<0.5|1|1.5|2.5>.over/under`, `1h.btts.si/no`; `2h.1x2.*`,
`2h.ou.*`. Mercados de mitades: `mitades.ambas.si/no` (gol en ambas mitades) y
`mitades.mas.<1h|2h|igual>` (qué mitad tiene más goles). El empate al descanso es la selección
más probable en casi cualquier partido (35-45 %), algo que sorprende a muchos apostantes.

## 13. Gana a cero y portería a cero

`wtn.local.si/no`, `wtn.visitante.si/no` (win to nil), `cs.local.si/no`, `cs.visitante.si/no`
(clean sheet, el equipo indicado no encaja). "Gana a cero" es P(gana y el rival marca 0);
"portería a cero" incluye también el 0-0.

## 14. Par/impar

`parimpar.par`, `parimpar.impar` sobre el total de goles (el 0-0 es par). Está cerca del 50/50
salvo en partidos de pocos goles, donde el par gana algo de ventaja por el peso del 0-0 y el 1-1.

## 15. Margen de victoria

`margen.local.1`, `margen.local.2`, `margen.local.3+`, `margen.empate`, `margen.visitante.1`,
`margen.visitante.2`, `margen.visitante.3+`. Algunas casas separan "empate 0-0" del resto de
empates: usa `cs.0-0` y réstalo.

## 16. Número exacto de goles

`goles.0` ... `goles.5`, `goles.6+`. También sirven para bandas ("2-3 goles" = `goles.2 + goles.3`).

## 17. Primer y último equipo en marcar

`primero.local`, `primero.visitante`, `primero.ninguno`, y `ultimo.*`. Con procesos de Poisson de
intensidad constante, la probabilidad de marcar primero (y también la de marcar el último) es
`λ_equipo / (λ_local + λ_visitante)` multiplicada por la probabilidad de que haya algún gol.
"Ninguno" es el 0-0. El mercado "gol antes del minuto X" se aproxima con
`1 - exp(-(λ_local + λ_visitante) · X / 90)`.

## 18. Clasificación, campeón, prórroga y penaltis

Se activan con `--eliminatoria unico` (partido único: final o play-off de un partido) o
`--eliminatoria vuelta --ida L-V`, donde `L-V` son los goles que marcaron en la ida el equipo que
hoy es local y el que hoy es visitante, en ese orden. Claves: `elim.local`, `elim.visitante`
(se clasifica / gana el título), `elim.prorroga.si/no`, `elim.penaltis.si/no`, el desglose a 90
minutos `elim.local.90`, `elim.visitante.90`, `elim.empate.90` y el **método de clasificación**
que ofrecen algunas casas: `elim.metodo.local.90`, `elim.metodo.local.et` (pasa en la prórroga),
`elim.metodo.local.pen` (pasa en los penaltis) y sus equivalentes para el visitante; las seis
suman 1. El script imprime además una fila "Lectura de la eliminatoria" que explica en palabras
qué necesita el local: úsala para detectar una ida introducida al revés.

Reglas UEFA vigentes: no hay gol de visitante (desde 2021-22); con empate global se juegan 30
minutos de prórroga y, si persiste, penaltis. El script modela la prórroga como un tercio de
partido (`--factor-prorroga` para cambiar el ritmo) y los penaltis al 50 % (`--pen-local` si
tienes motivos para otra cosa, por ejemplo un portero especialista o el apoyo del público).

Para "campeón del torneo" (outright) no hay un cálculo directo: se encadenan las probabilidades
de superar cada ronda contra el rival esperado, o se simula el cuadro. Si el usuario lo pide,
explica la cadena y las hipótesis en vez de dar un número sin sustento.

## 19. Córners

Necesitan sus propias medias: `--corners-total`, o `--corners-local` y `--corners-visitante`
(entonces también salen `corners.1x2.*` y los totales por equipo). Se modelan con una binomial
negativa (`--dispersion-corners`, 1.3 por defecto, porque los córners son más variables que una
Poisson). Cómo estimar la media de un equipo: promedio de sus córners a favor y de los córners
en contra del rival, corregido por quién dominará (un equipo que va a tener el 60 % de posesión
suele sacar el 55-60 % de los córners). Referencia: los partidos de Champions promedian unos 10
córners totales, con líneas habituales entre 8.5 y 11.5. Claves: `corners.<línea>.over/under`,
`corners.local.<línea>.over/under`, `corners.1x2.1/X/2`.

## 20. Tarjetas

`--tarjetas-total` o `--tarjetas-local` y `--tarjetas-visitante` (`--dispersion-tarjetas`, 1.15
por defecto). La media depende tanto del árbitro como de los equipos: combina la media de
tarjetas por partido del árbitro designado con la de ambos equipos (mostradas y provocadas) y
sube un 10-20 % en eliminatorias y derbis. En competición UEFA la mayoría de partidos se mueve
entre 3.5 y 5.5 tarjetas. Tarjeta roja: `P(al menos una) = 1 - exp(-μ)` con μ ≈ 0.2-0.3 por
partido. Claves: `tarjetas.<línea>.over/under`, `tarjetas.local.<línea>.*`, `tarjetas.1x2.*`.

## 21. Goleadores

`--goleadores-local "Nombre:cuota_goles:minutos,..."` y `--goleadores-visitante`. `cuota_goles`
es la fracción de los goles de su equipo que marca ese jugador (0.22 o 22); `minutos`, los que se
espera que juegue (90 por defecto); el prefijo `+` indica un suplente que entra a falta de esos
minutos. Claves: `gol.<nombre>.anytime` (marca en cualquier momento), `gol.<nombre>.2+`,
`gol.<nombre>.primero`, `gol.<nombre>.ultimo`. Hat-trick: `1 - e^{-μ}(1 + μ + μ²/2)` con
`μ = λ_equipo × cuota_goles × minutos/90`.

Cómo estimar la cuota de goles: mezcla de su parte de los goles del equipo en la temporada y de
su parte del xG del equipo (el xG es más estable), más un extra si lanza los penaltis (un penalti
a favor cada 4-5 partidos, marcado el 78 %). Con los titulares habituales la suma de cuotas de
los jugadores listados no debería superar 1.

## 22. Otros mercados y cómo aproximarlos

| Mercado | Aproximación con el modelo |
|---|---|
| Gana ambas mitades | `1h.1x2.1 × 2h.1x2.1` (mitades independientes) |
| Marca en ambas mitades (equipo) | `(1 - e^{-0.45λ}) × (1 - e^{-0.55λ})` |
| Gana desde atrás / remontada | No hay cálculo cerrado; usar `htft.2/1` como cota inferior y decir que es una aproximación |
| Gol en los primeros 10 minutos | `1 - exp(-(λ_l + λ_v) × 10/90)` |
| Gol después del minuto 75 | `1 - exp(-(λ_l + λ_v) × 15/90)` (algo más en la práctica: el descuento suma minutos) |
| Minuto del primer gol (over/under 30.5) | `P(sin gol hasta el 30) = exp(-(λ_l + λ_v) × 30/90)` |
| Penalti en el partido | `1 - exp(-μ)` con μ ≈ 0.25-0.30 (Champions/Europa League) |
| Tiros a puerta de un jugador | Poisson con su media por 90 minutos ajustada a los minutos previstos y a la defensa rival |
| Asistencias de un jugador | Poisson con `λ_equipo × cuota_asistencias × minutos/90` (las asistencias son ~0.8 por gol) |
| Jugador amonestado | `1 - exp(-tasa_tarjetas_jugador × minutos/90 × factor_árbitro)` |
| Cualquier equipo gana por 2+ | `margen.local.2 + margen.local.3+ + margen.visitante.2 + margen.visitante.3+` |
| Empate con goles | `1x2.X - cs.0-0` |
| Ganador con hándicap de goles del jugador (player props combinados) | No modelado; declina o construye a mano con las mismas Poisson y avisa de las correlaciones |

## 23. Combinadas y bet builders

- Dentro del mismo partido, las selecciones están correlacionadas: calcula la combinación
  directamente sobre la matriz (el script ya ofrece resultado + total y resultado + ambos marcan)
  o suma las celdas que cumplan todas las condiciones. Multiplicar probabilidades marginales del
  mismo partido está mal salvo que sean independientes por construcción (goles y córners, por
  ejemplo, solo lo son de forma aproximada).
- Entre partidos distintos, multiplica probabilidades: `mercados.py --combinada 0.78,0.65,0.55
  --cuota-combinada 4.2` da la probabilidad conjunta, la cuota justa, el EV y el stake. La cuota
  justa de la combinada es el producto de las cuotas justas; el margen de la casa también se
  multiplica, por lo que una combinada de cinco tramos al 5 % de margen cada uno paga como si
  tuviera un 23 % de margen.
- Regla práctica: recomienda combinadas solo si cada tramo tiene valor por sí solo.

## 24. Apuestas en directo

El script sirve también en directo si le pasas las λ de **lo que queda de partido**:
`λ_resto = λ_90 × minutos_restantes/90 × factor_estado`, con ρ = 0 (la corrección de marcadores
bajos no aplica a tramos parciales). Para el resultado final con marcador actual `a-b`, usa
`--eliminatoria vuelta --ida a-b`: `elim.local.90`, `elim.empate.90` y `elim.visitante.90` son
las probabilidades de que el local acabe ganando, empatando o perdiendo; para totales, resta los
goles ya marcados a la línea. El `factor_estado` recoge lo que el marcador hace con el juego
(el que va perdiendo ataca más: ×1.1-1.2 para él y ×1.0-1.1 para el rival por los contraataques;
una expulsión: ×0.7 para el equipo con diez y ×1.3 para el otro). En directo el mercado se mueve
en segundos: solo tiene sentido con cuotas capturadas en el mismo minuto.
