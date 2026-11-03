import difflib
import json
import os
import re
from bs4 import BeautifulSoup
from epicstore_api import EpicGamesStoreAPI
import requests
from Ratings_Polls_Epic import obter_ratings_polls

api = EpicGamesStoreAPI(country="BR", locale="pt-BR")

os.makedirs("dados/raw", exist_ok=True)

url = "https://www.nerdmaldito.com/2020/05/lista-com-todos-os-jogos-dados-pela.html"
headers = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; x64) AppleWebKit/537.36")
}

resposta = requests.get(url, headers=headers)
blocos_texto = []

if resposta.status_code == 200:
    soup = BeautifulSoup(resposta.text, "html.parser")
    post_body = soup.find("div", class_="post-body") or soup.find(
        "div", class_="entry-content"
    )

    if post_body:
        for elemento in post_body.find_all(["p", "li"]):
            texto = elemento.get_text().strip()
            if len(texto) > 3 and ("-" in texto or "–" in texto or "(" in texto):
                blocos_texto.append(texto)
    print(f"✅ Extraídos {len(blocos_texto)} blocos de texto da página.")
else:
    print(f"❌ Erro ao aceder ao site. Status code: {resposta.status_code}")

MESES = {
    "janeiro": 1, "jan": 1, "january": 1,
    "fevereiro": 2, "fev": 2, "february": 2, "feb": 2,
    "março": 3, "marco": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4,
    "maio": 5, "mai": 5, "may": 5,
    "junho": 6, "jun": 6, "june": 6,
    "julho": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "setembro": 9, "set": 9, "september": 9, "sep": 9,
    "outubro": 10, "out": 10, "october": 10, "oct": 10,
    "novembro": 11, "nov": 11, "november": 11,
    "dezembro": 12, "dez": 12, "december": 12, "dec": 12,
}

def padronizar_data_aquisicao(texto_data, ano_contexto="2020"):
    """Converte diferentes formatos de data para 'dd/mm/aaaa - dd/mm/aaaa'."""
    if not texto_data or not isinstance(texto_data, str):
        return None

    texto = texto_data.strip()
    if not texto or texto.lower() in ["desconhecida", "n/a", "none", "null"]:
        return None

    # Se já estiver exatamente no formato dd/mm/aaaa - dd/mm/aaaa
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}", texto):
        return re.sub(r"\s*-\s*", " - ", texto)

    texto_lower = texto.lower()

    # Busca anos explícitos na string
    anos_encontrados = re.findall(r"\b(20\d{2})\b", texto_lower)
    ano_base = anos_encontrados[0] if anos_encontrados else ano_contexto

    # 1. Duas datas completas dd/mm/aaaa
    datas_completas = re.findall(r"\b(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})\b", texto_lower)
    if len(datas_completas) == 2:
        d1, m1, y1 = datas_completas[0]
        d2, m2, y2 = datas_completas[1]
        y1 = f"20{y1}" if len(y1) == 2 else y1
        y2 = f"20{y2}" if len(y2) == 2 else y2
        return f"{int(d1):02d}/{int(m1):02d}/{y1} - {int(d2):02d}/{int(m2):02d}/{y2}"

    # 2. Intervalo numérico ("12 a 19/12/2019" ou "12/12 a 19/12/2019")
    m_range_num = re.search(r"\b(\d{1,2})(?:[\/\.-](\d{1,2}))?\s*(?:a|-|–|à|até)\s*(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})\b", texto_lower)
    if m_range_num:
        dia_ini, mes_ini, dia_fim, mes_fim, ano = m_range_num.groups()
        ano = f"20{ano}" if len(ano) == 2 else ano
        mes_ini = mes_ini if mes_ini else mes_fim

        # Correção da virada de ano (Dezembro para janeiro)
        ano_fim = str(int(ano) + 1) if mes_ini == 12 and mes_fim == 1 else ano
        return f"{int(dia_ini):02d}/{int(mes_ini):02d}/{ano} - {int(dia_fim):02d}/{int(mes_fim):02d}/{ano_fim}"

    # 3. Intervalo por extenso ("31 de dezembro de 2020 a 7 de janeiro de 2021")
    m_extenso_duplo = re.search(r"(\d{1,2})\s*(?:de\s*)?([a-zç]+)(?:\s*de\s*(20\d{2}))?\s*(?:a|-|–|à|até)\s*(\d{1,2})\s*(?:de\s*)?([a-zç]+)(?:\s*de\s*(20\d{2}))?", texto_lower)
    if m_extenso_duplo and m_extenso_duplo.group(2) in MESES and m_extenso_duplo.group(5) in MESES:
        d1 = int(m_extenso_duplo.group(1))
        m1 = MESES[m_extenso_duplo.group(2)]
        ano1 = m_extenso_duplo.group(3)

        d2 = int(m_extenso_duplo.group(4))
        m2 = MESES[m_extenso_duplo.group(5)]
        ano2 = m_extenso_duplo.group(6)

        ano2 = ano2 or ano1
        ano1 = ano1 or ano2
        if ano1 and ano2:
            return f"{d1:02d}/{m1:02d}/{ano1} - {d2:02d}/{m2:02d}/{ano2}"
   
    # "2 a 16 de maio de 2019" ou "2 - 16 de maio de 2019"   
    m_extenso_simples = re.search(r"(\d{1,2})\s*(?:a|-|–|à|até)\s*(\d{1,2})\s*de\s*([a-zç]+)(?:\s*de\s*(20\d{2}))?", texto_lower)
    if m_extenso_simples and m_extenso_simples.group(3) in MESES:
        d1 = int(m_extenso_simples.group(1))
        d2 = int(m_extenso_simples.group(2))
        m_num = MESES[m_extenso_simples.group(3)]
        ano_match = m_extenso_simples.group(4) or re.search(r"\b(20\d{2})\b", texto_lower)
        ano = ano_match.group(1) if isinstance(ano_match, re.Match) else ano_match
        if ano:
            return f"{d1:02d}/{m_num:02d}/{ano} - {d2:02d}/{m_num:02d}/{ano}"

    # "Maio 2-16, 2019" ou "Maio 2 - Maio 16, 2019"
    m_mes_primeiro = re.search(r"([a-zç]+)\s*(\d{1,2})\s*[-–aà]\s*(?:([a-zç]+)\s*)?(\d{1,2})[,\s]+(20\d{2})", texto_lower)
    if m_mes_primeiro and m_mes_primeiro.group(1) in MESES:
        m1 = MESES[m_mes_primeiro.group(1)]
        d1 = int(m_mes_primeiro.group(2))
        m2_str = m_mes_primeiro.group(3)
        m2 = MESES[m2_str] if m2_str and m2_str in MESES else m1
        d2 = int(m_mes_primeiro.group(4))
        ano = m_mes_primeiro.group(5)
        return f"{d1:02d}/{m1:02d}/{ano} - {d2:02d}/{m2:02d}/{ano}"

    # 4. Apenas 1 data
    if len(datas_completas) == 1:
        d, m, y = datas_completas[0]
        y = f"20{y}" if len(y) == 2 else y
        return f"{int(d):02d}/{int(m):02d}/{y} - {int(d):02d}/{int(m):02d}/{y}"

    return None

def limpar_nome_jogo(nome):
    """Remove símbolos de marca registrada e caracteres especiais"""
    nome_limpo = re.sub(r"[™®©]", "", nome)
    nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
    return nome_limpo.strip()

# --- HELPER FUNCTIONS DE FUZZY MATCHING E NORMALIZAÇÃO ---

def normalizar_texto(texto):
    """Limpa símbolos, pontuações e espaços extras para comparação estrita."""
    if not texto:
        return ""
    texto = re.sub(r"[™®©:]", "", texto)
    texto = re.sub(r"[^\w\s-]", " ", texto)
    texto = re.sub(r"[\s\-_]+", " ", texto).strip().lower()
    return texto

def calcular_similaridade(str1, str2):
    """Retorna a taxa de similaridade de SequenceMatcher entre duas strings."""
    n1, n2 = normalizar_texto(str1), normalizar_texto(str2)
    return difflib.SequenceMatcher(None, n1, n2).ratio()

def extrair_queries_busca(nome_original):
    """Gera termos de busca alternativos para evitar Falsos Negativos."""
    queries = []
    
    # 1. Nome limpo completo
    nome_limpo = re.sub(r"[™®©]", "", nome_original).strip()
    queries.append(nome_limpo)
    
    # 2. Remoção de subtítulo após :, - ou – (ex: "Scott Pilgrim...: The Game" -> "Scott Pilgrim...")
    corte_subtitulo = re.split(r"[:\-–—]", nome_limpo)[0].strip()
    if len(corte_subtitulo) >= 3 and corte_subtitulo not in queries:
        queries.append(corte_subtitulo)
        
    # 3. Remoção de pontos em acrônimos (ex: "F.E.A.R. 3" -> "FEAR 3")
    sem_pontos = re.sub(r"\b([a-zA-Z])\.", r"\1", nome_limpo)
    if sem_pontos not in queries:
        queries.append(sem_pontos)
        
    return queries

def selecionar_melhor_correspondencia(elements, nome_buscado):
    """Seleciona o produto ideal eliminando DLCs e falsos positivos por similaridade."""
    nome_norm = normalizar_texto(nome_buscado)
    palavras_busca = nome_norm.split()
    nums_orig = re.findall(r"\d+", nome_norm)
    
    melhor_candidato = None
    maior_score = 0.0

    for produto in elements:
        offer_type = str(produto.get("offerType", "")).upper()
        
        # Descarte direto de pacotes e adicionais indesejados
        if offer_type in ["DLC", "ADD_ON", "DIGITAL_EXTRA"]:
            continue
            
        titulo_prod = produto.get("title", "")
        titulo_prod_norm = normalizar_texto(titulo_prod)
        nums_prod = re.findall(r"\d+", titulo_prod_norm)
        
        # Garante que números na busca correspondam exatamente (evita F.E.A.R. 3 -> True Fear 1)
        if nums_orig != nums_prod:
            continue
            
        score = calcular_similaridade(nome_buscado, titulo_prod)
        
        # Regra para títulos de 1 palavra (ex: "Deponia", "The Forest")
        if len(palavras_busca) == 1:
            if titulo_prod_norm == nome_norm:
                return produto, 1.0
            continue
            
        # Prioriza BASE_GAME adicionando um bônus de peso
        if offer_type == "BASE_GAME":
            score += 0.05

        if score > maior_score:
            maior_score = score
            melhor_candidato = produto

    # Limiar mínimo de aceitação (80% de similaridade)
    if maior_score >= 0.80:
        return melhor_candidato, maior_score
        
    return None, 0.0

# --- LEITURA E PARSING DA PÁGINA WEB ---

nomes_jogos_epic = []
for bloco in blocos_texto:
    if re.search(r"repetido", bloco, re.IGNORECASE):
        continue
  
    tem_gmg = bool(re.search(r"\bgmg\b", bloco, re.IGNORECASE))
    bloco_sem_numero = re.sub(r"^\d+[\.\-\s]+", "", bloco).strip()

    partes = re.split(r"[-–\(]", bloco_sem_numero, maxsplit=1)
    if partes:
        nome_candidato = limpar_nome_jogo(partes[0])

        if tem_gmg:
            data_gratis = None
        else:
            raw_data = partes[1].replace(")", "").strip() if len(partes) > 1 else ""
            data_gratis = padronizar_data_aquisicao(raw_data)

        if (
            len(nome_candidato) > 2
            and not nome_candidato.isdigit()
            and nome_candidato.lower() not in ["dlc", "dev", "jogo", "jogos", "gratis"]
            and not nome_candidato.lower().startswith("http")
        ):
            if not any(j["nome"] == nome_candidato for j in nomes_jogos_epic):
                nomes_jogos_epic.append({"nome": nome_candidato, "data_gratis": data_gratis})

print(f"🔍 Identificados {len(nomes_jogos_epic)} jogos limpos para buscar na Epic Games.")

# --- LOOP DE BUSCA E DOWNLOAD DE METADADOS ---

for indice, item in enumerate(nomes_jogos_epic, start=1):
    nome = item["nome"]
    data_gratis = item["data_gratis"]

    print(f"\n[{indice}/{len(nomes_jogos_epic)}] Pesquisando na Epic: {nome} (Data: {data_gratis})")

    queries = extrair_queries_busca(nome)
    jogo_encontrado = None
    score_obtido = 0.0

    try:
        # Tenta as queries em ordem de prioridade
        for query in queries:
            try:
                resultados = api.fetch_store_games(keywords=query)
                elements = (
                    resultados.get("data", {})
                    .get("Catalog", {})
                    .get("searchStore", {})
                    .get("elements", [])
                )

                if elements:
                    # Varre até 15 resultados com o filtro de similaridade e offerType
                    jogo_encontrado, score_obtido = selecionar_melhor_correspondencia(elements[:15], nome)
                    if jogo_encontrado:
                        print(f"   ↳ Encontrado via query '{query}' (Similaridade: {score_obtido:.2f})")
                        break
            except Exception as e_busca:
                print(f"   ⚠️ Erro ao consultar query '{query}': {e_busca}")

        if jogo_encontrado:
            # Extração de Slug com Fallbacks
            catalog_ns = jogo_encontrado.get("catalogNs") or {}
            mappings = (catalog_ns.get("mappings") or jogo_encontrado.get("mappings") or [])

            slug = next((m.get("pageSlug") for m in mappings if isinstance(m, dict) and m.get("pageSlug")), None)

            if not slug:
                for campo in ("productSlug", "urlSlug"):
                    candidato = jogo_encontrado.get(campo)
                    if isinstance(candidato, str) and candidato.strip():
                        candidato = candidato.strip().removesuffix("/home")
                        if not re.fullmatch(r"[0-9a-fA-F]{32}", candidato):
                            slug = candidato
                            break

            if not slug:
                titulo_base = jogo_encontrado.get("title", "jogo_desconhecido")
                slug = normalizar_texto(titulo_base).replace(" ", "-")

            detalhes = None
            try:
                detalhes = api.get_product(slug)
            except Exception as e_detalhes:
                print(f"   ⚠️ get_product('{slug}') falhou ({e_detalhes}). Usando catálogo básico.")
                detalhes = dict(jogo_encontrado)

            if not isinstance(detalhes, dict):
                detalhes = dict(jogo_encontrado)

            # Preserva preço e metadados vitais obtidos do catálogo
            if "price" not in detalhes and "price" in jogo_encontrado:
                detalhes["price"] = jogo_encontrado["price"]
            if "offerType" not in detalhes and "offerType" in jogo_encontrado:
                detalhes["offerType"] = jogo_encontrado["offerType"]
            if "title" not in detalhes and "title" in jogo_encontrado:
                detalhes["title"] = jogo_encontrado["title"]

            detalhes["_store_country_requested"] = "BR"
            detalhes["_store_locale_requested"] = "pt-BR"
            detalhes["data_aquisicao_gratis"] = data_gratis

            ratings = obter_ratings_polls(
                jogo_encontrado=jogo_encontrado,
                detalhes=detalhes,
                slug_principal=slug,
                user_agent=headers.get("User-Agent")
            )
            detalhes["rating_polls"] = ratings

            if ratings.get("average_rating") is not None:
                print(f"⭐ Nota média Epic: {ratings['average_rating']}/5")
            else:
                print(f"⚠️ Nota média não disponível: {ratings.get('status', 'N/A')}")

            slug_limpo = slug.replace("/", "_")
            caminho_saida = f"dados/raw/epic_gratis_{slug_limpo}.json"

            with open(caminho_saida, "w", encoding="utf-8") as f:
                json.dump(detalhes, f, ensure_ascii=False, indent=4)
            print(f"   💾 Salvo com sucesso: epic_gratis_{slug_limpo}.json")
        else:
            print(f"   ❌ Jogo não encontrado na Epic Games.")

    except Exception as e:
        print(f"❌ Erro crítico ao buscar '{nome}': {e}")