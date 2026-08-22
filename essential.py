# essential.py

import os, time, json, pathlib, hashlib, requests, duckdb, subprocess, asyncio, re, math, unicodedata
import pandas as pd
import pydeck as pdk
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, HttpUrl, ValidationError, confloat
from typing import Literal, List, Any, Optional, Tuple, Dict
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode


# KEYS ====================================================

key_gemini = os.getenv("GEMINI_API_KEY")
key_serper = os.getenv("SERPER_API_KEY")


# IGNORE! ====================================================

CLIENT = None
CONFIG = None
CONFIG_JSON_ONLY = None

# Variavel de manutenção ====================================================

ancoras = [
    "White Martins", "Linde", "Air Liquide", "Messer", "Air Products", "IBG", "GEP"
]

# FUNÇÕES =================================================

def run_id():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds").replace(":", "-")

def isnull(x) -> bool:
    if x is None:
        return False
    if pd.isna(x):
        return False
    if str(x).strip() == "":
        return False
    return True

#def sha256_bytes(b: bytes) -> str:
    #return hashlib.sha256(b).hexdigest()

#def save_json(path: pathlib.Path, obj):
    #path.parent.mkdir(parents=True, exist_ok=True)
    #path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

#def save_bytes(path: pathlib.Path, b: bytes):
    #path.parent.mkdir(parents=True, exist_ok=True)
    #path.write_bytes(b)

def gemini_input(prompt: str, model="gemma-4-26b-a4b-it", config_override=None) -> str:
    global CLIENT, CONFIG

    if not key_gemini or key_gemini == "coloque sua chave":
        raise RuntimeError("Defina sua chave Gemini em key_gemini ou via variável de ambiente.")
    
    if CLIENT is None:
        CLIENT = genai.Client(api_key=key_gemini)
    if CONFIG is None:
        CONFIG = types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=700,
            system_instruction="Você é um auditor técnico."
        )

    cfg = config_override if config_override is not None else CONFIG
    resp = CLIENT.models.generate_content(
        model=model,
        contents=prompt,
        config=cfg,
    )
    return resp.text or ""

def _normalize_result(item: Dict[str, Any]) -> Dict[str, Any]:
    url = item.get("link") or item.get("url") or item.get("source") or ""
    title = item.get("title") or item.get("name") or ""
    hr = run_id()
    return {"url": url, "title": title, "accessed_at": hr}

def serper_searching(query = str, max_results = 3, gl: str = "br", hl: str = "pt") -> List[Dict[str, Any]]:
    api_key = key_serper
    url = "https://google.serper.dev/search"
    payload = {
        "q": query,
        "num": max_results,
        "gl": gl,
        "hl": hl,
    }
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"[ERRO SERPER] query={query} | erro={e}")
        return []
    
    organic = data.get("organic", [])
    return [_normalize_result(r) for r in organic]

def nome_md(markdown: str, quantidade_palavras: int = 4) -> str:
    texto_limpo = re.sub(r"[#>*_`\[\]\(\)!]", " ", markdown)
    palavras = texto_limpo.split()[:quantidade_palavras]
    nome = "_".join(palavras)
    nome = re.sub(r'[\\/:*?"<>|]', "", nome)
    if not nome:
        nome = "pagina_extraida"
    return nome.lower()[:10] + ".md"

def nome_pasta(cnpj) -> str:
    cnpj_limpo = re.sub(r"\D", "", str(cnpj or ""))
    return cnpj_limpo.zfill(14) if cnpj_limpo else "cnpj_indefinido"

def rodar_queries(row):
    cnpj = str(row.get("cnpj", "")) if isnull(row.get("cnpj")) else ""
    nome = str(row.get("nome_fantasia", "")) if isnull(row.get("nome_fantasia")) else ""
    cnae = str(row.get("cnae_principal", "")) if isnull(row.get("cnpj")) else ""
    cep = str(row.get("cep", "")) if isnull(row.get("cep")) else ""
    email = str(row.get("email","")) if isnull(row.get("email")) else ""

    queries = []
    if cnpj and nome:
        queries.append(f'"{cnpj}" "{nome}"')
        queries.append(f'"{cnpj}" "{nome}" hidrogênio')
        queries.append(f'"{cnpj}" "{nome}" hydrogen')
    if cnpj:
        queries.append(f'"{cnpj}"')
        queries.append(f'"{cnpj}" hidrogênio')
        queries.append(f'"{cnpj}" hydrogen')
    if nome:
        queries.append(f'"{nome}" hidrogênio OR hidrogenio OR H2 OR hydrogen')
        queries.append(f'"{nome}" "produção de hidrogênio" OR "planta de hidrogênio" OR "unidade de hidrogênio" OR eletrólise OR eletrolise OR SMR OR "reforma a vapor"')
    if email and "@" in email:
        dominio = email.split("@")[-1].lower()
        dominios_genericos = {
            "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
            "yahoo.com.br", "icloud.com", "live.com", "uol.com.br",
            "terra.com.br", "bol.com.br", "contabil", "contabilidade", "contador", "escritorio",
            "assessoria", "consultoria"
                }
        if dominio not in dominios_genericos:
            queries.append(f'site:{dominio} hidrogênio')
            queries.append(f'site:{dominio} hydrogen')

    resultados = []
    for q in queries:
        busca = serper_searching(q)
        resultados.append({
            "query": q,
            "results": busca
        })
    return resultados

async def crawler_url(url):
    browser_config = BrowserConfig(
        headless=True
    )
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        process_iframes=True,
        exclude_external_links=False,
        stream=False
    )
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                config=run_config
            )

            if result.success:
                return result.markdown.raw_markdown
            else:
                print("Erro:", result.error_message)
                return None
    except Exception as e:
        print(f"[ERRO CRAWLER] url={url} | erro={e}")
        return None

def filtrar_contexto_por_keywords(
    texto: str,
    keywords: list[str],
    janela: int = 5000
) -> str:
    texto_lower = texto.lower()
    intervalos = []

    for kw in keywords:
        kw_lower = kw.lower()
        inicio_busca = 0

        while True:
            pos = texto_lower.find(kw_lower, inicio_busca)

            if pos == -1:
                break

            ini = max(0, pos - janela)
            fim = min(len(texto), pos + len(kw) + janela)
            intervalos.append((ini, fim))

            inicio_busca = pos + len(kw_lower)

    if not intervalos:
        return ""

    intervalos.sort()

    # Junta intervalos sobrepostos para evitar repetir muito texto.
    intervalos_unidos = []
    atual_ini, atual_fim = intervalos[0]

    for ini, fim in intervalos[1:]:
        if ini <= atual_fim:
            atual_fim = max(atual_fim, fim)
        else:
            intervalos_unidos.append((atual_ini, atual_fim))
            atual_ini, atual_fim = ini, fim

    intervalos_unidos.append((atual_ini, atual_fim))

    trechos = []
    for ini, fim in intervalos_unidos:
        trechos.append(texto[ini:fim])

    return "\n\n--- TRECHO FILTRADO ---\n\n".join(trechos)

def remover_metadados_md(texto: str) -> str:
    linhas = texto.splitlines(keepends=True)

    if not linhas:
        return texto

    i = 0
    while i < len(linhas) and not linhas[i].strip():
        i += 1

    if i >= len(linhas) or linhas[i].strip() != "---":
        return texto

    for j in range(i + 1, len(linhas)):
        if linhas[j].strip() == "---":
            return "".join(linhas[j + 1:])

    return texto

def google_analise(
    pasta: Path,
    model: str = "gemma-4-26b-a4b-it",
    limite_chars: int = 60000,
    key=None
    ):

    textos = []

    keywords = [
    "hidrogênio",
    "hidrogenio",
    "hydrogen",
    "h2",
    "produção de hidrogênio",
    "producao de hidrogenio",
    "planta de hidrogênio",
    "planta de hidrogenio",
    "unidade de hidrogênio",
    "unidade de hidrogenio",
    "geração de hidrogênio",
    "geracao de hidrogenio",
    "eletrólise",
    "eletrolise",
    "electrolysis",
    "reforma a vapor",
    "steam methane reforming",
    "smr",
    "White Martins",
    "Linde",
    "Air Liquide",
    "Messer",
    "Air Products",
    "IBG",
    "GEP"
]

    for path_md in sorted(pasta.glob("*.md")):
        try:
            conteudo = path_md.read_text(encoding="utf-8", errors="ignore")
            conteudo_sem_metadados = remover_metadados_md(conteudo)
            conteudo_filtrado = filtrar_contexto_por_keywords(
                conteudo_sem_metadados,
                keywords=keywords,
                janela=2000
            )

            if conteudo_filtrado.strip():
                textos.append(f"\n\n# ARQUIVO: {path_md.name}\n\n{conteudo_filtrado}")

        except Exception as e:
            print(f"[ERRO LENDO MD] arquivo={path_md} | erro={e}")

    contexto = "\n".join(textos)[:limite_chars]

    if not contexto.strip():
        return {
            "output": "incerto - Nenhum trecho com palavras-chave relevantes foi encontrado nos markdowns.",
            "horario": run_id()
        }

    prompt = f"""
Você é um auditor técnico de evidências públicas sobre produção de hidrogênio.

A base de empresas analisada já foi filtrada pelo CNAE 2014-2/00, fabricação de gases industriais.
Portanto, CNAE, descrição cadastral, CNPJ.biz, Econodata, Serasa, CNPJCheck ou páginas cadastrais NÃO são evidência suficiente para afirmar produção de H2.

Sua tarefa é responder se há evidência de que a própria empresa produz hidrogênio.

Empresas âncora consideradas relevantes:
{", ".join(ancoras)}

Regra sobre empresas âncora:
- Se qualquer empresa âncora for mencionada nos documentos, mas NÃO houver evidência direta de que a empresa analisada produz H2, responda "talvez".
- A simples menção a uma empresa âncora NÃO autoriza responder "produz_h2".
- Use "produz_h2" somente se houver evidência direta de produção de hidrogênio pela empresa analisada, ou evidência clara de que ela é filial, subsidiária, unidade operacional ou parte do mesmo grupo econômico de uma empresa âncora produtora.
- Se a menção à âncora for apenas comercial, notícia genérica, distribuidor autorizado, revenda, parceria, comparação, fornecedor, cliente ou resultado irrelevante de busca, responda "talvez", não "produz_h2".
- Se houver uma empresa âncora relevante, cite na própria resposta a frase curta onde ela aparece.

Critério principal de triagem:
- Esta é uma triagem operacional, não uma prova jurídica definitiva.
- Se os documentos analisados NÃO trouxerem evidência relevante de hidrogênio/H2, nem menção a empresa âncora, responda "nao_produz".
- Não use "talvez" por simples falta de evidência.
- Use "talvez" quando houver menção a hidrogênio/H2, projeto relacionado a H2, ou qualquer menção a empresa âncora, mas sem evidência suficiente para afirmar "produz_h2".

Use como evidência principal somente o conteúdo dos documentos crawleados abaixo, especialmente:
- site institucional da empresa;
- página de produtos;
- catálogo técnico;
- relatório;
- notícia institucional;
- documento oficial;
- página que mencione planta, unidade, fabricação, geração ou produção de hidrogênio pela empresa.

Regras de decisão:

1. Responda "produz_h2" somente se houver evidência textual direta de que a empresa produz, gera, fabrica ou opera unidade/planta de hidrogênio.
   Exemplos fortes:
   - "produz hidrogênio";
   - "produção de hidrogênio";
   - "planta de hidrogênio";
   - "unidade de hidrogênio";
   - "geração de H2";
   - "eletrólise para produção de hidrogênio";
   - "reforma a vapor";
   - "SMR";
   - catálogo próprio oferecendo hidrogênio produzido pela empresa.

2. Responda "nao_produz" se os documentos mostrarem apenas:
   - revenda;
   - distribuição;
   - comercialização;
   - entrega;
   - representação;
   - gases medicinais ou industriais sem menção direta à produção de H2;
   - produção de outros gases, como oxigênio, nitrogênio, CO2, acetileno, argônio, sem prova de hidrogênio.

3. Responda "talvez" quando:
   - houver qualquer menção a uma empresa âncora nos documentos, mesmo sem prova de produção própria de H2;
   - houver menção a hidrogênio/H2 ligada à empresa, mas sem evidência de produção própria;
   - houver menção a projeto, produto, processo, energia, eletrólise ou planta relacionada a H2, mas sem confirmação de produção pela empresa analisada.
   Nesses casos, explique explicitamente que faltam evidências de produção própria de hidrogênio.

4. Ignore CNAE como critério decisivo.
   Se a única evidência for "fabricação de gases industriais", "CNAE 2014-2/00", "atividade econômica", ou página cadastral, responda "talvez" ou "nao_produz", conforme o restante do conteúdo.

5. Não conclua "produz_h2" apenas porque a empresa fabrica gases industriais.
6. Não conclua "produz_h2" apenas porque aparece em sites cadastrais.
7. Não invente evidências.
8. Cite somente frases curtas presentes nos documentos.
9. Se não houver evidência útil, diga isso explicitamente na resposta.

10. Responda "nao_produz" quando:
   - não houver nenhuma menção relevante a hidrogênio/H2;
   - não houver nenhuma menção a empresa âncora;
   - houver apenas CNAE, cadastro empresarial, Econodata, CNPJ.biz, Serasa ou CNPJCheck;
   - houver apenas fabricação/comércio/distribuição de gases industriais sem menção específica a H2;
   - houver apenas notícia genérica sem relação direta com H2 ou empresa âncora.

Responda de forma curta e direta.

Comece sua resposta com uma destas três classificações:
- produz_h2
- nao_produz
- talvez

Depois explique brevemente o motivo, citando evidências textuais quando houver.

DOCUMENTOS:
{contexto}
"""

    try:
        resposta = gemini_input(prompt, model=model)
        resposta = resposta.strip()

        return {
            "output": resposta,
            "horario": run_id()
        }

    except Exception as e:
        print(f"[ERRO GOOGLE] {str(pasta)} | erro={e}")
        return {
            "output": f"incerto - Erro na requisição Google: {e}",
            "horario": run_id()
        }

def normalizar_cnpj(valor):
    if pd.isna(valor):
        return ""
    return "".join(ch for ch in str(valor).split(".")[0] if ch.isdigit()).zfill(14)


def lista_preenchida(valor):
    return isinstance(valor, list) and len(valor) > 0


def tem_erro_rate_limit(valor):
    return "429" in str(valor) or "Too Many Requests" in str(valor)

def tem_incerto(valor):
    return "incerto" in str(valor).lower()


def incerto_sem_evidencia_md(valor):
    texto = str(valor).lower()
    return (
        "incerto" in texto
        and "nenhum trecho com palavras-chave relevantes" in texto
        and "markdowns" in texto
    )


def tem_erro_ia(valor):
    texto = str(valor).lower()
    return (
        "erro na requisição google" in texto
        or "erro na requisicao google" in texto
        or "erro na requisição groq" in texto
        or "erro na requisicao groq" in texto
        or "erro ao interpretar resposta" in texto
        or "500 internal" in texto
        or "internal error" in texto
        or "429" in texto
        or "too many requests" in texto
        or "413" in texto
        or "payload too large" in texto
        or "resource_exhausted" in texto
        or "unavailable" in texto
    )

def extrair_output_ia(valor):
    if isinstance(valor, list) and valor and isinstance(valor[0], dict):
        return str(valor[0].get("output", "")).strip()

    if isinstance(valor, dict):
        return str(valor.get("output", "")).strip()

    return ""

def output_de_interesse(output):
    texto = str(output or "").strip().lower()

    return (
        texto.startswith("produz")
        or texto.startswith("talvez")
        or incerto_sem_evidencia_md(output)
    )

def incerto_nao_previsto(output):
    texto = str(output or "").strip().lower()

    return (
        texto.startswith("incerto")
        and not incerto_sem_evidencia_md(output)
    )

def output_nao_produz(output):
    texto = str(output or "").strip().lower()

    return (
        texto.startswith("nao_produz")
        or texto.startswith("não_produz")
        or texto.startswith("nao produz")
        or texto.startswith("não produz")
    )


def tem_mencao_ancora_no_registro(row):
    campos_para_buscar = {
        "searching_urls": row.get("searching_urls", []),
        "nome_fantasia": row.get("nome_fantasia", ""),
        "razao_social": row.get("razao_social", ""),
        "nome": row.get("nome", "")
    }

    texto = json.dumps(
        campos_para_buscar,
        ensure_ascii=False
    ).lower()

    return any(ancora.lower() in texto for ancora in ancoras)

def registro_completo(row):
    searching_ok = lista_preenchida(row.get("searching_urls"))
    ia = row.get("IA_results")
    ia_ok = lista_preenchida(ia)

    if not searching_ok or not ia_ok:
        return False

    if tem_erro_ia(ia):
        return False

    if tem_incerto(ia) and not incerto_sem_evidencia_md(ia):
        return False

    return True

def extrair_label_output(output):
    texto = str(output or "").strip()

    if not texto:
        return ""

    primeira_linha = texto.splitlines()[0].strip().lower()

    if primeira_linha.startswith("produz_h2"):
        return "produz_h2"

    if primeira_linha.startswith("produz"):
        return "produz"

    if primeira_linha.startswith("talvez"):
        return "talvez"

    if primeira_linha.startswith("incerto"):
        return "incerto"

    if primeira_linha.startswith("nao_produz") or primeira_linha.startswith("não_produz"):
        return "nao_produz"

    if primeira_linha.startswith("nao produz") or primeira_linha.startswith("não produz"):
        return "nao_produz"

    return primeira_linha

#def base_domain(host: str) -> str:
    #host = (host or "").lower().strip(".")
    #parts = host.split(".")
    #if len(parts) <= 2:
        #return host
    #if parts[-1] == "br" and parts[-2] in {"com", "org", "net", "gov", "edu"}:
        #return ".".join(parts[-3:])
    #return ".".join(parts[-2:])

#def is_vertex_redirect(host: str) -> bool:
    #host = (host or "").lower()
    #return host.endswith("vertexaisearch.cloud.google.com")

#def url_snapshot(url: str, timeout=30, max_bytes=1_000_000):
    #headers = {
        #"User-Agent": "Mozilla/5.0 (ResearchBot/1.0)",       # Etiequeta útil para uma requisição não ser barrada 
        #"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    #}       
    #r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    #orig_host = urlparse(url).netloc.lower()
    #final_host = urlparse(str(r.url)).netloc.lower()
    #if not orig_host:
        #orig_host = final_host
    #domain_changed = base_domain(orig_host) != base_domain(final_host)
    #raw = r.content or b""     # Conteúdo cru em bytes da requisição
    #if len(raw) > max_bytes:
        #raw = raw[:max_bytes]
    #h = sha256_bytes(raw)
    
    #try:
        #txt = r.text or ""
    #except Exception:
        #txt = ""
    #text_head = txt[:20000]
    #h_text = sha256_bytes(text_head.encode("utf-8", errors="ignore"))
#
    #allowed_domain_change = is_vertex_redirect(orig_host)
    #if domain_changed and not allowed_domain_change:
        #return {
            #"url": url,
            #"url_final": str(r.url),
            #"domain_changed": True,
            #"host_original": orig_host,
            #"host_final": final_host,
            #"collected_at": run_id(),
            #"timeout_s": timeout,
            #"http_status": int(r.status_code),
            #"content_type": r.headers.get("Content-Type"),
            #"headers": {
                #"date": r.headers.get("Date"),
                #"last_modified": r.headers.get("Last-Modified"),
                #"etag": r.headers.get("ETag"),
                #"cache_control": r.headers.get("Cache-Control"),
            #},
            #"request": {"user_agent": headers["User-Agent"]},
            #"blocked": "redirect_out_of_base_domain",
            #"allowed_domain_change": allowed_domain_change,
        #}
#
    #return {
        #"url": url,
        #"url_final": str(r.url),
        #"domain_changed": domain_changed,
        #"allowed_domain_change": allowed_domain_change,
        #"host_original": orig_host,
        #"host_final": final_host,
        #"collected_at": run_id(),
        #"timeout_s": timeout,
        #"http_status": int(r.status_code),
        #"content_type": r.headers.get("Content-Type"),
        #"hash_raw_head": h,
        #"hash_bytes_used": len(raw),
        #"hash_text_head": h_text,
        #"text_head": text_head,
        #"headers": {
            #"date": r.headers.get("Date"),
            #"last_modified": r.headers.get("Last-Modified"),
            #"etag": r.headers.get("ETag"),
            #"cache_control": r.headers.get("Cache-Control"),
        #},
        #"request": {
            #"user_agent": headers["User-Agent"]
        #}
    #}

#class url_output(BaseModel):
    #url: HttpUrl
    #trecho: str = Field(min_length=1, max_length=800)

#class gemini_output(BaseModel):
    #label: Literal["produz", "nao_produz", "incerto"]
    #confidence: confloat(ge=0, le=1)
    #summary: str = Field(min_length=1, max_length=600)
    #evidence: List[url_output] = Field(default_factory=list, max_length=5)
    #notes: str = Field(default="", max_length=600)

#def veredito(text: str):
    #try:
        #data: Any = json.loads(text)
    #except Exception as e:
        #return {"ok": False, "obj": None, "error": f"JSON inválido: {e}"}
#    
    #try:
        #obj = gemini_output.model_validate(data)
        #return {"ok": True, "obj": obj.model_dump(), "error": ""}
    #except ValidationError as e:
        #msgs = [err.get("msg", "erro") for err in e.errors()]
        #return {"ok": False, "obj": None, "error": " | ".join(msgs)}
#    
#def reparar_output(bad_text: str, errors: str, model = "gemini-2.5-flash") -> str:
#    global CONFIG_JSON_ONLY
#
#    if CONFIG_JSON_ONLY is None:
#        CONFIG_JSON_ONLY = types.GenerateContentConfig(
#            response_mime_type="application/json"
#        )
#    
#prompt = f"""
#Corrija o JSON abaixo para aderir ESTRITAMENTE ao schema.
#Não invente novas evidências. Não adicione chaves extras.
#
#Erros de validação:
#{errors}
#
#Schema:
#{{
#  "label": "produz|nao_produz|incerto",
#  "confidence": number (0 a 1),
#  "summary": string,
#  "evidence": [{{"url": string, "trecho": string}}],
#  "notes": string
#}}
#
#JSON a corrigir:
#{bad_text}
#"""
#    return gemini_input(prompt, model=model, config_override=CONFIG_JSON_ONLY)
