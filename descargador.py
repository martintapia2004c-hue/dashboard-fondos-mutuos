import requests

CABECERAS = {"User-Agent": "Proyecto academico de Martin Tapia (estudiante de Magister en Finanzas, dashboard de fondos mutuos)"}
URL = "https://www.cmfchile.cl/institucional/estadisticas/ffm_download.php"

def descargar_mes(anio, mes):
    datos = {"mm": f"{mes:02d}", "aa": str(anio), "cartera": "NACI"}
    respuesta = requests.post(URL, data=datos, headers=CABECERAS)
    esperado = f"FFM_INV_NACI_{anio}{mes:02d}.txt"
    cabecera = respuesta.headers.get("Content-Disposition", "")
    if respuesta.status_code == 200 and esperado in cabecera:
        with open(f"Datos/{esperado}", "wb") as archivo:
            archivo.write(respuesta.content)
    else:
        print("AVISO: no se guardó", anio, mes, respuesta.status_code)
    return respuesta