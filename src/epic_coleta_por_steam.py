import json
import os
import re
import difflib
from epicstore_api import EpicGamesStoreAPI
from Ratings_Polls_Epic import obter_ratings_polls

# Inicializa a API da Epic Games
api = EpicGamesStoreAPI(country="BR", locale="pt-BR")
os.makedirs("dados/raw", exist_ok=True)

def normalizar_texto(texto):
  """Limpa símbolos, pontuações e espaços extras para comparação estrita"""
  if not texto:
    return ""
  texto = re.sub(r"[™®©:]", "", texto)
  texto = re.sub(r"[^\w\s-]", " ", texto)
  texto = re.sub(r"[\s\-_]+", " ", texto).strip().lower()
  return texto

def calcular_similaridade(str1, str2):
  """Retorna o ratio de similaridade de SequenceMatcher entre as duas strings"""
  n1, n2 = normalizar_texto(str1), normalizar_texto(str2)
  return difflib.SequenceMatcher(None, n1, n2).ratio()

def extrair_queries_busca(nome_original):
  """Gera termos de busca alternativos para evitar falsos negativos."""
  queries = []

  nome_limpo = re.sub(r"[™®©]", "", nome_original).strip()
  queries.append(nome_limpo)

  corte_subtitulo = re.split(r"[:\-–—]", nome_limpo)[0].strip()
  if len(corte_subtitulo) >= 3 and corte_subtitulo not in queries:
    queries.append(corte_subtitulo)

  sem_pontos = re.sub(r"\b([a-zA-Z])\.", r"\1", nome_limpo)
  if sem_pontos not in queries:
    queries.append(sem_pontos)

  return queries

def selecionar_melhor_correspondencia(elements, nome_buscado):
  """Seleciona o produto ideal eliminando DLCs e falsos positivos por similaridade"""
  nome_norm = normalizar_texto(nome_buscado)
  palavras_busca = nome_norm.split()
  nums_orig = re.findall(r"\d+", nome_norm)

  melhor_candidato = None
  maior_score = 0.0

  for produto in elements:
    offer_type = str(produto.get("offerType", "")).upper()

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

  # Limiar minimo de aceitação (80% de similaridade)
  if maior_score >= 0.80:
    return melhor_candidato, maior_score

  return None, 0.0

# Ler os nomes dos jogos a partir dos arquivos JSON salvos da steam
pasta_steam = "dados/raw"
jogos_para_buscar = []

# Leitura corrigida aceitando steam_ e steam_gratis_
for arquivo in os.listdir(pasta_steam):
    if arquivo.startswith("steam_") and arquivo.endswith(".json") and not arquivo.startswith(("epic_", "gog_")):
        caminho = os.path.join(pasta_steam, arquivo)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = json.load(f)
                match_id = re.search(r"\d+", arquivo)
                if not match_id:
                    continue
                app_id = match_id.group(0)
                if conteudo.get(app_id, {}).get("success"):
                    nome_jogo = conteudo[app_id]["data"].get("name")
                    if nome_jogo and nome_jogo not in jogos_para_buscar:
                        jogos_para_buscar.append(nome_jogo)
        except Exception:
            continue

for indice, nome in enumerate(jogos_para_buscar, start=1):
    print(f"\n[{indice}] Pesquisando: {nome}")
    queries = extrair_queries_busca(nome)
    
    jogo_encontrado = None
    score_obtido = 0.0
    
    for query in queries:
        try:
            resultados = api.fetch_store_games(keywords=query)
            elements = resultados.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
            
            if elements:
                # Varre até 15 resultados da Epic
                jogo_encontrado, score_obtido = selecionar_melhor_correspondencia(elements[:15], nome)
                if jogo_encontrado:
                    print(f"   ↳ Encontrado via query '{query}' (Similaridade: {score_obtido:.2f})")
                    break
        except Exception as e_busca:
            print(f"   ⚠️ Erro ao consultar query '{query}': {e_busca}")

    if jogo_encontrado:
        # Extração de slug com fallbacks
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
            titulo_base = jogo_encontrado.get("title", "jogo")
            slug = normalizar_texto(titulo_base).replace(" ", "-")

        try:
            detalhes = api.get_product(slug)
        except Exception:
            detalhes = dict(jogo_encontrado)

        if not isinstance(detalhes, dict):
            detalhes = dict(jogo_encontrado)

        # Preserva os dados essenciais do catálogo
        if "price" not in detalhes and "price" in jogo_encontrado:
            detalhes["price"] = jogo_encontrado["price"]
        if "offerType" not in detalhes and "offerType" in jogo_encontrado:
            detalhes["offerType"] = jogo_encontrado["offerType"]
        if "title" not in detalhes and "title" in jogo_encontrado:
            detalhes["title"] = jogo_encontrado["title"]

        detalhes["_store_country_requested"] = "BR"
        detalhes["_store_locale_requested"] = "pt-BR"

        ratings = obter_ratings_polls(jogo_encontrado, detalhes, slug_principal=slug)
        detalhes["rating_polls"] = ratings

        slug_limpo = slug.replace("/", "_")
        caminho_saida = f"dados/raw/epic_{slug_limpo}.json"

        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(detalhes, f, ensure_ascii=False, indent=4)
        print(f"💾 Salvo com sucesso: epic_{slug_limpo}.json")
    else:
        print(f"❌ Nenhum jogo correspondente encontrado na Epic para '{nome}'.")