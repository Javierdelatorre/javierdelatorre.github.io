#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mercados.py — Calculadora de probabilidades y cuotas justas para todos los mercados
habituales de un partido de fútbol, a partir de los goles esperados (λ) de cada equipo,
con un modelo Poisson bivariante corregido (Dixon-Coles). Solo usa la librería estándar.

Formas de obtener λ (goles esperados a 90 minutos):
  1) Directas:           --xg-local 1.65 --xg-visitante 1.10
  2) Desde cuotas 1X2:   --desde-cuotas 2.10 3.50 3.60 [--cuotas-ou 1.90 1.95 --linea-ou 2.5]
  3) Desde Elo:          --elo-local 1890 --elo-visitante 1780 [--ventaja-local 65 --total 3.0]
  4) Desde fuerzas:      --fuerzas ATA_L DEF_L ATA_V DEF_V [--media-local 1.65 --media-visitante 1.35]
Ajustes contextuales explícitos (bajas, rotación, motivación): --factor-local 0.95 --factor-visitante 1.05

Cuotas de la casa (opcional) para detectar valor:
  --cuotas '{"1x2.1":2.10,"1x2.X":3.50,"1x2.2":3.60,"ou.2.5.over":1.90}'
  (JSON en línea, ruta a un fichero JSON, o lista clave=cuota separada por comas)
Las claves son exactamente las que imprime el script en la columna "Clave".

Ejemplos:
  python3 mercados.py --xg-local 1.7 --xg-visitante 1.1 --local "Atlético" --visitante "Man United"
  python3 mercados.py --desde-cuotas 2.05 3.60 3.50 --cuotas-ou 1.80 2.05 --formato json
  python3 mercados.py --xg-local 1.4 --xg-visitante 1.3 --eliminatoria vuelta --ida 1-2
  python3 mercados.py --xg-local 1.6 --xg-visitante 1.2 --corners-local 5.8 --corners-visitante 4.4 \
      --tarjetas-total 4.6 --goleadores-local "Griezmann:0.22:80,Sorloth:0.20:65"
"""
import argparse
import json
import math
import os
import sys
from math import exp, lgamma, log

VERSION = "1.0"
EPS = 1e-9


# ----------------------------------------------------------------------------
# Distribuciones básicas
# ----------------------------------------------------------------------------
def pois(lam, n):
    """Vector de probabilidades Poisson(lam) para k = 0..n."""
    out = [0.0] * (n + 1)
    p = math.exp(-lam)
    out[0] = p
    for k in range(1, n + 1):
        p *= lam / k
        out[k] = p
    return out


def nb_pmf(mu, ratio, n):
    """Binomial negativa parametrizada por media y ratio varianza/media (ratio<=1 -> Poisson)."""
    if ratio <= 1.0001:
        v = pois(mu, n)
    else:
        size = mu / (ratio - 1.0)
        p = 1.0 / ratio
        v = []
        for k in range(n + 1):
            lp = lgamma(k + size) - lgamma(k + 1) - lgamma(size) + size * log(p) + k * log(1 - p)
            v.append(exp(lp))
    s = sum(v)
    return [x / s for x in v]


def tau(x, y, lh, la, rho):
    """Corrección Dixon-Coles para marcadores bajos."""
    if x == 0 and y == 0:
        return 1 - lh * la * rho
    if x == 0 and y == 1:
        return 1 + lh * rho
    if x == 1 and y == 0:
        return 1 + la * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def rho_valido(lh, la, rho):
    """Recorta rho al rango en el que todas las probabilidades siguen siendo positivas."""
    lo = max(-1.0 / lh, -1.0 / la) + 1e-6
    hi = min(1.0 / (lh * la), 1.0) - 1e-6
    return max(lo, min(hi, rho))


def matriz(lh, la, rho=0.0, n=10):
    """Matriz P[x][y] = P(local marca x, visitante marca y) normalizada."""
    ph, pa = pois(lh, n), pois(la, n)
    M = [[ph[x] * pa[y] * tau(x, y, lh, la, rho) for y in range(n + 1)] for x in range(n + 1)]
    s = sum(map(sum, M))
    return [[v / s for v in fila] for fila in M]


def P(M, cond):
    n = len(M)
    return sum(M[x][y] for x in range(n) for y in range(n) if cond(x, y))


def resultado(M):
    p1 = P(M, lambda x, y: x > y)
    px = P(M, lambda x, y: x == y)
    return p1, px, 1.0 - p1 - px


def dist_total(M):
    n = len(M)
    T = [0.0] * (2 * n - 1)
    for x in range(n):
        for y in range(n):
            T[x + y] += M[x][y]
    return T


def es_cuarto(linea):
    return int(round(linea * 4)) % 2 == 1


def fmt_linea(h, signo=False):
    s = f"{h:+.2f}" if signo else f"{h:.2f}"
    s = s.rstrip("0").rstrip(".")
    if s in ("+0", "-0", ""):
        s = "0"
    return s


# ----------------------------------------------------------------------------
# Mercados con línea (hándicap asiático, totales)
# ----------------------------------------------------------------------------
def _ah_simple(M, h):
    W = P(M, lambda x, y: x - y + h > EPS)
    L = P(M, lambda x, y: x - y + h < -EPS)
    return W, L


def ah_local(M, h):
    """(gana, pierde, devuelta) apostando al local con hándicap h (líneas de cuarto repartidas)."""
    if es_cuarto(h):
        w1, l1 = _ah_simple(M, h - 0.25)
        w2, l2 = _ah_simple(M, h + 0.25)
        W, L = (w1 + w2) / 2, (l1 + l2) / 2
    else:
        W, L = _ah_simple(M, h)
    return W, L, max(0.0, 1 - W - L)


def _ou_simple(T, linea):
    W = sum(T[k] for k in range(len(T)) if k > linea + EPS)
    L = sum(T[k] for k in range(len(T)) if k < linea - EPS)
    return W, L


def over(T, linea):
    """(gana, pierde, devuelta) apostando al over de una distribución de totales T."""
    if es_cuarto(linea):
        w1, l1 = _ou_simple(T, linea - 0.25)
        w2, l2 = _ou_simple(T, linea + 0.25)
        W, L = (w1 + w2) / 2, (l1 + l2) / 2
    else:
        W, L = _ou_simple(T, linea)
    return W, L, max(0.0, 1 - W - L)


# ----------------------------------------------------------------------------
# Obtención de λ
# ----------------------------------------------------------------------------
def probs_justas(cuotas, metodo="potencia"):
    """Quita el margen de una lista de cuotas mutuamente excluyentes."""
    imp = [1.0 / o for o in cuotas]
    if metodo == "multiplicativo":
        s = sum(imp)
        return [p / s for p in imp]
    lo, hi = 0.3, 6.0
    for _ in range(100):
        k = (lo + hi) / 2
        s = sum(p ** k for p in imp)
        if s > 1:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    return [p ** k for p in imp]


def esperanza(lh, la, rho, n):
    M = matriz(lh, la, rho_valido(lh, la, rho), n)
    p1, px, p2 = resultado(M)
    return p1 + 0.5 * px, px, M


def supremacia_para(T, E_obj, rho, n):
    """Busca la supremacía s tal que P(1)+0.5P(X) = E_obj con total T fijo."""
    lo, hi = -T + 0.02, T - 0.02
    for _ in range(60):
        s = (lo + hi) / 2
        E, _, _ = esperanza((T + s) / 2, (T - s) / 2, rho, n)
        if E < E_obj:
            lo = s
        else:
            hi = s
    return (lo + hi) / 2


def lambdas_desde_elo(elo_l, elo_v, ventaja, T, rho, n):
    E = 1.0 / (1.0 + 10 ** (-(elo_l + ventaja - elo_v) / 400.0))
    s = supremacia_para(T, E, rho, n)
    return (T + s) / 2, (T - s) / 2, E


def lambdas_desde_cuotas(o1, ox, o2, over_odds, under_odds, linea, T0, rho, n, metodo):
    """Invierte las cuotas del mercado para obtener (λ_local, λ_visitante) por mínimos cuadrados.

    Se minimiza el error cuadrático entre las probabilidades justas del mercado (1, X, 2 y, si
    las hay, over) y las del modelo. Se usa una rejilla gruesa seguida de una búsqueda local,
    porque la probabilidad de empate no es monótona en el total cuando un equipo es muy superior
    y una bisección simple puede converger a una solución falsa.
    """
    p1, px, p2 = probs_justas([o1, ox, o2], metodo)
    p_over = None
    if over_odds and under_odds:
        p_over = probs_justas([over_odds, under_odds], metodo)[0]

    def error(lh, la):
        if lh <= 0.02 or la <= 0.02:
            return float("inf")
        M = matriz(lh, la, rho_valido(lh, la, rho), n)
        a, b, c = resultado(M)
        e = (a - p1) ** 2 + (b - px) ** 2 + (c - p2) ** 2
        if p_over is not None:
            w, _, push = over(dist_total(M), linea)
            e += (w / max(EPS, 1 - push) - p_over) ** 2
        return e

    mejor, best_e = (T0 / 2, T0 / 2), float("inf")
    for i in range(2, 51):
        for j in range(2, 51):
            lh, la = i / 10.0, j / 10.0
            e = error(lh, la)
            if e < best_e:
                mejor, best_e = (lh, la), e
    lh, la = mejor
    paso = 0.05
    while paso > 2e-4:
        mejorado = False
        for dh, da in ((paso, 0), (-paso, 0), (0, paso), (0, -paso), (paso, paso), (-paso, -paso), (paso, -paso), (-paso, paso)):
            e = error(lh + dh, la + da)
            if e < best_e:
                lh, la, best_e, mejorado = lh + dh, la + da, e, True
                break
        if not mejorado:
            paso /= 2
    return lh, la, (p1, px, p2, p_over)


# ----------------------------------------------------------------------------
# Filas de mercado
# ----------------------------------------------------------------------------
class Fila:
    __slots__ = ("grupo", "clave", "seleccion", "W", "L", "push", "excl", "nota",
                 "cuota_casa", "q_mercado", "q_bruta", "ev", "kelly", "stake", "W_final", "L_final")

    def __init__(self, grupo, clave, seleccion, W, L=None, push=0.0, excl=None, nota=""):
        self.grupo, self.clave, self.seleccion = grupo, clave, seleccion
        self.W = max(0.0, min(1.0, W))
        self.L = (1.0 - self.W) if L is None else max(0.0, L)
        self.push = max(0.0, push)
        self.excl, self.nota = excl, nota
        self.cuota_casa = self.q_mercado = self.q_bruta = self.ev = self.kelly = self.stake = None
        self.W_final, self.L_final = self.W, self.L

    @property
    def prob(self):
        return self.W

    @property
    def prob_cond(self):
        d = self.W + self.L
        return self.W / d if d > 0 else 0.0

    @property
    def cuota_justa(self):
        return 1 + self.L / self.W if self.W > EPS else float("inf")

    def cuota_min(self, ev_min):
        return 1 + (self.L + ev_min) / self.W if self.W > EPS else float("inf")


def construir_filas(M, lh, la, rho, args, n):
    filas = []
    T = dist_total(M)
    loc, vis = args.local, args.visitante
    p1, px, p2 = resultado(M)

    # 1X2 y derivados
    filas += [Fila("1x2", "1x2.1", f"Gana {loc}", p1, excl="1x2"),
              Fila("1x2", "1x2.X", "Empate", px, excl="1x2"),
              Fila("1x2", "1x2.2", f"Gana {vis}", p2, excl="1x2")]
    filas += [Fila("dc", "dc.1X", f"{loc} o empate", p1 + px),
              Fila("dc", "dc.X2", f"Empate o {vis}", px + p2),
              Fila("dc", "dc.12", f"{loc} o {vis}", p1 + p2)]
    filas += [Fila("dnb", "dnb.1", f"{loc} (empate anula)", p1, p2, px, excl="dnb"),
              Fila("dnb", "dnb.2", f"{vis} (empate anula)", p2, p1, px, excl="dnb")]

    # Hándicap asiático
    lineas_ah = [i / 4 for i in range(-12, 13)]
    for h in lineas_ah:
        W, L, push = ah_local(M, h)
        visible = args.todas_lineas or (0.10 <= W / max(EPS, W + L) <= 0.90)
        if not visible:
            continue
        hl, hv = fmt_linea(h, True), fmt_linea(-h, True)
        filas.append(Fila("ah", f"ah.local.{hl}", f"{loc} {hl}", W, L, push, excl=f"ah.{hl}"))
        filas.append(Fila("ah", f"ah.visitante.{hv}", f"{vis} {hv}", L, W, push, excl=f"ah.{hl}"))

    # Hándicap europeo (3 vías)
    for h in (-3, -2, -1, 1, 2, 3):
        pw = P(M, lambda x, y: x - y + h > 0)
        pd = P(M, lambda x, y: x - y + h == 0)
        pl = 1 - pw - pd
        if not args.todas_lineas and max(pw, pd, pl) > 0.93:
            continue
        hl = fmt_linea(h, True)
        filas += [Fila("eh", f"eh.{hl}.1", f"{loc} ({hl})", pw, excl=f"eh.{hl}"),
                  Fila("eh", f"eh.{hl}.X", f"Empate ({hl})", pd, excl=f"eh.{hl}"),
                  Fila("eh", f"eh.{hl}.2", f"{vis} ({hl})", pl, excl=f"eh.{hl}")]

    # Totales
    lineas_ou = [i / 4 for i in range(2, 27)]
    for ln in lineas_ou:
        W, L, push = over(T, ln)
        visible = args.todas_lineas or (0.06 <= W / max(EPS, W + L) <= 0.94)
        if not visible:
            continue
        s = fmt_linea(ln)
        filas.append(Fila("ou", f"ou.{s}.over", f"Más de {s} goles", W, L, push, excl=f"ou.{s}"))
        filas.append(Fila("ou", f"ou.{s}.under", f"Menos de {s} goles", L, W, push, excl=f"ou.{s}"))

    # Totales por equipo
    Th = [sum(M[x]) for x in range(n + 1)]
    Ta = [sum(M[x][y] for x in range(n + 1)) for y in range(n + 1)]
    for nombre, tag, Td in ((loc, "local", Th), (vis, "visitante", Ta)):
        for ln in (0.5, 1.0, 1.5, 2.0, 2.5, 3.5):
            W, L, push = over(Td, ln)
            if not args.todas_lineas and not (0.06 <= W / max(EPS, W + L) <= 0.94):
                continue
            s = fmt_linea(ln)
            filas.append(Fila("tt", f"tt.{tag}.{s}.over", f"{nombre} más de {s}", W, L, push, excl=f"tt.{tag}.{s}"))
            filas.append(Fila("tt", f"tt.{tag}.{s}.under", f"{nombre} menos de {s}", L, W, push, excl=f"tt.{tag}.{s}"))

    # Ambos marcan y combinados
    btts = P(M, lambda x, y: x >= 1 and y >= 1)
    filas += [Fila("btts", "btts.si", "Ambos marcan: sí", btts, excl="btts"),
              Fila("btts", "btts.no", "Ambos marcan: no", 1 - btts, excl="btts")]
    filas += [Fila("res_btts", "res_btts.1.si", f"{loc} gana y ambos marcan", P(M, lambda x, y: x > y and y >= 1), excl="res_btts"),
              Fila("res_btts", "res_btts.X.si", "Empate y ambos marcan", P(M, lambda x, y: x == y and x >= 1), excl="res_btts"),
              Fila("res_btts", "res_btts.2.si", f"{vis} gana y ambos marcan", P(M, lambda x, y: y > x and x >= 1), excl="res_btts"),
              Fila("res_btts", "res_btts.1.no", f"{loc} gana a cero", P(M, lambda x, y: x > y and y == 0), excl="res_btts"),
              Fila("res_btts", "res_btts.X.no", "Empate 0-0", M[0][0], excl="res_btts"),
              Fila("res_btts", "res_btts.2.no", f"{vis} gana a cero", P(M, lambda x, y: y > x and x == 0), excl="res_btts")]
    lt = args.linea_total
    sl = fmt_linea(lt)
    filas += [Fila("res_ou", f"res_ou.1.over{sl}", f"{loc} gana y más de {sl}", P(M, lambda x, y: x > y and x + y > lt), excl="res_ou"),
              Fila("res_ou", f"res_ou.1.under{sl}", f"{loc} gana y menos de {sl}", P(M, lambda x, y: x > y and x + y < lt), excl="res_ou"),
              Fila("res_ou", f"res_ou.X.over{sl}", f"Empate y más de {sl}", P(M, lambda x, y: x == y and x + y > lt), excl="res_ou"),
              Fila("res_ou", f"res_ou.X.under{sl}", f"Empate y menos de {sl}", P(M, lambda x, y: x == y and x + y < lt), excl="res_ou"),
              Fila("res_ou", f"res_ou.2.over{sl}", f"{vis} gana y más de {sl}", P(M, lambda x, y: y > x and x + y > lt), excl="res_ou"),
              Fila("res_ou", f"res_ou.2.under{sl}", f"{vis} gana y menos de {sl}", P(M, lambda x, y: y > x and x + y < lt), excl="res_ou")]

    # Marcador exacto
    celdas = sorted(((M[x][y], x, y) for x in range(n + 1) for y in range(n + 1)), reverse=True)
    top = celdas[:args.top_marcadores]
    for p, x, y in top:
        filas.append(Fila("cs", f"cs.{x}-{y}", f"{x}-{y}", p, excl="cs"))
    filas.append(Fila("cs", "cs.otro", "Cualquier otro marcador", 1 - sum(p for p, _, _ in top), excl="cs"))

    # Mitades: descanso/final, 1ª parte, 2ª parte
    f = args.ht_fraccion
    n1 = min(n, 8)
    H1 = matriz(lh * f, la * f, 0.0, n1)
    H2 = matriz(lh * (1 - f), la * (1 - f), 0.0, n1)
    htft = {a + "/" + b: 0.0 for a in "1X2" for b in "1X2"}
    ambas_mitades = 0.0
    mas_1h = mas_2h = igual = 0.0
    T1 = dist_total(H1)
    T2 = dist_total(H2)
    for k1 in range(len(T1)):
        for k2 in range(len(T2)):
            pk = T1[k1] * T2[k2]
            if k1 >= 1 and k2 >= 1:
                ambas_mitades += pk
            if k1 > k2:
                mas_1h += pk
            elif k2 > k1:
                mas_2h += pk
            else:
                igual += pk
    for x1 in range(n1 + 1):
        for y1 in range(n1 + 1):
            p1h = H1[x1][y1]
            if p1h < 1e-12:
                continue
            r1 = "1" if x1 > y1 else ("X" if x1 == y1 else "2")
            for x2 in range(n1 + 1):
                for y2 in range(n1 + 1):
                    p2h = H2[x2][y2]
                    if p2h < 1e-12:
                        continue
                    xf, yf = x1 + x2, y1 + y2
                    rf = "1" if xf > yf else ("X" if xf == yf else "2")
                    htft[r1 + "/" + rf] += p1h * p2h
    nombres = {"1": loc, "X": "Empate", "2": vis}
    for k, v in htft.items():
        a, b = k.split("/")
        filas.append(Fila("htft", f"htft.{k}", f"Descanso {nombres[a]} / Final {nombres[b]}", v, excl="htft"))
    p1h, pxh, p2h = resultado(H1)
    filas += [Fila("1h", "1h.1x2.1", f"1ª parte: {loc}", p1h, excl="1h.1x2"),
              Fila("1h", "1h.1x2.X", "1ª parte: empate", pxh, excl="1h.1x2"),
              Fila("1h", "1h.1x2.2", f"1ª parte: {vis}", p2h, excl="1h.1x2")]
    for ln in (0.5, 1.0, 1.5, 2.5):
        W, L, push = over(T1, ln)
        s = fmt_linea(ln)
        filas.append(Fila("1h", f"1h.ou.{s}.over", f"1ª parte: más de {s}", W, L, push, excl=f"1h.ou.{s}"))
        filas.append(Fila("1h", f"1h.ou.{s}.under", f"1ª parte: menos de {s}", L, W, push, excl=f"1h.ou.{s}"))
    b1 = P(H1, lambda x, y: x >= 1 and y >= 1)
    filas += [Fila("1h", "1h.btts.si", "1ª parte: ambos marcan", b1, excl="1h.btts"),
              Fila("1h", "1h.btts.no", "1ª parte: no ambos marcan", 1 - b1, excl="1h.btts")]
    p1s, pxs, p2s = resultado(H2)
    filas += [Fila("2h", "2h.1x2.1", f"2ª parte: {loc}", p1s, excl="2h.1x2"),
              Fila("2h", "2h.1x2.X", "2ª parte: empate", pxs, excl="2h.1x2"),
              Fila("2h", "2h.1x2.2", f"2ª parte: {vis}", p2s, excl="2h.1x2")]
    for ln in (0.5, 1.5, 2.5):
        W, L, push = over(T2, ln)
        s = fmt_linea(ln)
        filas.append(Fila("2h", f"2h.ou.{s}.over", f"2ª parte: más de {s}", W, L, push, excl=f"2h.ou.{s}"))
        filas.append(Fila("2h", f"2h.ou.{s}.under", f"2ª parte: menos de {s}", L, W, push, excl=f"2h.ou.{s}"))
    filas += [Fila("mitades", "mitades.ambas.si", "Gol en ambas mitades: sí", ambas_mitades, excl="mitades.ambas"),
              Fila("mitades", "mitades.ambas.no", "Gol en ambas mitades: no", 1 - ambas_mitades, excl="mitades.ambas"),
              Fila("mitades", "mitades.mas.1h", "Mitad con más goles: 1ª", mas_1h, excl="mitades.mas"),
              Fila("mitades", "mitades.mas.2h", "Mitad con más goles: 2ª", mas_2h, excl="mitades.mas"),
              Fila("mitades", "mitades.mas.igual", "Mitad con más goles: iguales", igual, excl="mitades.mas")]

    # Gana a cero / portería a cero
    wtn_l = P(M, lambda x, y: x >= 1 and y == 0)
    wtn_v = P(M, lambda x, y: y >= 1 and x == 0)
    cs_l, cs_v = Ta[0], Th[0]
    filas += [Fila("cero", "wtn.local.si", f"{loc} gana a cero: sí", wtn_l, excl="wtn.local"),
              Fila("cero", "wtn.local.no", f"{loc} gana a cero: no", 1 - wtn_l, excl="wtn.local"),
              Fila("cero", "wtn.visitante.si", f"{vis} gana a cero: sí", wtn_v, excl="wtn.visitante"),
              Fila("cero", "wtn.visitante.no", f"{vis} gana a cero: no", 1 - wtn_v, excl="wtn.visitante"),
              Fila("cero", "cs.local.si", f"{loc} portería a cero: sí", cs_l, excl="cs.local"),
              Fila("cero", "cs.local.no", f"{loc} portería a cero: no", 1 - cs_l, excl="cs.local"),
              Fila("cero", "cs.visitante.si", f"{vis} portería a cero: sí", cs_v, excl="cs.visitante"),
              Fila("cero", "cs.visitante.no", f"{vis} portería a cero: no", 1 - cs_v, excl="cs.visitante")]

    # Par/impar, margen, goles exactos
    par = sum(T[k] for k in range(len(T)) if k % 2 == 0)
    filas += [Fila("parimpar", "parimpar.par", "Total de goles par", par, excl="parimpar"),
              Fila("parimpar", "parimpar.impar", "Total de goles impar", 1 - par, excl="parimpar")]
    margen = [("local.1", f"{loc} por 1 gol", lambda x, y: x - y == 1),
              ("local.2", f"{loc} por 2 goles", lambda x, y: x - y == 2),
              ("local.3+", f"{loc} por 3 o más", lambda x, y: x - y >= 3),
              ("empate", "Empate (cualquier marcador)", lambda x, y: x == y),
              ("visitante.1", f"{vis} por 1 gol", lambda x, y: y - x == 1),
              ("visitante.2", f"{vis} por 2 goles", lambda x, y: y - x == 2),
              ("visitante.3+", f"{vis} por 3 o más", lambda x, y: y - x >= 3)]
    for k, nombre, cond in margen:
        filas.append(Fila("margen", f"margen.{k}", nombre, P(M, cond), excl="margen"))
    for k in range(0, 6):
        filas.append(Fila("goles", f"goles.{k}", f"Exactamente {k} goles", T[k], excl="goles"))
    filas.append(Fila("goles", "goles.6+", "6 o más goles", sum(T[6:]), excl="goles"))

    # Primer / último equipo en marcar
    lam_tot = lh + la
    p00 = M[0][0]
    pf_l = lh / lam_tot * (1 - p00)
    pf_v = la / lam_tot * (1 - p00)
    filas += [Fila("primero", "primero.local", f"Primer gol: {loc}", pf_l, excl="primero"),
              Fila("primero", "primero.visitante", f"Primer gol: {vis}", pf_v, excl="primero"),
              Fila("primero", "primero.ninguno", "Sin goles", p00, excl="primero"),
              Fila("primero", "ultimo.local", f"Último gol: {loc}", pf_l, excl="ultimo"),
              Fila("primero", "ultimo.visitante", f"Último gol: {vis}", pf_v, excl="ultimo"),
              Fila("primero", "ultimo.ninguno", "Sin goles", p00, excl="ultimo")]
    return filas


def filas_eliminatoria(M, lh, la, args, n):
    """Clasificación / título: 90 minutos + prórroga + penaltis (sin regla del gol de visitante)."""
    loc, vis = args.local, args.visitante
    a, b = 0, 0
    if args.eliminatoria == "vuelta":
        try:
            a, b = (int(v) for v in args.ida.replace(":", "-").split("-"))
        except Exception:
            sys.exit("--ida debe tener el formato L-V (goles de la ida del local de hoy - goles del visitante de hoy)")
    d0 = a - b
    q90_l = P(M, lambda x, y: (x - y) + d0 > 0)
    q90_v = P(M, lambda x, y: (x - y) + d0 < 0)
    p_et = 1 - q90_l - q90_v
    fe = args.factor_prorroga * (30.0 / 90.0)
    ME = matriz(lh * fe, la * fe, 0.0, min(n, 8))
    e_l, e_x, e_v = resultado(ME)
    pen_l = args.pen_local
    q_l = q90_l + p_et * (e_l + e_x * pen_l)
    q_v = q90_v + p_et * (e_v + e_x * (1 - pen_l))
    filas = [Fila("elim", "elim.local", f"{loc} se clasifica / gana el título", q_l, excl="elim"),
             Fila("elim", "elim.visitante", f"{vis} se clasifica / gana el título", q_v, excl="elim"),
             Fila("elim", "elim.prorroga.si", "Habrá prórroga", p_et, excl="elim.prorroga"),
             Fila("elim", "elim.prorroga.no", "No habrá prórroga", 1 - p_et, excl="elim.prorroga"),
             Fila("elim", "elim.penaltis.si", "Se decide en penaltis", p_et * e_x, excl="elim.penaltis"),
             Fila("elim", "elim.penaltis.no", "No se decide en penaltis", 1 - p_et * e_x, excl="elim.penaltis"),
             Fila("elim", "elim.local.90", f"{loc} se clasifica en 90 minutos", q90_l, excl="elim.90"),
             Fila("elim", "elim.visitante.90", f"{vis} se clasifica en 90 minutos", q90_v, excl="elim.90"),
             Fila("elim", "elim.empate.90", "Eliminatoria empatada tras 90 minutos", p_et, excl="elim.90")]
    ctx = {"ida_local": a, "ida_visitante": b, "prob_prorroga": p_et, "prob_penaltis": p_et * e_x}
    return filas, ctx


def filas_secundarias(args):
    """Córners y tarjetas con binomial negativa (independientes de los goles)."""
    filas = []
    loc, vis = args.local, args.visitante

    def bloque(nombre, tag, media_total, media_l, media_v, ratio, lineas_total, lineas_equipo, nmax):
        if media_l and media_v and not media_total:
            media_total = media_l + media_v
        if media_total:
            Tt = nb_pmf(media_total, ratio, nmax)
            for ln in lineas_total:
                W, L, push = over(Tt, ln)
                if not args.todas_lineas and not (0.06 <= W / max(EPS, W + L) <= 0.94):
                    continue
                s = fmt_linea(ln)
                filas.append(Fila(tag, f"{tag}.{s}.over", f"{nombre}: más de {s}", W, L, push, excl=f"{tag}.{s}"))
                filas.append(Fila(tag, f"{tag}.{s}.under", f"{nombre}: menos de {s}", L, W, push, excl=f"{tag}.{s}"))
        if media_l and media_v:
            Dl, Dv = nb_pmf(media_l, ratio, nmax), nb_pmf(media_v, ratio, nmax)
            pl = sum(Dl[x] * Dv[y] for x in range(nmax + 1) for y in range(nmax + 1) if x > y)
            pe = sum(Dl[x] * Dv[x] for x in range(nmax + 1))
            filas.extend([Fila(tag, f"{tag}.1x2.1", f"{nombre}: más {loc}", pl, excl=f"{tag}.1x2"),
                          Fila(tag, f"{tag}.1x2.X", f"{nombre}: empate", pe, excl=f"{tag}.1x2"),
                          Fila(tag, f"{tag}.1x2.2", f"{nombre}: más {vis}", 1 - pl - pe, excl=f"{tag}.1x2")])
            for eq, t, D in ((loc, "local", Dl), (vis, "visitante", Dv)):
                for ln in lineas_equipo:
                    W, L, push = over(D, ln)
                    if not args.todas_lineas and not (0.06 <= W / max(EPS, W + L) <= 0.94):
                        continue
                    s = fmt_linea(ln)
                    filas.append(Fila(tag, f"{tag}.{t}.{s}.over", f"{nombre} {eq}: más de {s}", W, L, push, excl=f"{tag}.{t}.{s}"))
                    filas.append(Fila(tag, f"{tag}.{t}.{s}.under", f"{nombre} {eq}: menos de {s}", L, W, push, excl=f"{tag}.{t}.{s}"))

    bloque("Córners", "corners", args.corners_total, args.corners_local, args.corners_visitante,
           args.dispersion_corners, [i / 2 for i in range(13, 30)], [2.5, 3.5, 4.5, 5.5, 6.5, 7.5], 40)
    bloque("Tarjetas", "tarjetas", args.tarjetas_total, args.tarjetas_local, args.tarjetas_visitante,
           args.dispersion_tarjetas, [i / 2 for i in range(3, 18)], [0.5, 1.5, 2.5, 3.5], 25)
    return filas


def parse_goleadores(spec):
    """'Nombre:cuota_goles:minutos[,...]'; prefijo '+' = suplente que entra a falta de esos minutos."""
    out = []
    if not spec:
        return out
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        sub = item.startswith("+")
        item = item.lstrip("+")
        partes = item.split(":")
        if len(partes) < 2:
            sys.exit(f"Goleador mal formado: '{item}' (usa Nombre:cuota_goles[:minutos])")
        nombre = partes[0].strip()
        share = float(partes[1])
        if share > 1:
            share /= 100.0
        minutos = float(partes[2]) if len(partes) > 2 else 90.0
        out.append((nombre, share, min(90.0, max(0.0, minutos)), sub))
    return out


def filas_goleadores(lh, la, p00, args):
    filas = []
    lam_tot = lh + la
    for tag, lam, spec in (("local", lh, args.goleadores_local), ("visitante", la, args.goleadores_visitante)):
        for nombre, share, minutos, sub in parse_goleadores(spec):
            mu = lam * share * minutos / 90.0
            anytime = 1 - exp(-mu)
            dos = 1 - exp(-mu) * (1 + mu)
            frac_equipo = lam / lam_tot
            if sub:   # entra en el minuto 90-minutos
                ventana = 1 - exp(-lam_tot * minutos / 90.0)
                primero = share * frac_equipo * (exp(-lam_tot * (90 - minutos) / 90.0) - exp(-lam_tot))
                ultimo = share * frac_equipo * ventana
            else:     # titular que juega los primeros 'minutos'
                primero = share * frac_equipo * (1 - exp(-lam_tot * minutos / 90.0))
                ultimo = share * frac_equipo * (exp(-lam_tot * (90 - minutos) / 90.0) - exp(-lam_tot))
            k = nombre.lower().replace(" ", "_")
            filas += [Fila("goleadores", f"gol.{k}.anytime", f"{nombre} marca", anytime),
                      Fila("goleadores", f"gol.{k}.2+", f"{nombre} marca 2 o más", dos),
                      Fila("goleadores", f"gol.{k}.primero", f"{nombre} primer goleador", primero),
                      Fila("goleadores", f"gol.{k}.ultimo", f"{nombre} último goleador", ultimo)]
    return filas


# ----------------------------------------------------------------------------
# Cuotas de la casa, margen, valor y stake
# ----------------------------------------------------------------------------
def cargar_cuotas(spec):
    if not spec:
        return {}
    spec = spec.strip()
    if os.path.isfile(spec):
        with open(spec, encoding="utf-8") as fh:
            data = json.load(fh)
    elif spec.startswith("{"):
        data = json.loads(spec)
    else:
        data = {}
        for par in spec.split(","):
            if "=" in par:
                k, v = par.split("=", 1)
                data[k.strip()] = float(v)
    out = {}
    for k, v in data.items():
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if v > 1.0:
            out[k.strip()] = v
    return out


def aplicar_cuotas(filas, cuotas, args):
    por_clave = {f.clave: f for f in filas}
    desconocidas = [k for k in cuotas if k not in por_clave]
    grupos = {}
    for f in filas:
        if f.excl:
            grupos.setdefault(f.excl, []).append(f)
    for f in filas:
        if f.clave in cuotas:
            f.cuota_casa = cuotas[f.clave]
            f.q_bruta = 1.0 / f.cuota_casa
    for gid, miembros in grupos.items():
        if all(m.cuota_casa for m in miembros) and len(miembros) >= 2:
            justas = probs_justas([m.cuota_casa for m in miembros], args.metodo_margen)
            for m, q in zip(miembros, justas):
                m.q_mercado = q
    for f in filas:
        if not f.cuota_casa:
            continue
        W, L = f.W, f.L
        if args.peso_mercado > 0 and f.q_mercado is not None:
            c = (1 - args.peso_mercado) * f.prob_cond + args.peso_mercado * f.q_mercado
            d = W + L
            W, L = c * d, (1 - c) * d
        f.W_final, f.L_final = W, L
        o = f.cuota_casa
        f.ev = W * (o - 1) - L
        if W + L > 0 and o > 1:
            f.kelly = max(0.0, (W * (o - 1) - L) / ((o - 1) * (W + L)))
        else:
            f.kelly = 0.0
        if f.ev >= args.ev_min and W >= args.prob_min:
            f.stake = round(min(f.kelly * args.kelly, args.stake_max) * args.banca, 2)
        else:
            f.stake = 0.0
    return desconocidas


# ----------------------------------------------------------------------------
# Salida
# ----------------------------------------------------------------------------
TITULOS = [
    ("1x2", "Resultado final (1X2)"), ("dc", "Doble oportunidad"), ("dnb", "Empate no válido (DNB)"),
    ("ah", "Hándicap asiático"), ("eh", "Hándicap europeo (3 vías)"), ("ou", "Total de goles (over/under)"),
    ("tt", "Goles por equipo"), ("btts", "Ambos marcan"), ("res_btts", "Resultado + ambos marcan"),
    ("res_ou", "Resultado + total"), ("cs", "Marcador exacto"), ("htft", "Descanso / final"),
    ("1h", "Primera parte"), ("2h", "Segunda parte"), ("mitades", "Mitades"),
    ("cero", "Gana a cero / portería a cero"), ("parimpar", "Par / impar"), ("margen", "Margen de victoria"),
    ("goles", "Número exacto de goles"), ("primero", "Primer / último equipo en marcar"),
    ("elim", "Clasificación / título (eliminatoria)"), ("corners", "Córners"), ("tarjetas", "Tarjetas"),
    ("goleadores", "Goleadores"),
]


def pct(p):
    return f"{100 * p:.1f}%"


def cuota(c):
    return "∞" if c == float("inf") else f"{c:.2f}"


def salida_md(filas, ctx, args, con_cuotas):
    out = []
    loc, vis = args.local, args.visitante
    out.append(f"# {loc} vs {vis} — mercados (modelo Poisson/Dixon-Coles)\n")
    out.append("## Parámetros del modelo\n")
    out.append("| Parámetro | Valor |\n|---|---|")
    out.append(f"| Origen de λ | {ctx['origen']} |")
    out.append(f"| λ base local / visitante | {ctx['lh_base']:.3f} / {ctx['la_base']:.3f} |")
    out.append(f"| Factores contextuales | local ×{args.factor_local:.3f}, visitante ×{args.factor_visitante:.3f} |")
    out.append(f"| **λ final local / visitante** | **{ctx['lh']:.3f} / {ctx['la']:.3f}** |")
    out.append(f"| Total esperado / supremacía | {ctx['lh'] + ctx['la']:.2f} / {ctx['lh'] - ctx['la']:+.2f} |")
    out.append(f"| ρ (Dixon-Coles) | {ctx['rho']:.3f} |")
    out.append(f"| Fracción de goles en la 1ª parte | {args.ht_fraccion:.2f} |")
    if ctx.get("mercado"):
        m = ctx["mercado"]
        s = f"1: {pct(m[0])}, X: {pct(m[1])}, 2: {pct(m[2])}"
        if m[3] is not None:
            s += f", over {fmt_linea(args.linea_ou)}: {pct(m[3])}"
        out.append(f"| Probabilidades justas del mercado usadas | {s} |")
    if ctx.get("elo_E") is not None:
        out.append(f"| Expectativa Elo del local (1 = victoria, 0.5 = empate) | {ctx['elo_E']:.3f} |")
    if ctx.get("ida_local") is not None:
        out.append(f"| Ida (goles local de hoy - visitante de hoy) | {ctx['ida_local']}-{ctx['ida_visitante']} |")
    if con_cuotas:
        out.append(f"| Banca / Kelly fraccional / stake máx. | {args.banca:.0f} / {args.kelly:.2f} / {100 * args.stake_max:.1f}% |")
        out.append(f"| EV mínimo / peso del mercado / método margen | {100 * args.ev_min:.1f}% / {args.peso_mercado:.2f} / {args.metodo_margen} |")
    out.append("")

    res = ctx["resumen"]
    out.append("## Resumen rápido\n")
    out.append(f"- 1X2: **{pct(res['p1'])} / {pct(res['px'])} / {pct(res['p2'])}** "
               f"(cuotas justas {cuota(1 / res['p1'])} / {cuota(1 / res['px'])} / {cuota(1 / res['p2'])})")
    out.append(f"- Marcador más probable: **{res['cs']}** ({pct(res['cs_p'])})")
    out.append(f"- Más de 2.5 goles: **{pct(res['over25'])}** · Ambos marcan: **{pct(res['btts'])}**")
    out.append("")

    solo = set(args.solo.split(",")) if args.solo else None
    por_grupo = {}
    for f in filas:
        por_grupo.setdefault(f.grupo, []).append(f)
    for gid, titulo in TITULOS:
        if gid not in por_grupo or (solo and gid not in solo):
            continue
        out.append(f"## {titulo}\n")
        if con_cuotas:
            out.append(f"| Clave | Selección | Prob. | Devuelta | Cuota justa | Cuota mín. (EV≥{100 * args.ev_min:.0f}%) | Cuota casa | Prob. mercado | EV | Stake |")
            out.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        else:
            out.append(f"| Clave | Selección | Prob. | Devuelta | Cuota justa | Cuota mín. (EV≥{100 * args.ev_min:.0f}%) |")
            out.append("|---|---|---:|---:|---:|---:|")
        for f in por_grupo[gid]:
            push = pct(f.push) if f.push > 0.0005 else "—"
            base = f"| `{f.clave}` | {f.seleccion} | {pct(f.W)} | {push} | {cuota(f.cuota_justa)} | {cuota(f.cuota_min(args.ev_min))} |"
            if con_cuotas:
                if f.cuota_casa:
                    qm = pct(f.q_mercado) if f.q_mercado is not None else f"{pct(f.q_bruta)}*"
                    ev = f"**{100 * f.ev:+.1f}%**" if f.ev >= args.ev_min else f"{100 * f.ev:+.1f}%"
                    stake = f"{f.stake:.2f}" if f.stake else "—"
                    base += f" {f.cuota_casa:.2f} | {qm} | {ev} | {stake} |"
                else:
                    base += " — | — | — | — |"
            out.append(base)
        out.append("")
    if con_cuotas:
        valor = sorted([f for f in filas if f.stake], key=lambda f: -f.ev)
        out.append("## Apuestas con valor detectadas\n")
        if not valor:
            out.append(f"Ninguna selección supera el EV mínimo del {100 * args.ev_min:.0f}% con las cuotas facilitadas.")
        else:
            out.append("| Selección | Cuota casa | Prob. modelo | EV | Kelly pleno | Stake sugerido |")
            out.append("|---|---:|---:|---:|---:|---:|")
            for f in valor:
                out.append(f"| {f.seleccion} (`{f.clave}`) | {f.cuota_casa:.2f} | {pct(f.W_final)} | {100 * f.ev:+.1f}% | {100 * f.kelly:.1f}% | {f.stake:.2f} |")
        out.append("")
        out.append("\\* probabilidad implícita bruta (no se pudo quitar el margen porque faltan cuotas del resto del mercado).")
        if ctx.get("desconocidas"):
            out.append(f"\nClaves de cuotas no reconocidas (ignoradas): {', '.join(ctx['desconocidas'])}")
    out.append("\n_Las probabilidades son estimaciones de un modelo; ninguna apuesta es segura. Compara siempre con la cuota de cierre._")
    return "\n".join(out)


def salida_json(filas, ctx, args):
    data = {"version": VERSION, "local": args.local, "visitante": args.visitante,
            "parametros": {k: v for k, v in ctx.items() if k not in ("resumen", "desconocidas")},
            "resumen": ctx["resumen"], "mercados": {}, "valor": []}
    for f in filas:
        data["mercados"].setdefault(f.grupo, []).append({
            "clave": f.clave, "seleccion": f.seleccion, "prob": round(f.W, 5), "prob_perder": round(f.L, 5),
            "devuelta": round(f.push, 5), "cuota_justa": None if f.cuota_justa == float("inf") else round(f.cuota_justa, 3),
            "cuota_min": None if f.cuota_min(args.ev_min) == float("inf") else round(f.cuota_min(args.ev_min), 3),
            "cuota_casa": f.cuota_casa, "prob_mercado": None if f.q_mercado is None else round(f.q_mercado, 5),
            "ev": None if f.ev is None else round(f.ev, 4), "kelly": None if f.kelly is None else round(f.kelly, 4),
            "stake": f.stake})
    data["valor"] = [{"clave": f.clave, "seleccion": f.seleccion, "cuota_casa": f.cuota_casa, "prob": round(f.W_final, 5),
                      "ev": round(f.ev, 4), "stake": f.stake} for f in sorted(filas, key=lambda f: -(f.ev or -9)) if f.stake]
    if ctx.get("desconocidas"):
        data["cuotas_no_reconocidas"] = ctx["desconocidas"]
    return json.dumps(data, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_argument_group("Goles esperados (elige una vía)")
    g.add_argument("--xg-local", type=float, help="λ del local a 90 minutos")
    g.add_argument("--xg-visitante", type=float, help="λ del visitante a 90 minutos")
    g.add_argument("--desde-cuotas", type=float, nargs=3, metavar=("O1", "OX", "O2"), help="Cuotas 1X2 de la casa para invertirlas")
    g.add_argument("--cuotas-ou", type=float, nargs=2, metavar=("OVER", "UNDER"), help="Cuotas over/under que acompañan a --desde-cuotas")
    g.add_argument("--linea-ou", type=float, default=2.5, help="Línea de las cuotas over/under (por defecto 2.5)")
    g.add_argument("--elo-local", type=float)
    g.add_argument("--elo-visitante", type=float)
    g.add_argument("--ventaja-local", type=float, default=65.0, help="Ventaja de campo en puntos Elo (por defecto 65)")
    g.add_argument("--total", type=float, default=3.0, help="Total de goles esperado cuando se parte de Elo o no hay cuotas O/U (por defecto 3.0)")
    g.add_argument("--fuerzas", type=float, nargs=4, metavar=("ATA_L", "DEF_L", "ATA_V", "DEF_V"), help="Fuerzas relativas (1.0 = media)")
    g.add_argument("--media-local", type=float, default=1.65, help="Goles medios del local en la competición")
    g.add_argument("--media-visitante", type=float, default=1.35, help="Goles medios del visitante en la competición")
    g.add_argument("--factor-local", type=float, default=1.0, help="Multiplicador contextual del λ local")
    g.add_argument("--factor-visitante", type=float, default=1.0, help="Multiplicador contextual del λ visitante")
    m = p.add_argument_group("Modelo")
    m.add_argument("--rho", type=float, default=-0.06, help="Parámetro Dixon-Coles (por defecto -0.06)")
    m.add_argument("--ht-fraccion", type=float, default=0.45, help="Fracción de goles esperados en la 1ª parte (por defecto 0.45)")
    m.add_argument("--max-goles", type=int, default=10, help="Goles máximos por equipo en la matriz")
    m.add_argument("--linea-total", type=float, default=2.5, help="Línea para los mercados resultado + total")
    m.add_argument("--eliminatoria", choices=["unico", "vuelta"], help="Añade el mercado de clasificación (partido único o vuelta)")
    m.add_argument("--ida", default="0-0", help="Resultado de la ida como L-V desde la óptica de los equipos de hoy (local-visitante)")
    m.add_argument("--factor-prorroga", type=float, default=1.0, help="Multiplicador del ritmo goleador en la prórroga")
    m.add_argument("--pen-local", type=float, default=0.5, help="Probabilidad de que el local gane una tanda de penaltis")
    s = p.add_argument_group("Mercados secundarios")
    s.add_argument("--corners-total", type=float)
    s.add_argument("--corners-local", type=float)
    s.add_argument("--corners-visitante", type=float)
    s.add_argument("--dispersion-corners", type=float, default=1.3, help="Ratio varianza/media de los córners (por defecto 1.3)")
    s.add_argument("--tarjetas-total", type=float)
    s.add_argument("--tarjetas-local", type=float)
    s.add_argument("--tarjetas-visitante", type=float)
    s.add_argument("--dispersion-tarjetas", type=float, default=1.15, help="Ratio varianza/media de las tarjetas (por defecto 1.15)")
    s.add_argument("--goleadores-local", help="'Nombre:cuota_goles:minutos,...' (prefijo + para suplentes)")
    s.add_argument("--goleadores-visitante", help="Igual que --goleadores-local")
    c = p.add_argument_group("Cuotas de la casa y gestión de banca")
    c.add_argument("--cuotas", help="JSON en línea, fichero JSON o lista clave=cuota separada por comas")
    c.add_argument("--peso-mercado", type=float, default=0.0, help="Peso (0-1) de la probabilidad justa del mercado en la mezcla final")
    c.add_argument("--metodo-margen", choices=["potencia", "multiplicativo"], default="potencia")
    c.add_argument("--banca", type=float, default=1000.0)
    c.add_argument("--kelly", type=float, default=0.25, help="Fracción de Kelly (por defecto 0.25)")
    c.add_argument("--stake-max", type=float, default=0.03, help="Stake máximo como fracción de la banca (por defecto 0.03)")
    c.add_argument("--ev-min", type=float, default=0.03, help="EV mínimo para recomendar (por defecto 0.03 = 3%%)")
    c.add_argument("--prob-min", type=float, default=0.05, help="Probabilidad mínima del modelo para recomendar")
    o = p.add_argument_group("Salida")
    o.add_argument("--local", default="Local")
    o.add_argument("--visitante", default="Visitante")
    o.add_argument("--formato", choices=["md", "json"], default="md")
    o.add_argument("--solo", help="Grupos a mostrar separados por comas, p. ej. 1x2,ah,ou,btts")
    o.add_argument("--todas-lineas", action="store_true", help="Muestra todas las líneas, incluso las extremas")
    o.add_argument("--top-marcadores", type=int, default=12)
    o.add_argument("--version", action="version", version=VERSION)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    n = max(6, args.max_goles)
    ctx = {"rho": args.rho, "elo_E": None, "mercado": None}

    if args.xg_local is not None and args.xg_visitante is not None:
        lh, la = args.xg_local, args.xg_visitante
        ctx["origen"] = "λ indicados directamente"
    elif args.desde_cuotas:
        o1, ox, o2 = args.desde_cuotas
        ov, un = (args.cuotas_ou or (None, None))
        lh, la, merc = lambdas_desde_cuotas(o1, ox, o2, ov, un, args.linea_ou, args.total, args.rho, n, args.metodo_margen)
        ctx["origen"] = f"invertidos desde cuotas 1X2 {o1}/{ox}/{o2}" + (f" y O/U {fmt_linea(args.linea_ou)} {ov}/{un}" if ov else f" con total fijo {args.total}")
        ctx["mercado"] = merc
    elif args.elo_local is not None and args.elo_visitante is not None:
        lh, la, E = lambdas_desde_elo(args.elo_local, args.elo_visitante, args.ventaja_local, args.total, args.rho, n)
        ctx["origen"] = f"Elo {args.elo_local:.0f} vs {args.elo_visitante:.0f} (+{args.ventaja_local:.0f} local), total {args.total}"
        ctx["elo_E"] = E
    elif args.fuerzas:
        al, dl, av, dv = args.fuerzas
        lh, la = args.media_local * al * dv, args.media_visitante * av * dl
        ctx["origen"] = f"fuerzas ataque/defensa ({al}/{dl} vs {av}/{dv}) sobre medias {args.media_local}/{args.media_visitante}"
    else:
        sys.exit("Indica los goles esperados: --xg-local/--xg-visitante, --desde-cuotas, --elo-local/--elo-visitante o --fuerzas. Usa -h para ver la ayuda.")

    if lh <= 0 or la <= 0:
        sys.exit("Los goles esperados deben ser positivos.")
    ctx["lh_base"], ctx["la_base"] = lh, la
    lh *= args.factor_local
    la *= args.factor_visitante
    rho = rho_valido(lh, la, args.rho)
    if abs(rho - args.rho) > 1e-6:
        print(f"Aviso: rho recortado de {args.rho} a {rho:.4f} para mantener probabilidades válidas.", file=sys.stderr)
    ctx.update({"lh": lh, "la": la, "rho": rho})

    M = matriz(lh, la, rho, n)
    filas = construir_filas(M, lh, la, rho, args, n)
    if args.eliminatoria:
        fe, cx = filas_eliminatoria(M, lh, la, args, n)
        filas += fe
        ctx.update(cx)
    filas += filas_secundarias(args)
    filas += filas_goleadores(lh, la, M[0][0], args)

    p1, px, p2 = resultado(M)
    T = dist_total(M)
    best = max(((M[x][y], x, y) for x in range(n + 1) for y in range(n + 1)))
    ctx["resumen"] = {"p1": p1, "px": px, "p2": p2, "cs": f"{best[1]}-{best[2]}", "cs_p": best[0],
                      "over25": sum(T[3:]), "btts": P(M, lambda x, y: x >= 1 and y >= 1)}

    cuotas = cargar_cuotas(args.cuotas)
    con_cuotas = bool(cuotas)
    if con_cuotas:
        ctx["desconocidas"] = aplicar_cuotas(filas, cuotas, args)

    if args.formato == "json":
        print(salida_json(filas, ctx, args))
    else:
        print(salida_md(filas, ctx, args, con_cuotas))


if __name__ == "__main__":
    main()
