import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from essential import *

# Objetificando as pastas/caminhos ====================================================

ORIG = BASE / "dados_brutos"
DEST = BASE / "dados_convertidos"
DEST.mkdir(parents=True, exist_ok=True)

# Informando-as ====================================================

print("BASE =", BASE)
print("ORIG =", ORIG)
print("DEST =", DEST)

if not ORIG.exists():
    raise FileNotFoundError(f"A pasta 'dados_brutos' não existe em: {ORIG}")

# Código de conversão ====================================================

arquivos = [p for p in ORIG.rglob("*") if p.is_file() and p.suffix.lower() == ".estabele"]

print(f"Arquivos .ESTABELE encontrados: {len(arquivos)}")
if len(arquivos) == 0:
    print("Nada para converter. Verifique se você EXTRAIOU os .zip e se os arquivos realmente terminam com .ESTABELE.")
    raise SystemExit(0)

print("\nIniciando conversão...\n")

for arquivo in arquivos:
    saida = DEST / (arquivo.name + ".csv")

    print(f"Convertendo: {arquivo.name} -> {saida.name}")

    with open(arquivo, "r", encoding="latin1", errors="replace") as fin, \
         open(saida, "w", encoding="utf-8", newline="") as fout:
        for linha in fin:
            fout.write(linha)

print("\n✔ CONVERSÃO FINALIZADA")
print("Arquivos limpos em:", DEST)
