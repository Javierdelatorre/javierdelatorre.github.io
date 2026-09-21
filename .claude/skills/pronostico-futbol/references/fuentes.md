# Fuentes de datos: dónde conseguir cada cosa y cómo

Tabla de contenidos: [Qué funciona según el entorno](#1-qué-funciona-según-el-entorno) · [Cuotas](#2-cuotas) ·
[Fuerza de los equipos](#3-fuerza-de-los-equipos-elo-y-xg) · [Calendario, resultados y clasificación](#4-calendario-resultados-y-clasificación) ·
[Alineaciones, bajas y árbitros](#5-alineaciones-bajas-sanciones-y-árbitros) · [Córners y tarjetas](#6-córners-tarjetas-y-estadísticas-de-partido) ·
[Histórico para backtesting](#7-histórico-para-backtesting) · [WebSearch](#8-consultas-de-websearch-que-funcionan) · [Buenas prácticas](#9-buenas-prácticas)

## 1. Qué funciona según el entorno

| Entorno | Qué hay disponible |
|---|---|
| Claude Code en tu máquina, red normal | Todo lo de abajo (`curl`, `WebFetch`, `WebSearch`); respeta los límites de peticiones de cada web |
| Sesión remota con red restringida (claude.ai/code) | Comprobado el 2026-09-21: solo funcionaban `WebSearch` y `raw.githubusercontent.com`; football-data.co.uk, ClubElo, FBref, Understat, ESPN, UEFA, Sofascore, Flashscore, Oddsportal, Transfermarkt, Wikipedia y las APIs con clave estaban bloqueadas por la política de salida. Comprueba con una petición rápida antes de dar nada por hecho |

En modo restringido: `WebSearch` con las consultas del apartado 8 (los fragmentos suelen traer
cuotas 1X2, over/under y listas de lesionados), openfootball para calendario y resultados, y
datos del usuario. Declara siempre qué falta.

Claves de API: guárdalas en variables de entorno (`FOOTBALL_DATA_TOKEN`, `API_FOOTBALL_KEY`,
`ODDS_API_KEY`) y no las imprimas nunca en el informe ni en los comandos que muestres.

## 2. Cuotas

| Fuente | Qué da | Acceso | Notas |
|---|---|---|---|
| **The Odds API** | 1X2 (`h2h`), totales (`totals`), hándicaps (`spreads`) de decenas de casas, por región | `https://api.the-odds-api.com/v4/sports/soccer_uefa_champs_league/odds?regions=eu&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey=$ODDS_API_KEY` | Claves de deporte: `soccer_uefa_champs_league`, `soccer_uefa_europa_league`, `soccer_uefa_europa_conference_league`, `soccer_spain_la_liga`, `soccer_epl`... Plan gratuito con crédito mensual limitado |
| **API-Football** (api-sports.io) | Cuotas por casa y mercado (`/odds?fixture=ID`), además de lineups, lesiones y estadísticas | Cabecera `x-apisports-key: $API_FOOTBALL_KEY`; base `https://v3.football.api-sports.io` | Ligas: 2 Champions, 3 Europa League, 848 Conference, 140 LaLiga, 39 Premier. Plan gratuito con unas 100 peticiones al día |
| **Oddsportal** | Comparador con histórico de apertura y cierre | `https://www.oddsportal.com/football/europe/champions-league/` | Web con mucho JavaScript; para leerla en local usa Playwright |
| **BetExplorer** | Comparador sencillo de leer, con cuotas de cierre históricas | `https://www.betexplorer.com/football/europe/champions-league/` | Bueno para backtesting de Champions/Europa League |
| **Pinnacle** | Referencia de cuotas de margen bajo (cierre "sharp") | `https://www.pinnacle.com/en/soccer/uefa-champions-league/matchups` | Úsalo como cuota de cierre de referencia para el CLV |
| **football-data.co.uk** | Cuotas de apertura y cierre de Bet365, Pinnacle y medias de mercado, con líneas asiáticas y O/U 2.5, en CSV | Ver apartado 7 | Solo ligas nacionales, no competiciones UEFA |

Si el usuario no da cuotas y no puedes obtenerlas, entrega la columna "Cuota mín." del script
para que compare él.

## 3. Fuerza de los equipos (Elo y xG)

| Fuente | Qué da | Acceso |
|---|---|---|
| **ClubElo** | Elo de todos los clubes europeos, calibrado entre ligas; histórico y próximos partidos con probabilidades | Ranking de un día: `http://api.clubelo.com/2026-09-21` (CSV: Rank, Club, Country, Level, Elo, From, To). Historial de un club: `http://api.clubelo.com/Barcelona`. Próximos partidos: `http://api.clubelo.com/Fixtures` |
| **FBref** (datos Opta) | xG, xGA, tiros, posesión por equipo y por partido, también en Champions, Europa League y Conference | Champions: `https://fbref.com/en/comps/8/Champions-League-Stats`; Europa League: `https://fbref.com/en/comps/19/Europa-League-Stats`; Conference: `https://fbref.com/en/comps/882/Conference-League-Stats`. Calendario con xG por partido: `https://fbref.com/en/comps/8/schedule/Champions-League-Scores-and-Fixtures`. Máximo unas 10 peticiones por minuto o te bloquean |
| **Understat** | xG por partido y por jugador en las cinco grandes ligas y la liga rusa (no en competiciones UEFA) | `https://understat.com/league/La_liga/2026`, `https://understat.com/team/Atletico_Madrid/2026` (los datos van en JSON embebido en el HTML) |
| **Sofascore** | xG por partido (también UEFA), alineaciones, valoraciones | Web: `https://www.sofascore.com/tournament/football/europe/uefa-champions-league/7`. Su API interna cambia y bloquea con facilidad: solo para consulta manual |
| **UEFA oficial** | Estadísticas oficiales, clasificación, alineaciones y calendario | `https://www.uefa.com/uefachampionsleague/standings/`, `https://www.uefa.com/uefachampionsleague/fixtures-results/`, `https://www.uefa.com/uefaeuropaleague/standings/` |

Cómo convertirlo en λ: Elo → `--elo-local/--elo-visitante`; xG → fuerzas de ataque y defensa
(`references/modelo.md`, apartado 6). Con menos de 8-10 partidos de la temporada, pondera la
anterior.

## 4. Calendario, resultados y clasificación

| Fuente | Acceso | Notas |
|---|---|---|
| **openfootball** (GitHub, texto plano) | `https://raw.githubusercontent.com/openfootball/champions-league/master/2025-26/cl.txt` | Calendario y resultados por temporada (también resultados al descanso). Funciona incluso en entornos restringidos. La temporada en curso puede no estar publicada todavía; comprueba la ruta `<temporada>/cl.txt` |
| **ESPN (API no oficial, JSON, sin clave)** | Partidos del día: `https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=20261013`. Clasificación: `https://site.api.espn.com/apis/v2/sports/soccer/uefa.champions/standings` | Ligas: `uefa.champions`, `uefa.europa`, `uefa.europa.conf`, `esp.1`, `eng.1`, `ita.1`, `ger.1`, `fra.1`. A veces incluye cuotas y probabilidades |
| **football-data.org v4** | `curl -s -H "X-Auth-Token: $FOOTBALL_DATA_TOKEN" "https://api.football-data.org/v4/competitions/CL/matches?matchday=2"`; clasificación en `/v4/competitions/CL/standings` | Plan gratuito con Champions (CL) y grandes ligas; Europa League solo en planes de pago |
| **Wikipedia** | `https://en.wikipedia.org/wiki/2026–27_UEFA_Champions_League_league_phase` | Tabla y resultados actualizados por voluntarios; bien para contexto rápido en local |
| **Flashscore / Sofascore / UEFA** | Ver apartado 3 | Marcadores en directo |

## 5. Alineaciones, bajas, sanciones y árbitros

| Necesidad | Fuente |
|---|---|
| Lesionados y sancionados por club | Transfermarkt: `https://www.transfermarkt.es/<club>/sperrenundverletzungen/verein/<id>`; lista de toda la Champions: `https://www.transfermarkt.es/uefa-champions-league/verletztespieler/pokalwettbewerb/CL` |
| Alineaciones probables | Prensa deportiva del día (Marca, AS, Mundo Deportivo, The Athletic, L'Équipe, Kicker, Gazzetta), WhoScored (`https://www.whoscored.com/`), API-Football `/fixtures/lineups?fixture=ID` (oficiales ~1 h antes) |
| Árbitro designado y sus medias de tarjetas | UEFA (designaciones, dos o tres días antes), WhoScored/Transfermarkt (perfil del árbitro), `WebSearch` "árbitro <local> <visitante> Champions" |
| Descanso y calendario de cada equipo | Calendario de su liga (ESPN, football-data.org) para ver el partido anterior y el siguiente |

## 6. Córners, tarjetas y estadísticas de partido

- FBref (tiros, córners en "Miscellaneous Stats", tarjetas), WhoScored (córners y tarjetas por
  partido), API-Football `/fixtures/statistics?fixture=ID` (córners, tarjetas, tiros, posesión).
- football-data.co.uk incluye córners (HC, AC) y tarjetas (HY, AY, HR, AR) por partido en ligas
  nacionales: útil para estimar las medias de los equipos fuera de Europa.

## 7. Histórico para backtesting

- **football-data.co.uk**: `https://www.football-data.co.uk/mmz4281/2526/SP1.csv` (temporada
  2025-26 de LaLiga; `E0` Premier, `I1` Serie A, `D1` Bundesliga, `F1` Ligue 1, `N1` Eredivisie,
  `P1` Portugal, `T1` Turquía, `B1` Bélgica, `SC0` Escocia). Columnas clave: `FTHG/FTAG`
  (goles), `HTHG/HTAG` (descanso), `HC/AC` (córners), `HY/AY/HR/AR` (tarjetas), `B365H/D/A`,
  `PSH/PSD/PSA` (Pinnacle apertura), `PSCH/PSCD/PSCA` (Pinnacle cierre), `B365>2.5/<2.5`,
  `AHh` y `B365AHH/AHA` (línea asiática y cuotas). Guía de columnas:
  `https://www.football-data.co.uk/notes.txt`.
- Champions/Europa League: resultados de openfootball o FBref + cuotas de cierre de BetExplorer
  u Oddsportal.
- Elo histórico diario: ClubElo (`http://api.clubelo.com/<Club>`), para reconstruir la fuerza
  de cada equipo en la fecha del partido sin mirar al futuro.

## 8. Consultas de WebSearch que funcionan

Los fragmentos de los resultados de búsqueda suelen contener el dato sin necesidad de abrir la
página. Combina dos o tres consultas por partido:

- `"<local> vs <visitante>" cuotas` y `"<local> <visitante>" odds 1X2 over 2.5`
- `<equipo> lesionados sancionados <mes> <año>` / `<team> injury news Champions League`
- `"<local> <visitante>" alineaciones probables` / `predicted lineups`
- `Champions League jornada <N> resultados <año>` / `league phase standings`
- `<equipo> xG temporada <año>` / `<team> xG xGA 2026-27`
- `árbitro "<local>" "<visitante>" Champions`
- `<equipo> Elo clubelo`

Anota la fecha del resultado y desconfía de fragmentos sin fecha o de cuotas de otra temporada.

## 9. Buenas prácticas

- Guarda lo que descargues en el directorio de trabajo con la fecha en el nombre
  (`datos/2026-10-13_cuotas_ucl.json`) para poder reproducir el pronóstico y calcular el CLV.
- Una petición cada pocos segundos a webs sin API; identifica el `User-Agent`; nada de
  scraping masivo ni de saltarse bloqueos.
- Cuando dos fuentes discrepen (por ejemplo, un lesionado que una web da como disponible), di
  cuál has seguido y por qué.
