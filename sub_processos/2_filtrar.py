import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from essential import *

CNAE = "2014200"
STATUS = ("02","03")

# Objetificando as pastas/caminhos ====================================================

PASTA = (BASE / "dados_convertidos").as_posix() + "/*.csv"
PASTA_SAIDA = BASE / "dados_filtrados"
PASTA_SAIDA.mkdir(exist_ok=True)
SAIDA = (PASTA_SAIDA / "empresas_filtradas.csv").as_posix()

# Inicinado código DuckDB de filtro ====================================================

con = duckdb.connect()
query = f"""
COPY (
  SELECT
    LPAD(column00, 8, '0') || LPAD(column01, 4, '0') || LPAD(column02, 2, '0') AS cnpj,
    column04 AS nome_fantasia,
    column05 AS situacao_cadastral,
    column09 AS pais,
    column11 AS cnae_principal,
    column15 AS numero,
    column16 AS complemento,
    column18 AS cep,
    column19 AS uf,
    column20 AS municipio,
    column27 AS email
  FROM read_csv('{PASTA}', delim=';', header=False, all_varchar=true)
  WHERE TRIM(column11) = '{CNAE}'
    AND TRIM(column05) IN {STATUS}
) TO '{SAIDA}' (HEADER, DELIMITER ',');
"""
con.execute(query)

print("\n✔ CSV FINAL GERADO EM:")
print(SAIDA)
