import json
import os
import re
from epicstore_api import EpicGamesStoreAPI
from Ratings_Polls_Epic import obter_ratings_polls

# Inicializa a API da Epic Games
api = EpicGamesStoreAPI(country="BR", locale="pt-BR")

os.makedirs("dados/raw", exist_ok=True)


def limpar_nome_jogo(nome):
  """Remove símbolos de marca registrada e caracteres especiais para facilitar a busca"""
  # Remove ™, ®, ©
  nome_limpo = re.sub(r"[™®©]", "", nome)
  nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
  return nome_limpo.strip()


# Ler os nomes dos jogos a partir dos arquivos JSON salvos da steam
pasta_steam = "dados/raw"
jogos_para_buscar = []

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

print(
    f"Encontrados {len(jogos_para_buscar)} nomes de jogos da Steam para buscar na"
    " Epic."
)

# Buscas e coleta dos dados correspondentes na Epic Games
for indice, nome in enumerate(jogos_para_buscar, start=1):
  nome_busca = limpar_nome_jogo(nome)

  print(f"\n[{indice}] Pesquisando: {nome}")
  if nome_busca != nome:
    print(f"   ↳ Nome limpo: {nome_busca}")

  try:
    # Tentativa 1: Busca com o nome limpo principal
    resultados = api.fetch_store_games(keywords=nome_busca)
    elements = (
        resultados.get("data", {})
        .get("Catalog", {})
        .get("searchStore", {})
        .get("elements", [])
    )

    # Tentativa 2 (Fallback):
    if not elements and ("-" in nome_busca or ":" in nome_busca):
      nome_curto = re.split(r"[:\-]", nome_busca)[0].strip()
      if len(nome_curto) > 3:
        print(f"   ↳ Fallback: tentando buscar por '{nome_curto}'...")
        resultados = api.fetch_store_games(keywords=nome_curto)
        elements = (
            resultados.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )

    jogo_encontrado = None
    if elements:
      palavras_originais = set(nome_busca.lower().split())
      nums_orig = re.findall(r"\d+", nome_busca)

      for produto in elements[:5]:
        titulo_prod = produto.get("title", "").lower()
        palavras_prod = set(titulo_prod.split())
        nums_prod = re.findall(r"\d+", titulo_prod)

        if nums_orig != nums_prod:
          continue

        intersecao = palavras_originais.intersection(palavras_prod)
        if len(intersecao) >= max(1, len(palavras_originais) - 1):
          jogo_encontrado = produto
          break

      if jogo_encontrado:
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
          slug = re.sub(r"[^\w\s-]", "", titulo_base).strip().lower()
          slug = re.sub(r"\s+", "-", slug)
        
        detalhes = None

        try:
          detalhes = api.get_product(slug)
        except Exception as e_detalhes:
          print(f"⚠️ get_product('{slug}') falhou ({e_detalhes}). Usando dados do catálogo básico.")
          detalhes = dict(jogo_encontrado)

        if not isinstance(detalhes, dict):
          detalhes = dict(jogo_encontrado)
        
        # A loja é consultada com country=BR e locale=pt-BR.
        # Guardamos a região solicitada para auditoria no ETL.
        
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

          if ratings["average_rating"] is not None:
            print(f"⭐ Nota média Epic: {ratings['average_rating']}/5")
          else:
            print(f"⚠️ Nota média não disponível: {ratings['status']}")

        slug_limpo = slug.replace("/", "_")
        caminho_saida = f"dados/raw/epic_{slug_limpo}.json"

        with open(caminho_saida, "w", encoding="utf-8") as f:
          json.dump(detalhes, f, ensure_ascii=False, indent=4)
        print(f"💾 Salvo com sucesso: epic_{slug_limpo}.json")
      else:
        print(f"❌ Nenhum jogo correspondente encontrado na Epic para '{nome}'.")
  except Exception as e:
    print(f"❌ Erro crítico ao buscar '{nome}': {e}")