# identificar.py

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from essential import *

# Objetificando as pastas/caminhos ====================================================

entrada1 = BASE / "dados_selecionados" / "dados_liquidos.json"
entrada2 = BASE / "dados_selecionados" / "dados_selecionados_prev.csv"
saida1 = BASE / "dados_identificados" / "empresas_identificadas.json"
saida2 = BASE / "dados_coletados"
saida3 = saida2 / "dados_triados.json"
saida4 = BASE / "dados_identificados" / "empresas_identificadas.csv"

# Variaveis de Controle ====================================================

REPROCESSAR_APENAS_IA = False
PAUSA_ENTRE_IAS = 20
REFAZER_BUSCA_SEM_MD = True
REFAZER_BUSCA_SE_SEARCHING_VAZIO = True

# Searching com Serper ====================================================


df = pd.read_json(entrada1, dtype={"cnpj": str})
df["cnpj"] = df["cnpj"].apply(normalizar_cnpj)
df["searching_urls"] = [[] for _ in range(len(df))]
df["IA_results"] = [[] for _ in range(len(df))]

if saida3.exists():
    df_antigo = pd.read_json(saida3, dtype={"cnpj": str})
    df_antigo["cnpj"] = df_antigo["cnpj"].apply(normalizar_cnpj)

    df["_cnpj_key"] = df["cnpj"].apply(normalizar_cnpj)
    df_antigo["_cnpj_key"] = df_antigo["cnpj"].apply(normalizar_cnpj)

    df_antigo = df_antigo.drop_duplicates(subset=["_cnpj_key"], keep="last")
    antigo_por_cnpj = df_antigo.set_index("_cnpj_key")

    for idx, row in df.iterrows():
        cnpj_key = row["_cnpj_key"]

        if cnpj_key in antigo_por_cnpj.index:
            antigo = antigo_por_cnpj.loc[cnpj_key]

            if "searching_urls" in antigo:
                df.at[idx, "searching_urls"] = antigo["searching_urls"]

            if "IA_results" in antigo:
                df.at[idx, "IA_results"] = antigo["IA_results"]

    df = df.drop(columns=["_cnpj_key"])

def salvar_progresso():
    df.to_json(
        saida3,
        orient="records",
        force_ascii=False,
        indent=2
    )
def apagar_markdowns(path_pasta):
    for path_md in path_pasta.glob("*.md"):
        try:
            path_md.unlink()
        except Exception as e:
            print(f"[ERRO APAGANDO MD] arquivo={path_md} | erro={e}")

def gerar_dados_identificados():
    saida1.parent.mkdir(parents=True, exist_ok=True)

    df_final = pd.DataFrame(columns=["cnpj", "output"])

    if entrada2.exists():
        df_prev = pd.read_csv(
            entrada2,
            sep=";",
            dtype={"cnpj": str},
            encoding="utf-8"
        )

        df_prev["cnpj"] = df_prev["cnpj"].apply(normalizar_cnpj)

        if "output" not in df_prev.columns:
            if "H2" in df_prev.columns:
                df_prev = df_prev.rename(columns={"H2": "output"})
            else:
                df_prev["output"] = ""

        df_prev = df_prev[["cnpj", "output"]].copy()
        df_final = pd.concat([df_final, df_prev], ignore_index=True)

    df_triado = pd.read_json(saida3, dtype={"cnpj": str})
    df_triado["cnpj"] = df_triado["cnpj"].apply(normalizar_cnpj)
    df_triado["output"] = df_triado["IA_results"].apply(extrair_output_ia)
    df_incertos_nao_previstos = df_triado[
        df_triado["output"].apply(incerto_nao_previsto)
    ].copy()

    if not df_incertos_nao_previstos.empty:
        print("\nALERTA: existem incertos que NÃO são por falta de evidência nos markdowns.")
        print("Esses registros NÃO serão incluídos automaticamente em dados identificados.\n")

        for _, row in df_incertos_nao_previstos.iterrows():
            print(f"CNPJ: {row.get('cnpj')}")
            print(f"OUTPUT: {str(row.get('output'))[:500]}")
            print("-" * 80)

        while True:
            r = input("Continuar mesmo assim? (s/n) ").strip().lower()

            if r == "s":
                break

            if r == "n":
                raise SystemExit("Execução interrompida por haver incertos não previstos.")

            print("Responda com 's' ou 'n'.")

    df_triado = df_triado[
        df_triado.apply(
            lambda row: (
                output_de_interesse(row["output"])
                or (
                    output_nao_produz(row["output"])
                    and tem_mencao_ancora_no_registro(row)
                )
            ),
            axis=1
        )
    ].copy()

    df_triado = df_triado[["cnpj", "output"]].copy()

    df_final = pd.concat([df_final, df_triado], ignore_index=True)

    df_final = df_final.drop_duplicates(
        subset=["cnpj"],
        keep="last"
    )

    df_csv = df_final.copy()
    df_csv["output"] = df_csv["output"].apply(extrair_label_output)

    df_csv.to_csv(
        saida4,
        sep=";",
        index=False,
        encoding="utf-8-sig"
    )

    df_final.to_json(
        saida1,
        orient="records",
        force_ascii=False,
        indent=2
    )

    print(f"Dados identificados salvos em: {saida4}")

async def main():
    saida2.mkdir(parents=True, exist_ok=True)

    for idx, row in df.iterrows():
        path_pasta = saida2 / nome_pasta(row.get("cnpj"))
        pasta_existe = path_pasta.exists()

        if registro_completo(df.loc[idx]) and not REPROCESSAR_APENAS_IA:
            print(f"CNPJ {row.get('cnpj')} já completo, pulando...")
            continue

        path_pasta.mkdir(parents=True, exist_ok=True)

        print(f"Processando/retomando CNPJ {row.get('cnpj')}...")

        markdowns_existentes = list(path_pasta.glob("*.md"))
        buscas_existentes = lista_preenchida(df.at[idx, "searching_urls"])

        inconsistente_sem_pasta = not pasta_existe
        inconsistente_sem_buscas = not buscas_existentes
        inconsistente_sem_markdowns = not markdowns_existentes

        rodar_tudo = (
            inconsistente_sem_pasta
            or inconsistente_sem_buscas
            or inconsistente_sem_markdowns
        )

        if rodar_tudo:
            print(f"CNPJ {row.get('cnpj')} inconsistente; refazendo Serper + Crawl4AI...")

            apagar_markdowns(path_pasta)
            markdowns_existentes = []

            buscas = rodar_queries(row)
            df.at[idx, "searching_urls"] = buscas

        else:
            print(f"CNPJ {row.get('cnpj')} consistente; refazendo apenas IA...")
            buscas = df.at[idx, "searching_urls"]

# Crawl com Crawl4AI ====================================================

        cont = len(list(path_pasta.glob("*.md"))) + 1
        urls_crawleadas = set()

        if rodar_tudo:
            for busca in buscas:
                for dici in busca["results"]:
                    url = (dici["url"])
                    if ".xml" in url.lower():
                        continue
                    if url in urls_crawleadas:
                        continue
                    urls_crawleadas.add(url)
                    str_md = await crawler_url(url)
                    if not str_md:
                        continue

                    nome = f"{cont:03d}_{nome_md(str_md)}"
                    path_md = path_pasta / nome

                    metadata_md = (
                        "---\n"
                        f"cnpj: {json.dumps(str(row.get('cnpj')), ensure_ascii=False)}\n"
                        f"query: {json.dumps(busca.get('query', ''), ensure_ascii=False)}\n"
                        f"url: {json.dumps(url, ensure_ascii=False)}\n"
                        f"title: {json.dumps(dici.get('title', ''), ensure_ascii=False)}\n"
                        f"accessed_at: {json.dumps(dici.get('accessed_at', ''), ensure_ascii=False)}\n"
                        f"arquivo: {json.dumps(nome, ensure_ascii=False)}\n"
                        "---\n\n"
                    )

                    with open(path_md, "w", encoding="utf-8") as arquivo:
                        arquivo.write(metadata_md)
                        arquivo.write(str_md)

                    cont += 1
        
# Identificação da I.A ====================================================

        time.sleep(PAUSA_ENTRE_IAS)
        resultado_ia = google_analise(path_pasta)
        df.at[idx, "IA_results"] = [resultado_ia]
        salvar_progresso()

asyncio.run(main())

salvar_progresso()
gerar_dados_identificados()
