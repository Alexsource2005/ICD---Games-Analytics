import json
import os
import re
from bs4 import BeautifulSoup
from epicstore_api import EpicGamesStoreAPI
import requests

api = EpicGamesStoreAPI()

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

def limpar_nome_jogo(nome):
  """Remove símbolos de marca registrada e caracteres especiais"""
  nome_limpo = re.sub(r"[™®©]", "", nome)
  nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
  return nome_limpo.strip()

nomes_jogos_epic = []
for bloco in blocos_texto:
  # Remove a numeração inicial do item da lista (ex: "110. Jogo X" vira "Jogo X")
  bloco_sem_numero = re.sub(r"^\d+[\.\-\s]+", "", bloco).strip()

  match = re.split(r"[-–\(]", bloco_sem_numero)
  if match:
    nome_candidato = limpar_nome_jogo(match[0])

    # Filtros rigorosos para evitar números isolados ou palavras inúteis
    if (
        len(nome_candidato) > 2
        and not nome_candidato.isdigit()  # Ignora se for apenas um número
        and nome_candidato.lower()
        not in ["dlc", "dev", "jogo", "jogos", "gratis"]
        and nome_candidato not in nomes_jogos_epic
        and not nome_candidato.lower().startswith("http")
    ):
      nomes_jogos_epic.append(nome_candidato)

print(
    f"🔍 Identificados {len(nomes_jogos_epic)} jogos limpos para buscar na Epic"
    " Games."
)

# Loop de bisca e download dos metadados na Epic Games Store
for indice, nome in enumerate(nomes_jogos_epic, start=1):
    print(f"[{indice}/{len(nomes_jogos_epic)}] Pesquisando na Epic: {nome}")

    try:
        resultados = api.fetch_store_games(keywords=nome)
        elements = (
            resultados.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        )

        if not elements and ("-" in nome or ":" in nome):
            nome_curto = re.split(r"[:/-]", nome)[0].strip()
            if len(nome_curto) > 3:
                resultados = api.fetch_store_games(keywords=nome_curto)
                elements = (
                    resultados.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
                )

        jogo_encontrado = None
        if elements:
            palavras_originais = set(nome.lower().split())
            nums_orig = re.findall(r"\d+", nome)

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
                slug = jogo_encontrado.get("productSlug")

                if slug:
                    try:
                        detalhes = api.get_product(slug)
                    except Exception:
                        detalhes = jogo_encontrado

                    slug_limpo = slug.replace("/", "_")
                    caminho_saida = f"dados/raw/epic_gratis_{slug_limpo}.json"

                    with open(caminho_saida, "w", encoding="utf-8") as f:
                        json.dump(detalhes, f, ensure_ascii=False, indent=4)
                    print(f"Salvo com sucesso: epic_gratis_{slug_limpo}.json")
                else:
                    print(f"Slug não encontrado para '{nome}'.")
            else:
                print(f"Jogo não encontrado na Epic Games")

    except Exception as e:
        print(f"Erro critico ao buscar '{nome}': {e}")


            
                
        

