import os
import shutil

CARPETA = "sitio"
ARCHIVOS = ["flujo_industria.json", "peso_industria.json",
            "cmf_patrimonio_industria.json", "cmf_patrimonio_tipo.json"]

os.makedirs(CARPETA, exist_ok=True)

# La página de inicio de un sitio debe llamarse index.html
shutil.copy("dashboard6.html", os.path.join(CARPETA, "index.html"))

for nombre in ARCHIVOS:
    shutil.copy(nombre, os.path.join(CARPETA, nombre))
# Archivos extra: administradoras, fondos y posiciones por mes
shutil.copy("agf_inversion.json", os.path.join(CARPETA, "agf_inversion.json"))
shutil.copy("fondos_mes.json", os.path.join(CARPETA, "fondos_mes.json"))
shutil.copytree("posiciones", os.path.join(CARPETA, "posiciones"), dirs_exist_ok=True)

print("Contenido de la carpeta sitio:")
total = 0
for nombre in sorted(os.listdir(CARPETA)):
    tam = os.path.getsize(os.path.join(CARPETA, nombre))
    total += tam
    print(f"  {nombre:35} {tam / 1048576:6.2f} MB")
print(f"  {'TOTAL':35} {total / 1048576:6.2f} MB")

# Revisar qué archivos pide la página (deben estar todos en la carpeta)
print()
print("Archivos que pide la página:")
with open(os.path.join(CARPETA, "index.html"), "r", encoding="utf-8") as f:
    for n, linea in enumerate(f, 1):
        if ".json" in linea:
            print(f"  línea {n}: {linea.strip()[:110]}")