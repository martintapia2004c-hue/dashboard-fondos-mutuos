import os
import shutil
import json
import numpy as np
import pandas as pd

RENOMBRES = {
    "SAN PEDRO": "VSPT",
    "ENDESA-CH": "ENELGXCH",
    "ENERSIS-CH": "ENELCHILE",
    "AESGENER": "AESANDES",
    "ITAUCORP": "ITAUCL",
    "ORO BLANCO": "PAMPA",
    "LAN": "LTM",
}

# Mes del evento: acciones con flujo = 0 ese mes (nombres ya renombrados)
EVENTOS = {
    201906: ["CHILE", "SM-CHILE B"],
    201604: ["ENDESA", "ENERSIS", "ENDESA-AM", "ENELGXCH", "ENERSIS-AM", "ENELCHILE"],
    201612: ["ENDESA-AM", "ENERSIS-AM", "ENELAM"],
    202607: ["NORTEGRAN", "PAMPA"],
}

# ---------- 0. Respaldos de los JSON originales (solo la primera vez) ----------
for nombre in ["flujo_industria.json", "peso_industria.json"]:
    respaldo = nombre.replace(".json", "_ANTES.json")
    if not os.path.exists(respaldo):
        shutil.copy(nombre, respaldo)

# ---------- 1. Leer la base corregida ----------
df = pd.read_csv("base_acciones.csv", sep=";", keep_default_na=False, na_values=[""],
                 usecols=["Mes", "Run Fondo", "FFM_6010100", "FFM_6010900", "FFM_6011200"])
df = df.rename(columns={"FFM_6010100": "Accion", "FFM_6010900": "Cant", "FFM_6011200": "Monto"})
df["P"] = (df["Mes"].str[3:7] + df["Mes"].str[0:2]).astype(int)

# ---------- 2 y 3. Posiciones por fondo y precio de referencia ----------
pos = df.groupby(["P", "Run Fondo", "Accion"])[["Cant", "Monto"]].sum().reset_index()

# Precio implícito por fondo = monto total (miles) x 1.000 / cantidad total
pos["Precio"] = (pos["Monto"] * 1000 / pos["Cant"]).where((pos["Cant"] > 0) & (pos["Monto"] > 0))

med = pos.groupby(["P", "Accion"])["Precio"].transform("median")
normal = pos[(pos["Precio"] >= 0.5 * med) & (pos["Precio"] <= 2 * med)]
pref = normal.groupby(["P", "Accion"])["Precio"].median().reset_index(name="Precio_ref")

pos = pos[["P", "Run Fondo", "Accion", "Cant"]]

# Canje ITAUCL 4.500:1 -> todo expresado en acciones nuevas
itau_viejo = (pos["Accion"] == "ITAUCL") & (pos["P"] <= 202304)
pos.loc[itau_viejo, "Cant"] = pos.loc[itau_viejo, "Cant"] / 4500
f8455 = (pos["Accion"] == "ITAUCL") & (pos["P"] == 202305) & (pos["Run Fondo"] == 8455)
pos.loc[f8455, "Cant"] = pos.loc[f8455, "Cant"] / 4500
pref.loc[(pref["Accion"] == "ITAUCL") & (pref["P"] <= 202304), "Precio_ref"] *= 4500
print("ITAUCL ajustado: filas antiguas", itau_viejo.sum(), "| fondo 8455 mayo-2023:", f8455.sum())

# ---------- 4. Cantidad del mes anterior (incluye fondos que vendieron todo) ----------
meses = sorted(pos["P"].unique())
siguiente = {meses[i]: meses[i + 1] for i in range(len(meses) - 1)}
print("Meses en la base:", len(meses), "| desde", meses[0], "hasta", meses[-1])

pos["en_t"] = 1
ant = pos.drop(columns=["en_t"]).copy()
ant["P"] = ant["P"].map(siguiente)
ant = ant.dropna(subset=["P"])
ant["P"] = ant["P"].astype(int)
ant = ant.rename(columns={"Cant": "Cant_ant"})

fl = pos.merge(ant, on=["P", "Run Fondo", "Accion"], how="outer")
fl["Cant"] = fl["Cant"].fillna(0)
fl["Cant_ant"] = fl["Cant_ant"].fillna(0)
fl["en_t"] = fl["en_t"].notna()
fl = fl[fl["P"] != meses[0]]

# Precio: el del mes; si nadie la tiene este mes (venta total), el del mes anterior
pref_ant = pref.copy()
pref_ant["P"] = pref_ant["P"].map(siguiente)
pref_ant = pref_ant.dropna(subset=["P"])
pref_ant["P"] = pref_ant["P"].astype(int)
pref_ant = pref_ant.rename(columns={"Precio_ref": "Precio_ant"})

fl = fl.merge(pref, on=["P", "Accion"], how="left").merge(pref_ant, on=["P", "Accion"], how="left")
fl["Precio_usado"] = fl["Precio_ref"].fillna(fl["Precio_ant"])
fl["Flujo"] = (fl["Cant"] - fl["Cant_ant"]) * fl["Precio_usado"] / 1000

# ---------- 5. Neutralizar eventos ----------
for p, acciones in EVENTOS.items():
    m = (fl["P"] == p) & fl["Accion"].isin(acciones)
    fl.loc[m, "Flujo"] = 0
    print("Neutralizado", p, ":", m.sum(), "filas")

# ---------- 6. Comparar con el cálculo anterior ----------
# Se excluyen: acciones tocadas por eventos, ventas totales y los 2 últimos meses
# (los 2 últimos se vuelven a descargar cada mes y pueden cambiar por fondos que informan tarde)
EXCLUIR = set(RENOMBRES.keys()) | set(RENOMBRES.values())
for acciones in EVENTOS.values():
    EXCLUIR |= set(acciones)
corte = meses[-2]

presentes = fl[fl["en_t"]].groupby(["P", "Accion"])["Flujo"].sum().reset_index()
with open("flujo_industria_ANTES.json", "r", encoding="utf-8") as f:
    viejo = pd.DataFrame(json.load(f))
viejo["Periodo"] = viejo["Periodo"].astype(int)

comp = presentes.merge(viejo, left_on=["P", "Accion"], right_on=["Periodo", "FFM_6010100"],
                       suffixes=("_nuevo", "_viejo"))
comp = comp[~comp["Accion"].isin(EXCLUIR) & (comp["P"] < corte)]
comp["dif"] = (comp["Flujo_nuevo"] - comp["Flujo_viejo"]).abs()
ok = comp["dif"] <= 1 + comp["Flujo_viejo"].abs() * 0.001
print()
print(f"Flujos: coinciden con el cálculo anterior {ok.sum()} de {len(comp)} ({ok.mean() * 100:.2f} %), meses antes de {corte}")
print("Mayores diferencias:")
print(comp[~ok].sort_values("dif", ascending=False).head(10)[["P", "Accion", "Flujo_nuevo", "Flujo_viejo"]].to_string(index=False))

# ---------- 7. Ventas totales agregadas ----------
salidas = fl[~fl["en_t"]]
print()
print("Ventas totales agregadas:", len(salidas), "filas,", round(salidas["Flujo"].sum() / 1000), "millones de $")
ind = fl.groupby(["P", "Accion"])["Flujo"].sum().reset_index()

# ---------- 8. Peso de cada acción en la industria (calculado desde la base) ----------
b = pd.read_csv("base_acciones.csv", sep=";", keep_default_na=False, na_values=[""],
                usecols=["Mes", "Run Fondo", "FFM_6010100", "FFM_6010900", "FFM_6011200"])
b = b[b["FFM_6010900"] > 0].copy()
b["P"] = (b["Mes"].str[3:7] + b["Mes"].str[0:2]).astype(int)
b["precio"] = b["FFM_6011200"] * 1000 / b["FFM_6010900"]
b["precio_ref"] = b.groupby(["P", "FFM_6010100"])["precio"].transform("median")
b["valor_calc"] = b["FFM_6010900"] * b["precio_ref"] / 1000
b["razon"] = b["valor_calc"] / b["FFM_6011200"]
b["razon_fondo"] = b.groupby(["P", "Run Fondo"])["razon"].transform("median")
b["valor"] = np.where(b["razon_fondo"] > 100, b["valor_calc"], b["FFM_6011200"])   # SI(dólar; calculado; monto)

pe = b.groupby(["P", "FFM_6010100"])["valor"].sum().reset_index()
pe["Peso"] = pe["valor"] / pe.groupby("P")["valor"].transform("sum") * 100
pe = pe.rename(columns={"valor": "Valor"})

# Comparar con el archivo anterior (mismo formato de Periodo que tenía)
with open("peso_industria_ANTES.json", "r", encoding="utf-8") as f:
    pj = json.load(f)
pv = pd.DataFrame(pj["data"], columns=pj["columns"])
pv["FFM_6010100"] = pv["FFM_6010100"].str.upper().str.strip().replace(RENOMBRES)
pv = pv.groupby(["Periodo", "FFM_6010100"], as_index=False)["Peso"].sum()
ejemplo = str(pv["Periodo"].iloc[0])
print()
print("Formato de Periodo en peso_industria_ANTES:", repr(ejemplo))


def a_numero(x):
    s = str(x)
    if "-" in s:
        return int(s[:4]) * 100 + int(s[5:7])           # "2015-01"
    if "/" in s:
        return int(s[3:7]) * 100 + int(s[:2])           # "01/2015"
    return int(s)                                        # 201501


pv["P"] = pv["Periodo"].map(a_numero)
cp = pe.merge(pv, on=["P", "FFM_6010100"], suffixes=("_nuevo", "_viejo"))
cp = cp[cp["P"] < corte]
cp["dif"] = (cp["Peso_nuevo"] - cp["Peso_viejo"]).abs()
ok_peso = cp["dif"] <= 0.05
print(f"Pesos: dentro de 0,05 pp del cálculo anterior {ok_peso.sum()} de {len(cp)} ({ok_peso.mean() * 100:.2f} %)")
print("Mayores diferencias de peso:")
print(cp.sort_values("dif", ascending=False).head(10)[["P", "FFM_6010100", "Peso_nuevo", "Peso_viejo"]].to_string(index=False))

# ---------- 9. Guardar solo si los dos cálculos coinciden ----------
if ok.mean() < 0.99 or ok_peso.mean() < 0.95:
    print()
    print("NO SE GUARDÓ: los cálculos no coinciden lo suficiente con los anteriores. Pégame esta salida.")
    raise SystemExit(1)

ind = ind.rename(columns={"P": "Periodo", "Accion": "FFM_6010100"})
ind.to_json("flujo_industria.json", orient="records", force_ascii=False)

# Periodo en el mismo formato que usaba peso_industria.json
if "-" in ejemplo:
    pe["Periodo"] = pe["P"].astype(str).str[:4] + "-" + pe["P"].astype(str).str[4:]
elif "/" in ejemplo:
    pe["Periodo"] = pe["P"].astype(str).str[4:] + "/" + pe["P"].astype(str).str[:4]
else:
    pe["Periodo"] = pe["P"]
pe["Valor"] = pe["Valor"].round(0)
pe["Peso"] = pe["Peso"].round(4)
pe = pe[["Periodo", "FFM_6010100", "Valor", "Peso"]]
pe.to_json("peso_industria.json", orient="split", index=False, force_ascii=False)

print()
print("GUARDADO: flujo_industria.json (", len(ind), "filas ) y peso_industria.json (", len(pe), "filas )")