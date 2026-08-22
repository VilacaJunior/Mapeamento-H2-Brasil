import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from essential import *

entrada1 = (
    BASE / "dados_complementares" / "empresas_identificadas_complementadas.csv"
)
entrada2 = (
    BASE / "dados_analisados" / "dados_analisados_25_05_26_v1.xlsx"
)

saida1 = (
    BASE / "dados_analisados" / "dados_analisados.csv"
)

URL_PROJETOS_EPE = (
    "https://gisepeprd2.epe.gov.br/arcgis/rest/services/"
    "Hosted/Map/FeatureServer/0/query"
)
DISTANCIA_DUPLICIDADE_KM = 1.0
ABA_ENTRADA2 = 0
COLUNA_CNPJ_ENTRADA2 = "cnpj"
COLUNA_RELACAO_ENTRADA2 = "veredito"

st.set_page_config(
    page_title="Dashboard H₂",
    page_icon="🗺️",
    layout="wide",
)

def normalizar_cnpj2(serie: pd.Series) -> pd.Series:
    return (
        serie.astype("string")
        .str.replace(r"\D", "", regex=True)
        .str.zfill(14)
    )

def preparar_dados_analisados() -> Path:
    if not entrada1.exists():
        raise FileNotFoundError(
            f"Arquivo complementado não encontrado: "
            f"{entrada1}"
        )

    if not entrada2.exists():
        raise FileNotFoundError(
            f"Planilha de vereditos não encontrada: "
            f"{entrada2}"
        )

    # Não recria o arquivo se ele já estiver mais recente
    # que suas duas fontes.
    if saida1.exists():
        data_saida = saida1.stat().st_mtime

        data_mais_recente_das_entradas = max(
            entrada1.stat().st_mtime,
            entrada2.stat().st_mtime,
        )

        if data_saida >= data_mais_recente_das_entradas:
            return saida1

    df_complementado = pd.read_csv(
        entrada1,
        sep=";",
        dtype={
            "cnpj": "string",
            "cep": "string",
            "uf": "string",
        },
        encoding="utf-8-sig",
    )

    df_vereditos = pd.read_excel(
        entrada2,
        sheet_name=ABA_ENTRADA2,
        dtype={
            COLUNA_CNPJ_ENTRADA2: "string",
        },
    )

    colunas_complementado = {
        "cnpj",
        "lat",
        "lon",
    }

    colunas_ausentes = (
        colunas_complementado
        - set(df_complementado.columns)
    )

    if colunas_ausentes:
        raise ValueError(
            "Colunas ausentes no arquivo complementado: "
            f"{sorted(colunas_ausentes)}"
        )

    colunas_excel = {
        COLUNA_CNPJ_ENTRADA2,
        COLUNA_RELACAO_ENTRADA2,
    }

    colunas_ausentes = (
        colunas_excel
        - set(df_vereditos.columns)
    )

    if colunas_ausentes:
        raise ValueError(
            "Colunas ausentes na planilha de vereditos: "
            f"{sorted(colunas_ausentes)}. "
            "Colunas encontradas: "
            f"{df_vereditos.columns.tolist()}"
        )

    # Padroniza os CNPJs antes da correspondência.
    df_complementado["cnpj"] = normalizar_cnpj2(
        df_complementado["cnpj"]
    )

    df_vereditos[COLUNA_CNPJ_ENTRADA2] = (
        normalizar_cnpj2(
            df_vereditos[COLUNA_CNPJ_ENTRADA2]
        )
    )

    # Mantém somente as colunas necessárias do Excel.
    df_vereditos = df_vereditos[
        [
            COLUNA_CNPJ_ENTRADA2,
            COLUNA_RELACAO_ENTRADA2,
        ]
    ].copy()

    df_vereditos = df_vereditos.rename(
        columns={
            COLUNA_CNPJ_ENTRADA2: "cnpj",
            COLUNA_RELACAO_ENTRADA2: "Veredito",
        }
    )

    # Evita que CNPJs duplicados no Excel multipliquem linhas.
    df_vereditos = df_vereditos.drop_duplicates(
        subset=["cnpj"],
        keep="last",
    )

    # Equivalente ao PROCX.
    # how="left" mantém todos os registros complementados.
    df_analisados = df_complementado.merge(
        df_vereditos,
        on="cnpj",
        how="left",
        validate="many_to_one",
    )

    saida1.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df_analisados.to_csv(
        saida1,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )

    return saida1

def normalizar_texto(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().casefold()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return " ".join(texto.split())

def distancia_haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    raio_terra_km = 6371.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    diferenca_lat = math.radians(lat2 - lat1)
    diferenca_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(diferenca_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(diferenca_lon / 2) ** 2
    )

    return 2 * raio_terra_km * math.asin(math.sqrt(a))


@st.cache_data(ttl=86400)
def carregar_projetos_epe() -> pd.DataFrame:
    parametros = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }

    resposta = requests.get(
        URL_PROJETOS_EPE,
        params=parametros,
        timeout=30,
    )

    resposta.raise_for_status()
    dados = resposta.json()

    if "error" in dados:
        raise RuntimeError(
            f"Erro retornado pela EPE: {dados['error']}"
        )

    registros = []

    for feature in dados.get("features", []):
        atributos = feature.get("attributes") or {}
        geometria = feature.get("geometry") or {}

        lat = geometria.get("y")
        lon = geometria.get("x")

        if lat is None or lon is None:
            continue

        registros.append(
            {
                "cnpj": "",
                "nome": str(
                    atributos.get("nome") or ""
                ).strip(),
                "relacao_final": "",
                "relacao_exibicao": "Projeto EPE",
                "uf": "",
                "cidade_geo": str(
                    atributos.get("local") or ""
                ).strip(),
                "local_epe": str(
                    atributos.get("local") or ""
                ).strip(),
                "estagio_epe": str(
                    atributos.get("estagio") or ""
                ).strip(),
                "finalidade_epe": str(
                    atributos.get("finalidade") or ""
                ).strip(),
                "capacidade_epe": atributos.get("capacidade"),
                "valor_epe": atributos.get("valor"),
                "lat": float(lat),
                "lon": float(lon),
                "fonte_dado": "EPE",
                "polo_mais_proximo": "",
                "tipo_polo": "",
                "distancia_min_km": pd.NA,
                "cor": [45, 125, 210, 220],
            }
        )

    return pd.DataFrame(registros)


def remover_localizacoes_repetidas(
    df_epe: pd.DataFrame,
    df_existente: pd.DataFrame,
    limite_km: float,
) -> pd.DataFrame:
    """
    Remove um ponto da EPE quando ele estiver próximo de algum
    ponto já existente ou de outro ponto da própria EPE.
    """
    if df_epe.empty:
        return df_epe

    coordenadas_existentes = list(
        df_existente[["lat", "lon"]]
        .dropna()
        .itertuples(index=False, name=None)
    )

    registros_aceitos = []

    for _, projeto in df_epe.iterrows():
        lat_projeto = float(projeto["lat"])
        lon_projeto = float(projeto["lon"])

        repetido = any(
            distancia_haversine_km(
                lat_projeto,
                lon_projeto,
                float(lat_existente),
                float(lon_existente),
            )
            <= limite_km
            for lat_existente, lon_existente
            in coordenadas_existentes
        )

        if repetido:
            continue

        registros_aceitos.append(projeto)

        # Também impede repetições dentro dos próprios dados da EPE.
        coordenadas_existentes.append(
            (lat_projeto, lon_projeto)
        )

    if not registros_aceitos:
        return df_epe.iloc[0:0].copy()

    return pd.DataFrame(registros_aceitos).reset_index(
        drop=True
    )

# def posicionar_exterior_no_mapa(
#     df: pd.DataFrame,
# ) -> pd.DataFrame:
#     df = df.copy()

#     mascara_exterior = (
#         df["uf"].astype("string").str.strip().str.upper()
#         == "EX"
#     )

#     indices_exterior = df.index[mascara_exterior].tolist()

#     # Posição simbólica no Oceano Atlântico.
#     longitude_simbolica = -27.0
#     latitude_inicial = 3.0
#     espacamento = 2.5

#     for posicao, indice in enumerate(indices_exterior):
#         df.at[indice, "lat"] = (
#             latitude_inicial - posicao * espacamento
#         )

#         df.at[indice, "lon"] = longitude_simbolica

#         df.at[indice, "cidade_geo"] = (
#             "Localização no exterior"
#         )

#         df.at[indice, "localizacao_simbolica"] = True

#     df.loc[
#         ~mascara_exterior,
#         "localizacao_simbolica",
#     ] = False

#     return df

def carregar_dados() -> pd.DataFrame:
    caminho_dados = preparar_dados_analisados()

    df = pd.read_csv(
        caminho_dados,
        sep=";",
        dtype={
            "cnpj": "string",
            "cep": "string",
            "uf": "string",
            "Veredito": "string",
        },
        encoding="utf-8-sig",
    )

    # Padroniza a classificação.
    df["relacao_normalizada"] = (
        df["Veredito"].apply(normalizar_texto)
    )

    equivalencias = {
        "planta": "planta",
        "produz": "planta",
        "conceito de planta": "conceito de planta",
        "conceiito de planta": "conceito de planta",
        "potencial planta": "potencial planta",
        "potencial de planta": "potencial planta",
    }

    df["relacao_final"] = (
        df["relacao_normalizada"].map(equivalencias)
    )

    relacoes_permitidas = {
        "planta",
        "conceito de planta",
        "potencial planta",
    }

    # Somente estas três categorias entram no mapa.
    df = df[
        df["relacao_final"].isin(relacoes_permitidas)
    ].copy()

    # Converte e valida as coordenadas.
    df["lat"] = pd.to_numeric(
        df["lat"],
        errors="coerce",
    )

    df["lon"] = pd.to_numeric(
        df["lon"],
        errors="coerce",
    )

    if "distancia_min_km" in df.columns:
        df["distancia_min_km"] = pd.to_numeric(
            df["distancia_min_km"],
            errors="coerce",
        )

    df = df.dropna(
        subset=["lat", "lon"]
    ).copy()

    # Limites aproximados do território brasileiro.
    df = df[
        df["lat"].between(-34, 6)
        & df["lon"].between(-74, -32)
    ].copy()

    cores = {
        "planta": [102, 204, 102, 220],
        "conceito de planta": [0, 100, 0, 220],
        "potencial planta": [255, 215, 0, 220],
    }

    nomes_relacoes = {
        "planta": "Planta",
        "conceito de planta": "Conceito de planta",
        "potencial planta": "Potencial planta",
    }

    df["cor"] = df["relacao_final"].map(cores)

    df["relacao_exibicao"] = (
        df["relacao_final"].map(nomes_relacoes)
    )

    # Colunas usadas para compatibilizar com os projetos EPE.
    df["fonte_dado"] = "Pesquisa própria"
    df["nome"] = ""
    df["local_epe"] = ""
    df["estagio_epe"] = ""
    df["finalidade_epe"] = ""
    df["capacidade_epe"] = pd.NA
    df["valor_epe"] = pd.NA

    try:
        df_epe = carregar_projetos_epe()

        df_epe = remover_localizacoes_repetidas(
            df_epe=df_epe,
            df_existente=df,
            limite_km=DISTANCIA_DUPLICIDADE_KM,
        )

        df = pd.concat(
            [df, df_epe],
            ignore_index=True,
            sort=False,
        )

    except requests.RequestException as erro:
        st.warning(
            "Não foi possível consultar os projetos da EPE. "
            "Serão mostrados apenas os dados locais. "
            f"Erro: {erro}"
        )

    except Exception as erro:
        st.warning(
            "Os dados da EPE não puderam ser processados. "
            f"Erro: {erro}"
        )

    return df


try:
    df = carregar_dados()

except FileNotFoundError as erro:
    st.error(
        f"Arquivo não encontrado: {erro.filename}"
    )
    st.stop()

except ValueError as erro:
    st.error(str(erro))
    st.stop()

except Exception as erro:
    st.error(
        f"Não foi possível carregar os dados: {erro}"
    )
    st.stop()

st.title("Mapa de plantas de H₂", text_alignment="center")
st.caption("CNPJs com coordenadas e relação final classificada como: Planta, Conceito de Planta ou Potencial planta.", text_alignment="center")
st.markdown("---")

st.sidebar.header("Filtros")

ufs = sorted(
    uf
    for uf in df["uf"].dropna().unique().tolist()
    if str(uf).strip()
)

classificacoes = [
    "Planta",
    "Conceito de planta",
    "Potencial planta",
]

fontes = sorted(
    df["fonte_dado"].dropna().unique().tolist()
)

ufs_selecionadas = st.sidebar.multiselect(
    "Estado",
    options=ufs,
)

classificacoes_selecionadas = st.sidebar.multiselect(
    "Relação final",
    options=classificacoes,
)

fontes_selecionadas = st.sidebar.multiselect(
    "Fonte dos dados",
    options=fontes,
)

df_filtrado = df.copy()

if ufs_selecionadas:
    df_filtrado = df_filtrado[
        df_filtrado["uf"].isin(ufs_selecionadas)
    ]

if classificacoes_selecionadas:
    df_filtrado = df_filtrado[
        df_filtrado["relacao_exibicao"].isin(
            classificacoes_selecionadas
        )
    ]

if fontes_selecionadas:
    df_filtrado = df_filtrado[
        df_filtrado["fonte_dado"].isin(
            fontes_selecionadas
        )
    ]

coluna1, coluna2, coluna3, coluna4, coluna5 = st.columns(5)

coluna1.metric(
    "Total no mapa",
    len(df_filtrado),
)

coluna2.metric(
    "Plantas",
    (
        df_filtrado["relacao_final"]
        == "planta"
    ).sum(),
)

coluna3.metric(
    "Conceitos de planta",
    (
        df_filtrado["relacao_final"]
        == "conceito de planta"
    ).sum(),
)

coluna4.metric(
    "Potenciais plantas",
    (
        df_filtrado["relacao_final"]
        == "potencial planta"
    ).sum(),
)

coluna5.metric(
    "Projetos EPE",
    (
        df_filtrado["fonte_dado"] == "EPE"
    ).sum(),
)

if df_filtrado.empty:
    st.warning(
        "Nenhum registro corresponde aos filtros selecionados."
    )

else:
    camada_pontos = pdk.Layer(
        "ScatterplotLayer",
        data=df_filtrado,
        get_position="[lon, lat]",
        get_fill_color="cor",
        get_line_color=[40, 40, 40, 180],
        get_radius=7000,
        radius_min_pixels=5,
        radius_max_pixels=16,
        line_width_min_pixels=1,
        stroked=True,
        filled=True,
        pickable=True,
        auto_highlight=True,
    )

    visualizacao_inicial = pdk.ViewState(
        latitude=-14.235,
        longitude=-51.9253,
        zoom=3.2,
        pitch=0,
        bearing=0,
    )

    tooltip = {
        "html": """
            <b>Nome:</b> {nome}<br>
            <b>CNPJ:</b> {cnpj}<br>
            <b>Classificação:</b> {relacao_exibicao}<br>
            <b>Fonte:</b> {fonte_dado}<br>
            <b>UF:</b> {uf}<br>
            <b>Local:</b> {cidade_geo}<br>
            <b>Estágio EPE:</b> {estagio_epe}<br>
            <b>Finalidade EPE:</b> {finalidade_epe}<br>
            <b>Capacidade EPE:</b> {capacidade_epe}<br>
            <b>Investimento EPE:</b> {valor_epe}
        """,
        "style": {
            "backgroundColor": "#202020",
            "color": "white",
        },
    }

    mapa = pdk.Deck(
        layers=[camada_pontos],
        initial_view_state=visualizacao_inicial,
        tooltip=tooltip,
        map_style=None,
    )

    st.pydeck_chart(
        mapa,
        use_container_width=True,
    )

st.markdown(
    """
<div style="display:flex; gap:25px; align-items:center; margin-bottom:15px; flex-wrap:wrap;">
    <div style="display:flex; align-items:center;">
        <span style="display:inline-block; width:14px; height:14px; border-radius:50%; background-color:rgb(102,204,102); margin-right:6px;"></span>
        <span>Planta</span>
    </div>
    <div style="display:flex; align-items:center;">
        <span style="display:inline-block; width:14px; height:14px; border-radius:50%; background-color:rgb(0,100,0); margin-right:6px;"></span>
        <span>Conceito de planta</span>
    </div>
    <div style="display:flex; align-items:center;">
        <span style="display:inline-block; width:14px; height:14px; border-radius:50%; background-color:rgb(255,215,0); margin-right:6px;"></span>
        <span>Potencial planta</span>
    </div>
    <div style="display:flex; align-items:center;">
        <span style="display:inline-block; width:14px; height:14px; border-radius:50%; background-color:rgb(45,125,210); margin-right:6px;"></span>
        <span>Projeto EPE</span>
    </div>
</div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Visualizar os dados exibidos no mapa"):
    colunas_tabela = [
        "fonte_dado",
        "cnpj",
        "nome",
        "relacao_exibicao",
        "uf",
        "cidade_geo",
        "local_epe",
        "estagio_epe",
        "finalidade_epe",
        "capacidade_epe",
        "valor_epe",
        "polo_mais_proximo",
        "tipo_polo",
        "distancia_min_km",
        "lat",
        "lon",
    ]

    colunas_tabela = [
        coluna
        for coluna in colunas_tabela
        if coluna in df_filtrado.columns
    ]

    tabela = df_filtrado[
        colunas_tabela
    ].rename(
        columns={
            "cnpj": "CNPJ",
            "relacao_exibicao": "Relação final",
            "uf": "UF",
            "cidade_geo": "Cidade",
            "polo_mais_proximo": "Polo mais próximo",
            "tipo_polo": "Tipo de polo",
            "distancia_min_km": "Distância (km)",
            "lat": "Latitude",
            "lon": "Longitude",
            "fonte_dado": "Fonte",
            "nome": "Nome do projeto",
            "local_epe": "Local EPE",
            "estagio_epe": "Estágio EPE",
            "finalidade_epe": "Finalidade EPE",
            "capacidade_epe": "Capacidade EPE",
            "valor_epe": "Investimento EPE",
        }
    )

    st.dataframe(
        tabela,
        use_container_width=True,
        hide_index=True,
    )