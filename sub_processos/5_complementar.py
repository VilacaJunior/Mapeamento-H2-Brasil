import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from essential import *

entrada1 = BASE / "dados_complementares" / "CTF_APP"
entrada2 = BASE / "dados_identificados" / "empresas_identificadas.csv"
entrada3 = BASE / "dados_filtrados" / "empresas_filtradas.csv"
saida1 = BASE / "dados_complementares" / "CTF_APP_filtrado.csv"
saida2 = BASE / "dados_complementares" / "empresas_identificadas_complementadas.csv"
ARQUIVO_CACHE = BASE / "dados_complementares" / "cache_geocodificacao.json"

LIMITE_KM = 80

# CTF/APP ====================================================

if not saida1.exists():
    df_final1 = pd.DataFrame()

    for csv in entrada1.glob("*.csv"):
        df1 = pd.read_csv(csv, sep=";", encoding="latin1")
        df1 = df1[
            (df1["CÃ³digo da categoria"] == 15)
            & (df1["CÃ³digo da atividade"] == 1)
            & (df1["SituaÃ§Ã£o cadastral"] == "Ativa")
        ]
        df_final1 = pd.concat([df_final1, df1], ignore_index=True)

    df_final1.to_csv(saida1, sep=";", encoding="latin1", index=False)

else:
    print(f"CTF/APP filtrado já existe, usando arquivo existente: {saida1}")

# Inferencia Geografica

POLOS_H2 = [
    {"polo": "Suape/PE", "tipo": "porto_industrial", "lat": -8.398, "lon": -34.960},
    {"polo": "Camaçari/BA", "tipo": "petroquimico", "lat": -12.6964, "lon": -38.3234},
    {"polo": "Mataripe/Candeias/BA", "tipo": "refino_petroquimico", "lat": -12.7049, "lon": -38.5666},
    {"polo": "Triunfo/RS", "tipo": "petroquimico", "lat": -29.8740, "lon": -51.3874},
    {"polo": "Canoas/REFAP/RS", "tipo": "refino", "lat": -29.912, "lon": -51.183},
    {"polo": "Araucária/REPAR/PR", "tipo": "refino", "lat": -25.5874, "lon": -49.405},
    {"polo": "Cubatão/SP", "tipo": "industrial_siderurgico", "lat": -23.8711, "lon": -46.4287},
    {"polo": "ABC/Capuava/SP", "tipo": "petroquimico_industrial", "lat": -23.660, "lon": -46.470},
    {"polo": "Paulínia/REPLAN/SP", "tipo": "refino_petroquimico", "lat": -22.728, "lon": -47.138},
    {"polo": "Jacareí/SP", "tipo": "gases_industriais", "lat": -23.305, "lon": -45.965},
    {"polo": "Duque de Caxias/REDUC/RJ", "tipo": "refino_petroquimico", "lat": -22.7199, "lon": -43.2727},
    {"polo": "Volta Redonda/CSN/RJ", "tipo": "siderurgia", "lat": -22.523, "lon": -44.104},
    {"polo": "Santa Cruz/Ternium/RJ", "tipo": "siderurgia", "lat": -22.919, "lon": -43.678},
    {"polo": "Macaé/RJ", "tipo": "oleo_gas", "lat": -22.3833, "lon": -41.7667},
    {"polo": "Serra/Tubarão/ES", "tipo": "siderurgia_portuario", "lat": -20.252, "lon": -40.265},
    {"polo": "Vale do Aço/MG", "tipo": "siderurgia", "lat": -19.468, "lon": -42.536},
    {"polo": "Ouro Branco/MG", "tipo": "siderurgia", "lat": -20.526, "lon": -43.696},
    {"polo": "João Monlevade/MG", "tipo": "siderurgia", "lat": -19.812, "lon": -43.173},
    {"polo": "Barreiro/BH/MG", "tipo": "industrial_metalurgico", "lat": -19.988, "lon": -44.015},
    {"polo": "Uberaba/MG", "tipo": "fertilizantes_quimico", "lat": -19.747, "lon": -47.939},
    {"polo": "Barcarena/Vila do Conde/PA", "tipo": "alumina_aluminio_portuario", "lat": -1.5437, "lon": -48.7465},
    {"polo": "Marechal Deodoro/AL", "tipo": "quimico_cloroquimico", "lat": -9.710, "lon": -35.895},
    {"polo": "Laranjeiras/SE", "tipo": "fertilizantes_amonia", "lat": -10.805, "lon": -37.169},
    {"polo": "Pecém/CE", "tipo": "porto_industrial", "lat": -3.5497, "lon": -38.8112},
]

def limpar_numero(valor):
    return re.sub(r"\D", "", str(valor or ""))

def limpar_cnpj(valor):
    cnpj = limpar_numero(valor)
    return cnpj.zfill(14) if cnpj else ""

def limpar_cep(valor):
    cep = limpar_numero(valor)
    return cep.zfill(8) if cep else ""

def carregar_cache():
    path = Path(ARQUIVO_CACHE)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_cache(cache):
    with open(ARQUIVO_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def ler_arquivo_sem_header(caminho):
    """
    Lê arquivo copiado do Excel, separado por TAB.
    Usa:
    - primeira coluna como CNPJ
    - antepenúltima coluna como CEP
    - penúltima coluna como UF
    """
    linhas = []

    with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
        for linha in f:
            linha = linha.rstrip("\n")
            if not linha.strip():
                continue

            partes = linha.split("\t")

            if len(partes) < 4:
                continue

            cnpj = limpar_cnpj(partes[0])
            cep = limpar_cep(partes[-3])
            uf = str(partes[-2]).strip().upper()

            linhas.append({
                "cnpj": cnpj,
                "cep": cep,
                "uf_arquivo": uf,
                "linha_original": linha
            })

    df = pd.DataFrame(linhas)
    df = df.drop_duplicates(subset=["cnpj", "cep"]).reset_index(drop=True)
    return df

def buscar_brasilapi_cep_v2(cep):
    """
    Primeira tentativa: BrasilAPI CEP v2.
    Em alguns CEPs ela retorna coordenadas.
    """
    url = f"https://brasilapi.com.br/api/cep/v2/{cep}"

    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()
        location = data.get("location") or {}
        coordinates = location.get("coordinates") or {}

        lat = coordinates.get("latitude")
        lon = coordinates.get("longitude")

        if lat is None or lon is None:
            return None

        return {
            "lat": float(lat),
            "lon": float(lon),
            "fonte_geo": "BrasilAPI CEP v2",
            "cidade": data.get("city"),
            "uf": data.get("state"),
            "endereco": data.get("street"),
            "bairro": data.get("neighborhood"),
        }

    except Exception:
        return None

def buscar_viacep(cep):
    """
    Segunda tentativa: ViaCEP.
    ViaCEP não retorna latitude/longitude, mas retorna endereço para geocodificar.
    """
    url = f"https://viacep.com.br/ws/{cep}/json/"

    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()

        if data.get("erro"):
            return None

        return {
            "cep": data.get("cep"),
            "logradouro": data.get("logradouro"),
            "bairro": data.get("bairro"),
            "cidade": data.get("localidade"),
            "uf": data.get("uf"),
        }

    except Exception:
        return None

def geocodificar_nominatim(texto_busca):
    """
    Geocodificação pelo Nominatim/OpenStreetMap.
    Evita chamadas rápidas demais com sleep.
    """
    url = "https://nominatim.openstreetmap.org/search"

    headers = {
        "User-Agent": "h2-polos-auditoria-academica/1.0"
    }

    params = {
        "q": texto_busca,
        "format": "json",
        "limit": 1,
        "countrycodes": "br",
    }

    try:
        time.sleep(1.1)
        r = requests.get(url, headers=headers, params=params, timeout=20)

        if r.status_code != 200:
            return None

        data = r.json()

        if not data:
            return None

        item = data[0]

        return {
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "fonte_geo": "Nominatim/OpenStreetMap",
            "endereco_geocodificado": item.get("display_name"),
        }

    except Exception:
        return None

def geocodificar_cep(cep, cache):
    """
    Ordem:
    1. Usa cache local.
    2. Tenta BrasilAPI com coordenadas.
    3. Tenta ViaCEP + Nominatim.
    4. Tenta CEP bruto + Nominatim.
    """
    if cep in cache and cache[cep] is not None:
        return cache[cep]

    resultado = buscar_brasilapi_cep_v2(cep)

    if resultado is not None:
        cache[cep] = resultado
        salvar_cache(cache)
        return resultado

    viacep = buscar_viacep(cep)

    if viacep:
        partes_endereco = [
            viacep.get("logradouro"),
            viacep.get("bairro"),
            viacep.get("cidade"),
            viacep.get("uf"),
            cep,
            "Brasil"
        ]

        texto_busca = ", ".join([str(x) for x in partes_endereco if x])
        resultado = geocodificar_nominatim(texto_busca)

        if resultado is not None:
            resultado.update({
                "cidade": viacep.get("cidade"),
                "uf": viacep.get("uf"),
                "endereco": viacep.get("logradouro"),
                "bairro": viacep.get("bairro"),
            })

            cache[cep] = resultado
            salvar_cache(cache)
            return resultado

        # Fallback: cidade + UF
        if viacep.get("cidade") and viacep.get("uf"):
            texto_busca = f"{viacep.get('cidade')}, {viacep.get('uf')}, Brasil"
            resultado = geocodificar_nominatim(texto_busca)

            if resultado is not None:
                resultado.update({
                    "cidade": viacep.get("cidade"),
                    "uf": viacep.get("uf"),
                    "endereco": viacep.get("logradouro"),
                    "bairro": viacep.get("bairro"),
                    "observacao_geo": "Coordenada aproximada pelo município, não pelo CEP exato."
                })

                cache[cep] = resultado
                salvar_cache(cache)
                return resultado

    # Último fallback: CEP bruto
    resultado = geocodificar_nominatim(f"{cep}, Brasil")

    if resultado is not None:
        cache[cep] = resultado
        salvar_cache(cache)
        return resultado

    return None

def haversine_km(lat1, lon1, lat2, lon2):
    """
    Distância em km entre dois pontos geográficos.
    """
    R = 6371.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))
    return R * c

def calcular_distancias_para_polos(lat, lon):
    distancias = []

    for polo in POLOS_H2:
        d = haversine_km(lat, lon, polo["lat"], polo["lon"])

        distancias.append({
            "polo": polo["polo"],
            "tipo_polo": polo["tipo"],
            "distancia_km": round(d, 2)
        })

    distancias = sorted(distancias, key=lambda x: x["distancia_km"])
    return distancias

def adicionar_relacao(relacao_atual, nova_relacao):
    relacao_atual = str(relacao_atual or "").strip()

    if not relacao_atual:
        return nova_relacao

    partes = [p.strip() for p in relacao_atual.split(" e ")]

    if nova_relacao in partes:
        return relacao_atual

    return f"{relacao_atual} e {nova_relacao}"


def carregar_ctf_app_cnpjs():
    if not saida1.exists():
        print(f"[ALERTA] Arquivo CTF/APP filtrado não encontrado: {saida1}")
        return set()

    df_ctf = pd.read_csv(
        saida1,
        sep=";",
        dtype={"CNPJ": str},
        encoding="latin1"
    )

    df_ctf["cnpj"] = df_ctf["CNPJ"].apply(normalizar_cnpj)

    return set(df_ctf["cnpj"].dropna())


def carregar_ceps_filtrados():
    df_filtrados = pd.read_csv(
        entrada3,
        sep=",",
        dtype={"cnpj": str, "cep": str},
        encoding="utf-8"
    )

    df_filtrados["cnpj"] = df_filtrados["cnpj"].apply(normalizar_cnpj)
    df_filtrados["cep"] = df_filtrados["cep"].apply(limpar_cep)

    return df_filtrados[["cnpj", "cep", "uf", "municipio"]].drop_duplicates(
        subset=["cnpj"],
        keep="last"
    )

def main():
    cache = carregar_cache()

    df = pd.read_csv(
        entrada2,
        sep=";",
        dtype={"cnpj": str},
        encoding="utf-8-sig"
    )

    df["cnpj"] = df["cnpj"].apply(normalizar_cnpj)
    df["relacao"] = ""

    cnpjs_ctf_app = carregar_ctf_app_cnpjs()

    df.loc[
        df["cnpj"].isin(cnpjs_ctf_app),
        "relacao"
    ] = "CTF_APP"

    df_ceps = carregar_ceps_filtrados()

    df = df.merge(
        df_ceps,
        on="cnpj",
        how="left"
    )

    df["polo_mais_proximo"] = ""
    df["tipo_polo"] = ""
    df["distancia_min_km"] = pd.NA
    df["lat"] = pd.NA
    df["lon"] = pd.NA
    df["fonte_geo"] = ""
    df["cidade_geo"] = ""
    df["uf_geo"] = ""
    df["observacao_geo"] = ""

    df["distancia_min_km"] = df["distancia_min_km"].astype("Float64")
    df["lat"] = df["lat"].astype("Float64")
    df["lon"] = df["lon"].astype("Float64")

    total = len(df)

    for idx, row in df.iterrows():
        cnpj = row["cnpj"]
        cep = limpar_cep(row.get("cep", ""))

        print(f"[{idx + 1}/{total}] Complementando CNPJ {cnpj} | CEP {cep}")

        if not cep or len(cep) != 8:
            continue

        geo = geocodificar_cep(cep, cache)

        if geo is None:
            continue

        lat = geo["lat"]
        lon = geo["lon"]

        distancias = calcular_distancias_para_polos(lat, lon)
        melhor = distancias[0]

        df.at[idx, "polo_mais_proximo"] = melhor["polo"]
        df.at[idx, "tipo_polo"] = melhor["tipo_polo"]
        df.at[idx, "distancia_min_km"] = melhor["distancia_km"]
        df.at[idx, "lat"] = lat
        df.at[idx, "lon"] = lon
        df.at[idx, "fonte_geo"] = geo.get("fonte_geo", "")
        df.at[idx, "cidade_geo"] = geo.get("cidade", "")
        df.at[idx, "uf_geo"] = geo.get("uf", "")
        df.at[idx, "observacao_geo"] = geo.get("observacao_geo", "")

        if melhor["distancia_km"] <= LIMITE_KM:
            df.at[idx, "relacao"] = adicionar_relacao(
                df.at[idx, "relacao"],
                "80km"
            )

    df.to_csv(
        saida2,
        sep=";",
        index=False,
        encoding="utf-8-sig"
    )


    print("\nArquivos gerados:")
    print(f"- {saida2}")

    print("\nResumo de relações:")
    print(df["relacao"].replace("", "sem_relacao").value_counts(dropna=False))

if __name__ == "__main__":
    main()