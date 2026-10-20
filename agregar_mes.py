import os
import time
import pandas as pd
from descargador import descargar_mes

ARCHIVO = "base_acciones_ORIGINAL.csv"


def clave(m):
    """'09/2026' -> (2026, 9), para ordenar meses correctamente."""
    return (int(m[3:]), int(m[:2]))


def bajar_mes(anio, mes, columnas_base):
    """Descarga un mes y devuelve sus filas ACC, o None si la CMF no tiene datos."""
    os.makedirs("Datos", exist_ok=True)
    descargar_mes(anio, mes)
    ruta = f"Datos/FFM_INV_NACI_{anio}{mes:02d}.txt"
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r", encoding="utf-8", errors="replace") as f:
        inicio = f.read(200)
    if os.path.getsize(ruta) < 1000 or "Sin informaci" in inicio:
        os.remove(ruta)
        return None

    df = pd.read_csv(ruta, sep=";", dtype=str, keep_default_na=False)
    if df.columns.tolist() != columnas_base[1:]:
        print(f"ERROR: las columnas de {mes:02d}/{anio} no son las de siempre. No se cambió nada.")
        raise SystemExit(1)
    acc = df[df["FFM_6010400"] == "ACC"].copy()
    if len(acc) == 0:
        print(f"ERROR: {mes:02d}/{anio} no trae acciones. No se cambió nada.")
        raise SystemExit(1)
    acc.insert(0, "Mes", f"{mes:02d}/{anio}")
    acc = acc.sort_values(acc.columns.tolist()).reset_index(drop=True)
    return acc


# 1. Leer la base completa como texto (así se reescribe exactamente igual)
base = pd.read_csv(ARCHIVO, sep=";", dtype=str, keep_default_na=False)
columnas_base = base.columns.tolist()
meses = sorted(base["Mes"].unique(), key=clave)
print("Filas en la base:", len(base), "| último mes:", meses[-1])

# 2. Meses a revisar: los 2 últimos que ya tenemos + el siguiente
anio, mes = clave(meses[-1])
mes = mes + 1
if mes == 13:
    mes, anio = 1, anio + 1
revisar = meses[-2:] + [f"{mes:02d}/{anio}"]
print("Meses a revisar:", revisar)

# 3. Descargar cada uno y reemplazarlo si la CMF tiene datos
cambios = []
for m in revisar:
    a, me = clave(m)
    acc = bajar_mes(a, me, columnas_base)
    time.sleep(1)                                   # pausa respetuosa entre descargas
    antes = (base["Mes"] == m).sum()
    if acc is None:
        print(f"{m}: sin datos en la CMF (antes había {antes} filas, no se toca)")
        continue
    base = base[base["Mes"] != m]                   # saca la versión vieja de ese mes
    base = pd.concat([base, acc], ignore_index=True)   # y pone la nueva
    print(f"{m}: antes {antes} filas | ahora {len(acc)} filas | fondos: {acc['Run Fondo'].nunique()}")
    if len(acc) != antes:
        cambios.append(m)

# 4. Ordenar por mes y guardar
base["_orden"] = base["Mes"].str[3:] + base["Mes"].str[:2]      # "09/2026" -> "202609"
base = base.sort_values("_orden", kind="stable").drop(columns="_orden")
base.to_csv(ARCHIVO, sep=";", index=False)

print()
print("Filas en la base ahora:", len(base))
print("HAY CAMBIOS en:" if cambios else "SIN CAMBIOS en número de filas.", ", ".join(cambios))