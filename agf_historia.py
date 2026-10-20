import os
import json
import numpy as np
import pandas as pd

# 1. Leer la base (solo filas con cantidad de acciones)
base = pd.read_csv("base_acciones.csv", sep=";", keep_default_na=False, na_values=[""])
print("Filas de la base:", len(base))
base = base[base["FFM_6010900"] > 0].copy()
print("Filas con cantidad > 0:", len(base))

# 2. Precio de referencia de cada acción en cada mes
base["precio"] = base["FFM_6011200"] * 1000 / base["FFM_6010900"]
base["precio_ref"] = base.groupby(["Mes", "FFM_6010100"])["precio"].transform("median")
base["valor_calc"] = base["FFM_6010900"] * base["precio_ref"] / 1000   # miles de $

# 3. Detectar fondos en dólares, mes a mes
base["razon"] = base["valor_calc"] / base["FFM_6011200"]
base["razon_fondo"] = base.groupby(["Mes", "Run Fondo"])["razon"].transform("median")
base["dolar"] = base["razon_fondo"] > 100
dolar_mes = base[base["dolar"]].groupby("Mes")["Run Fondo"].nunique()
print("Meses con algún fondo en dólares:", len(dolar_mes), "| máximo en un mes:", dolar_mes.max())

# 4. Valor final en miles de $: SI(dólar; valor calculado; monto propio)
base["valor"] = np.where(base["dolar"], base["valor_calc"], base["FFM_6011200"])

# 5. Pegar la AGF (los fondos que no estén en fondos.json quedan como "AGF NO IDENTIFICADA")
with open("fondos.json", encoding="utf-8") as f:
    j = json.load(f)
fondos = pd.DataFrame(j["data"], columns=j["columns"])
base = base.merge(fondos[["Run Fondo", "AGF"]], on="Run Fondo", how="left")
sin_agf = base[base["AGF"].isna()]
print("Filas sin AGF:", len(sin_agf), "| fondos:", sorted(sin_agf["Run Fondo"].unique().tolist()))
base["AGF"] = base["AGF"].fillna("AGF NO IDENTIFICADA")


# 6. Nombre corto de la AGF para el gráfico
def nombre_corto(nombre):
    nombre = " ".join(nombre.split())          # quita espacios dobles
    for quitar in ["ADMINISTRADORA GENERAL DE FONDOS", "ASSET MANAGEMENT", "S.A."]:
        nombre = nombre.replace(quitar, "")
    return " ".join(nombre.split())


base["AGF_corta"] = base["AGF"].apply(nombre_corto)
print()
print(base[["AGF", "AGF_corta"]].drop_duplicates().to_string(index=False))

# 7. Tabla final: un renglón por mes y AGF
agf = base.groupby(["Mes", "AGF_corta"])["valor"].sum().reset_index()
agf["Valor"] = (agf["valor"] / 1000).round(1)                                              # millones de $
agf["Peso"] = (agf["valor"] / agf.groupby("Mes")["valor"].transform("sum") * 100).round(2)  # % del mes
agf["Periodo"] = agf["Mes"].str[3:] + "-" + agf["Mes"].str[:2]                             # "09/2026" -> "2026-09"
agf = agf.rename(columns={"AGF_corta": "AGF"})[["Periodo", "AGF", "Valor", "Peso"]]
agf = agf.sort_values(["Periodo", "Valor"], ascending=[True, False])

# 8. Revisiones (sobre el último mes disponible)
ultimo = agf["Periodo"].max()
suma_pesos = agf.groupby("Periodo")["Peso"].sum()
print()
print("Meses:", agf["Periodo"].nunique(), "| filas:", len(agf))
print("Suma de pesos por mes: mín", suma_pesos.min(), "| máx", suma_pesos.max())
print()
print("Último mes:", ultimo)
print(agf[agf["Periodo"] == ultimo].head(10).to_string(index=False))
print("Total último mes:", round(agf[agf["Periodo"] == ultimo]["Valor"].sum()), "millones de $")

# 9. Guardar para el dashboard
agf.to_json("agf_inversion.json", orient="split", index=False, force_ascii=False)
print("Guardado: agf_inversion.json")

# 10. Resumen por fondo y mes
base["Periodo"] = base["Mes"].str[3:] + "-" + base["Mes"].str[:2]
fon = base.groupby(["Periodo", "Run Fondo", "Nombre Fondo", "AGF_corta"]).agg(
    Valor=("valor", "sum"),
    Peso_fondo=("FFM_6011513", "sum"),
    Acciones=("FFM_6010100", "nunique"),
).reset_index()
fon["Valor"] = (fon["Valor"] / 1000).round(2)          # millones de $
fon["Peso_fondo"] = fon["Peso_fondo"].round(2)         # % del fondo en acciones chilenas
fon = fon.rename(columns={"Run Fondo": "Run", "Nombre Fondo": "Fondo", "AGF_corta": "AGF"})
print()
print("Fondo-mes:", len(fon), "| fondos distintos:", fon["Run"].nunique())
print("Fondo-mes con peso > 100 %:", (fon["Peso_fondo"] > 100.01).sum())
fon.to_json("fondos_mes.json", orient="split", index=False, force_ascii=False)
print("Guardado: fondos_mes.json")

# 11. Posiciones: un archivo por mes en la carpeta "posiciones"
os.makedirs("posiciones", exist_ok=True)
pos = base.groupby(["Periodo", "Run Fondo", "FFM_6010100"]).agg(
    Valor=("valor", "sum"),
    Peso=("FFM_6011513", "sum"),
).reset_index()
pos["Valor"] = (pos["Valor"] / 1000).round(2)
pos["Peso"] = pos["Peso"].round(2)
pos = pos.rename(columns={"Run Fondo": "Run", "FFM_6010100": "Accion"})
for periodo, tabla in pos.groupby("Periodo"):
    tabla[["Run", "Accion", "Valor", "Peso"]].to_json(
        f"posiciones/{periodo}.json", orient="split", index=False, force_ascii=False)
archivos = os.listdir("posiciones")
mb = sum(os.path.getsize(os.path.join("posiciones", a)) for a in archivos) / 1048576
print("Archivos en posiciones/:", len(archivos), "| tamaño total:", round(mb, 2), "MB")