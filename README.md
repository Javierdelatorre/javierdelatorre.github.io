# javierdelatorre.github.io
## Skills de Claude Code

- `.claude/skills/pronostico-futbol/`: pronósticos de fútbol (Champions, Europa League, ligas)
  para todos los mercados de apuestas, con un modelo Poisson/Dixon-Coles en
  `scripts/mercados.py`. Se activa sola al pedir un pronóstico o con `/pronostico-futbol`.
  Ejemplo rápido:

  ```bash
  python3 .claude/skills/pronostico-futbol/scripts/mercados.py \
    --desde-cuotas 2.05 3.60 3.50 --cuotas-ou 1.85 1.95 \
    --local "Atlético" --visitante "Man United" --solo 1x2,ah,ou,btts
  ```
