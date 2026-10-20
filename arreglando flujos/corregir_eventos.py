import os
import shutil
import pandas as pd

BASE = "base_acciones.csv"
ORIGINAL = "base_acciones_ORIGINAL.csv"

# Guardar una copia original limpia (solo la primera vez)
if not os.path.exists(ORIGINAL):
    if os.path.exists("base_acciones_ANTES_PAMPA.csv"):
        shutil.copy("base_acciones_ANTES_PAMPA.csv", ORIGINAL)
    else:
        shutil.copy(BASE, ORIGINAL)

# Cambios de nombre 1 a 1 (viejo: nuevo)
RENOMBRES = {
    "SAN PEDRO": "VSPT",
    "ENDESA-CH": "ENELGXCH",
    "ENERSIS-CH": "ENELCHILE",
    "AESGENER": "AESANDES",
    "ITAUCORP": "ITAUCL",
    "ORO BLANCO": "PAMPA",
    "LAN": "LTM",
}

df = pd.read_csv(ORIGINAL, sep=";", keep_default_na=False, na_values=[""])
print("Filas leídas:", len(df))
df["FFM_6010100"] = df["FFM_6010100"].str.upper().str.strip()

for viejo, nuevo in RENOMBRES.items():
    n = (df["FFM_6010100"] == viejo).sum()
    ambos = df[df["FFM_6010100"].isin([viejo, nuevo])].groupby(["Mes", "Run Fondo"])["FFM_6010100"].nunique()
    print(f"{viejo:11} -> {nuevo:10}: {n:6} filas | fondo-mes con ambos nombres: {(ambos == 2).sum()}")

df["FFM_6010100"] = df["FFM_6010100"].replace(RENOMBRES)
df.to_csv(BASE, sep=";", index=False)

print("Filas guardadas:", len(df))
print("Nombres viejos que quedan:", df["FFM_6010100"].isin(list(RENOMBRES.keys())).sum())