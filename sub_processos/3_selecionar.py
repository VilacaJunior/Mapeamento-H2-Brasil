# selecionar.py

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from essential import *

# Objetificando as pastas/caminhos ====================================================

entrada = BASE / "dados_selecionados" / "dados_selecionados_prev.csv"
saida1 = BASE / "dados_selecionados" / "dados_selecionados_prev.json"
saida2 = BASE / "dados_selecionados" / "empresas_filtradas.json"
saida3 = BASE / "dados_selecionados" / "dados_liquidos.json"
filtrados = BASE / "dados_filtrados" / "empresas_filtradas.csv"

# JSON dos selecionados ====================================================

df1 = pd.read_csv(entrada, sep=";", encoding="utf-8")
df1.to_json(saida1, orient="records", force_ascii=False, indent=2)

# JSON dos filtrados ====================================================

df2 = pd.read_csv(filtrados, sep=",", encoding="utf-8")
df2.to_json(saida2, orient="records", force_ascii=False, indent=2)

# Padronizando os jsons ====================================================

df1["cnpj"] = df1["cnpj"].astype(str).str.replace(r"\D", "", regex=True)
df2["cnpj"] = df2["cnpj"].astype(str).str.replace(r"\D", "", regex=True)

# Mantendo apenas os cnpj que não foram selecionados previamente ====================================================

df_selecionado = df2[~df2["cnpj"].isin(df1["cnpj"])]
df_selecionado.to_json(saida3, orient="records", force_ascii=False, indent=2)

# Apagando arquivos temporários ====================================================

saida1.unlink(missing_ok=True); saida2.unlink(missing_ok=True)