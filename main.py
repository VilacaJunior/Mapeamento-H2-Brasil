# main.py
import sys
from essential import *

BASE = Path(__file__).resolve().parent
pasta_dc = BASE / "dados_convertidos"
arquivos_dc = list(pasta_dc.glob("*"))
pasta_df = BASE / "dados_filtrados"
arquivos_df = list(pasta_df.glob("*"))
pasta_ds = BASE / "dados_selecionados"
arquivos_ds = list(pasta_ds.glob("*"))
pasta_di = BASE / "dados_identificados"
arquivos_di = list(pasta_di.glob("*"))
pasta_dco = BASE / "dados_complementares"
arquivos_dco = list(pasta_dco.glob("*"))

# Etapa 1 - Conversão ====================================================

if arquivos_dc:
    print(f"ALERTA: existem {len(arquivos_dc)} arquivo(s) em {pasta_dc}, indo para o processo de filtro")
else:
    print("Iniciando conversão")
    subprocess.run(["python", "sub_processos/1_converter.py"], check=True)

# Etapa 2 - Filtro ====================================================

if arquivos_df:
    print(f"ALERTA: existem {len(arquivos_df)} arquivo(s) em {pasta_df}, indo para o processo de seleção prévia")
else:
    print("Iniciando filtro")
    subprocess.run(["python", "sub_processos/2_filtrar.py"], check=True)

# Etapa 3 - Seleção ====================================================

while True:
    arquivos_ds = list(pasta_ds.glob("*"))

    if len(arquivos_ds) == 2 and any(p.name == "dados_liquidos.json" for p in arquivos_ds):
        print("Seleção já concluída (dados_liquidos.json encontrado). Pulando etapa 3.")
        break

    if len(arquivos_ds) == 1:
        print(f"iniciando categorização de dados selecionados previamente")
        subprocess.run(["python", "sub_processos/3_selecionar.py"], check=True)
        break

    print(f"ALERTA: existem {len(arquivos_ds)} arquivo(s) em {pasta_ds}, para continuar, deixe apenas o arquivo CSV dos dados selecionados previamente")
    
    while True:
        r = input("Ir para a próxima etapa? (s/n)")
        if r == "s":
            break
        elif r == "n":
            break

        print("Responda com 's' ou 'n'!")
        continue

    if r == "s":
        break
    else:
        raise SystemExit
    
# Etapa 3.1 - Pré-Identificação ====================================================

while True:
    arquivos_ds = list(pasta_ds.glob("*"))
    if len(arquivos_ds) == 2 and any(p.name == "dados_liquidos.json" for p in arquivos_ds):
        print("Selecionamento concluído com sucesso!")
        break

    print("ALERTA: Selecionamento concluído, porém há arquivos temporários não previstos")
    while True:
        r = input("Ir para a próxima etapa? (s/n)")
        if r == "s":
            break
        elif r == "n":
            break

        print("Responda com 's' ou 'n'!")
        continue

    if r == "s":
        break
    else:
        raise SystemExit

# Etapa 4 - Identificação ====================================================

while True:
    arquivos_di = list(pasta_di.glob("*"))

    if len(arquivos_di) > 1 and any(p.name == "empresas_identificadas.json" for p in arquivos_di):
        print("Seleção já concluída (empresas_identificadas.json encontrado). Pulando etapa 4.")
        break

    if len(arquivos_di) == 0:
        print(f"iniciando identificação por I.A")
        subprocess.run(["python", "sub_processos/4_identificar.py"], check=True)
        break

    print(f"ALERTA: existem {len(arquivos_di)} arquivo(s) em {pasta_di}, para continuar, limpe a pasta")
    
    while True:
        r = input("Ir para a próxima etapa? (s/n)")
        if r == "s":
            break
        elif r == "n":
            break

        print("Responda com 's' ou 'n'!")
        continue

    if r == "s":
        break
    else:
        raise SystemExit

# Etapa 5 - Complementação ====================================================

while True:
    arquivos_dco = list(pasta_dco.glob("*"))
    if any(p.name == "empresas_identificadas_complementadas.csv" for p in arquivos_dco):
        print("Complementação concluída com sucesso!")
        break

    else:
        print(f"iniciando complementação")
        subprocess.run(["python", "sub_processos/5_complementar.py"], check=True)
        break

# Etapa 6 - Dashboard ====================================================

dashboard = BASE / "sub_processos" / "6_dashboard.py"

if not dashboard.exists():
    raise FileNotFoundError(
        f"Dashboard não encontrado: {dashboard}"
    )

print("\nProcessamento concluído!")
print("Iniciando dashboard...\n")

subprocess.run(
    [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard),
    ],
    check=True,
    cwd=BASE,
)