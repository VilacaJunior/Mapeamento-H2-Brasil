# Mapeamento de plantas de hidrogênio (H₂)

Pipeline em Python para localizar e analisar empresas brasileiras potencialmente relacionadas à produção de hidrogênio. O projeto parte dos arquivos de **Estabelecimentos da Receita Federal do Brasil (RFB)**, filtra empresas pelo CNAE de fabricação de gases industriais, realiza pesquisa pública e triagem assistida por IA, complementa os registros com dados ambientais e geográficos e apresenta os resultados em um mapa interativo com Streamlit.

Observações: esse pipeline foi criado para me auxiliar no desenvolvimento da minha pesquisa, e não representa, de forma isolada, toda a metodologia, o conhecimento técnico ou as análises empregados no trabalho e as devidas bibliotecas usadas; o pipeline foi desenvolvido junto ao auxílio de IA assistida, utilizada durante a elaboração, revisão e aperfeiçoamento do código. A pesquisa faz parte do Programa de Iniciação à Pesquisa da Universidade Federal de Goiás (PIP/PIBIC-UFG), denominada: "CENTRO DE ANÁLISE DE DADOS ECONÔMICOS E DE NEGÓCIOS (CADEN/UFG): INTRODUÇÃO A ANÁLISE DE DADOS", a qual o tema de aplicação foi: "MAPEAMENTO DAS PLANTAS DE HIDROGÊNIO E OPORTUNIDADES NO BRASIL". O código da pesquisa é "PI07934-2024"; meu orientador é o professor Dr. Waldemiro Alcântara da Silva Neto, a quem sou extremamente grato pela confiança e apoio em me permitir participar desse projeto. A base utilizada corresponde à competência de janeiro de 2026 e foi processada pela aplicação em 25 de maio de 2026, de modo que alterações cadastrais posteriores não foram contempladas.


## Visão geral do processamento

O comando `python main.py` executa as etapas abaixo na ordem:

1. **Conversão:** converte os arquivos `.ESTABELE` da RFB de Latin-1 para CSV em UTF-8.
2. **Filtro:** seleciona estabelecimentos com CNAE principal `2014200` e situação cadastral `02` ou `03`.
3. **Seleção:** exclui CNPJs que já constam na seleção manual realizada anteriormente.
4. **Identificação:** pesquisa cada empresa, coleta páginas públicas e usa IA para classificar as evidências encontradas.
5. **Complementação:** cruza os resultados com o CTF/APP, geocodifica os CEPs e calcula a distância até polos industriais relacionados ao H₂.
6. **Dashboard:** combina os resultados com a planilha de vereditos e abre um mapa interativo no Streamlit.

## Requisitos

- Python **3.12** recomendado;
- `pip` disponível no terminal;
- conexão com a internet;
- chave da Gemini API;
- chave da Serper API;
- espaço em disco suficiente para extrair e converter a base da RFB (recomendado +35GB livres);
- navegador instalado/configurado para o Crawl4AI.

O projeto pode funcionar em outros sistemas operacionais, mas o fluxo foi estruturado e testado principalmente para execução pelo comando `python`.


## Instalação e configuração

Clone o repositório, crie um ambiente virtual e instale as dependências; exemplo:

```bash
git clone https://github.com/VilacaJunior/Mapeamento-H2-Brasil.git
cd Map_H2_IC
python -m venv .venv
python -m pip install -r requirements.txt
crawl4ai-setup
```

Configure as chaves necessárias como variáveis de ambiente:

```text
GEMINI_API_KEY
SERPER_API_KEY
```

As variáveis devem estar disponíveis no terminal em que `python main.py` for executado. O projeto não carrega arquivos `.env` automaticamente.


## Baixar os dados de Estabelecimentos da RFB

Baixe, na fonte oficial da Receita Federal, os arquivos da base aberta de CNPJ referentes a **Estabelecimentos**, na data mais recente. Baixe os arquivos clicando [aqui](https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9).

Os arquivos normalmente são distribuídos em partes compactadas. É necessário:

1. baixar todas as partes de Estabelecimentos referentes ao mesmo período da base;
2. extrair os arquivos compactados;
3. copiar os arquivos extraídos terminados em `.ESTABELE` para `dados_brutos`.

Estrutura esperada:

```text
Map_H2_IC/
├── dados_brutos/
│   ├── arquivo_0.ESTABELE
│   ├── arquivo_1.ESTABELE
│   ├── arquivo_2.ESTABELE
│   └── ...
├── main.py
└── requirements.txt
```

Não coloque apenas os arquivos `.zip` em `dados_brutos`: a etapa de conversão procura diretamente por arquivos cujo nome termina em `.ESTABELE`. Subpastas são aceitas, pois a busca é recursiva.

Não é necessário baixar as bases de Empresas, Sócios, Municípios ou CNAEs para o fluxo atual. O pipeline usa somente os arquivos de Estabelecimentos.


## Conferir os dados auxiliares

Além dos `.ESTABELE`, o repositório deve conter estes insumos:

```text
dados_selecionados/dados_selecionados_prev.csv
dados_complementares/CTF_APP_filtrado.csv
dados_complementares/CTF_APP/*.csv
dados_analisados/dados_analisados_25_05_26_v1.xlsx
dados_analisados/auditoria/* ("cache_geocodificacao.json", "dados_triados.json", "empresas_identificadas_complementadas.csv")
```

## Executar o pipeline completo

Com o ambiente virtual ativo, as chaves definidas e os `.ESTABELE` extraídos em `dados_brutos`, execute:

```bash
python main.py
```

O processo cria ou utiliza as seguintes saídas:

```text
dados_convertidos/       CSVs da RFB convertidos para UTF-8
dados_filtrados/         empresas_filtradas.csv
dados_selecionados/      dados_liquidos.json
dados_coletados/         páginas coletadas e progresso da pesquisa
dados_identificados/     classificações da IA em CSV e JSON
dados_complementares/    dados complementados e cache geográfico
dados_analisados/        dados finais preparados para o dashboard
```

Ao final, o próprio `main.py` inicia o Streamlit. O terminal exibirá um endereço local, normalmente:

```text
http://localhost:8501
```

Abra esse endereço no navegador caso ele não seja aberto automaticamente. Para encerrar o dashboard, pressione `Ctrl+C` no terminal.


## Executar somente o dashboard

Se os arquivos processados já existirem e a intenção for apenas abrir o mapa:

```bash
python -m streamlit run sub_processos/6_dashboard.py
```

O dashboard também consulta projetos de hidrogênio da EPE. Se essa consulta externa falhar, ele tenta continuar mostrando somente os dados locais.


## O que esperar durante a identificação

A etapa 4 é deliberadamente demorada. Para cada CNPJ, ela pode:

- realizar várias buscas no Serper;
- visitar diferentes páginas com o Crawl4AI;
- salvar páginas em Markdown;
- aguardar 20 segundos antes da chamada de IA;
- consumir cota das APIs.

Não feche o terminal sem necessidade. O progresso é salvo em `dados_coletados/dados_triados.json`, permitindo que uma nova execução reutilize parte do trabalho já concluído.

Algumas páginas podem bloquear automação ou não possuir conteúdo útil. Por isso, a ausência de evidência coletada não deve ser interpretada automaticamente como prova de que uma empresa não produz hidrogênio.


## Retomar ou refazer uma execução

O `main.py` decide pular etapas verificando os arquivos que já existem nas pastas de saída. Assim:

- se `dados_convertidos` contiver arquivos, a conversão será pulada;
- se `dados_filtrados` contiver arquivos, o filtro será pulado;
- se `dados_liquidos.json` estiver presente junto da seleção anterior, a seleção será pulada;
- se os resultados identificados estiverem presentes, a pesquisa pode ser pulada;
- se `empresas_identificadas_complementadas.csv` existir, a complementação será pulada.

Para reprocessar desde uma etapa, faça primeiro uma cópia de segurança e remova manualmente apenas as saídas dessa etapa e das etapas posteriores. Não remova os seguintes insumos sem possuir outra cópia:

```text
dados_brutos/*.ESTABELE
dados_selecionados/dados_selecionados_prev.csv
dados_complementares/CTF_APP/
dados_complementares/CTF_APP_filtrado.csv
dados_analisados/dados_analisados_25_05_26_v1.xlsx
```

Evite deixar arquivos avulsos nas pastas de saída: em alguns pontos, o orquestrador considera apenas a quantidade ou a presença de arquivos para decidir se uma etapa já terminou.


## Arquivos principais

```text
main.py                         orquestra todas as etapas
essential.py                    funções compartilhadas e integrações externas
requirements.txt                dependências Python
sub_processos/1_converter.py    conversão dos arquivos da RFB
sub_processos/2_filtrar.py      filtro do CNAE e situação cadastral
sub_processos/3_selecionar.py   exclusão da seleção anterior
sub_processos/4_identificar.py  buscas, crawling e análise por IA
sub_processos/5_complementar.py CTF/APP, geocodificação e distâncias
sub_processos/6_dashboard.py    preparação e visualização do mapa
```

## Serviços externos utilizados

- Receita Federal do Brasil: base aberta de CNPJ;
- Serper: pesquisa na web;
- Google Gemini API: triagem das evidências;
- Crawl4AI: coleta do conteúdo das páginas;
- BrasilAPI e ViaCEP: consulta de CEP;
- Nominatim/OpenStreetMap: geocodificação;
- EPE: projetos adicionais exibidos no dashboard.

O funcionamento dessas integrações depende de disponibilidade, limites, termos de uso e eventuais alterações realizadas pelos respectivos provedores.

## Observação metodológica

As classificações automáticas representam uma triagem técnica baseada em evidências públicas encontradas na web. Elas não constituem prova jurídica ou confirmação definitiva de produção de hidrogênio. Os resultados devem ser revisados antes de uso acadêmico, institucional ou decisório.

## Licença

O código-fonte deste projeto é disponibilizado sob a Licença MIT. Os dados provenientes de terceiros permanecem sujeitos aos respectivos termos, licenças e condições de uso de suas fontes originais.
