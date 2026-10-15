import json
import os
import re
from bs4 import BeautifulSoup
from epicstore_api import EpicGamesStoreAPI
import requests

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

def limpar_nome_jogo(nome):
  """Remove símbolos de marca registrada e caracteres especiais"""
  nome_limpo = re.sub(r"[™®©]", "", nome)
  nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
  return nome_limpo.strip()

nomes_jogos_epic = []
for bloco in blocos_texto:
  if re.search(r"repetido", bloco, re.IGNORECASE):
    continue
  
  # Remove a numeração inicial do item da lista (ex: "110. Jogo X" vira "Jogo X")
  bloco_sem_numero = re.sub(r"^\d+[\.\-\s]+", "", bloco).strip()

  partes = re.split(r"[-–\(]", bloco_sem_numero, maxsplit=1)
  if partes:
    nome_candidato = limpar_nome_jogo(partes[0])

    data_gratis = "Desconhecida"
    if len(partes) > 1:
       data_gratis = partes[1].replace(")", "").strip()

    # Filtros rigorosos para evitar números isolados ou palavras inúteis
    if (
        len(nome_candidato) > 2
        and not nome_candidato.isdigit()  # Ignora se for apenas um número
        and nome_candidato.lower()
        not in ["dlc", "dev", "jogo", "jogos", "gratis"]
        and nome_candidato not in nomes_jogos_epic
        and not nome_candidato.lower().startswith("http")
    ):
      if not any(j["nome"] == nome_candidato for j in nomes_jogos_epic):
         nomes_jogos_epic.append({"nome": nome_candidato, "data_gratis": data_gratis})

print(
    f"🔍 Identificados {len(nomes_jogos_epic)} jogos limpos para buscar na Epic"
    " Games."
)

# Loop de bisca e download dos metadados na Epic Games Store
for indice, item in enumerate(nomes_jogos_epic, start=1):
    nome = item["nome"]
    data_gratis = item["data_gratis"]

    print(f"\n[{indice}/{len(nomes_jogos_epic)}] Pesquisando na Epic: {nome} (Data: {data_gratis})")

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
            # Tenta encontrar o slug no campo padrão ou em alternativas comuns da Epic
                slug = (
                    jogo_encontrado.get("productSlug")
                    or jogo_encontrado.get("urlSlug")
                    or next(
                        (
                            m.get("pageSlug")
                            for m in jogo_encontrado.get("mappings", [])
                            if m.get("pageSlug")
                        ),
                        None,
                    )
                )

                detalhes = None
                if slug:
                    try:
                        detalhes = api.get_product(slug)
                    except Exception:
                        detalhes = jogo_encontrado  # Se falhar o detalhe profundo, usa o básico
                else:
                    # Se nenhum slug foi encontrado, aproveita os dados básicos do catálogo
                    detalhes = jogo_encontrado
                    #Cria um slug temporário limpo baseado no título do jogo
                    titulo_base = jogo_encontrado.get("title", "jogo_desconhecido")
                    slug = re.sub(r"[^\w\s-]", "", titulo_base).strip().lower()
                    slug = re.sub(r"\s+", "-", slug)
                    print(
                        f"   ⚠️ Slug direto não encontrado, usando catálogo básico para"
                        f" '{titulo_base}'."
                    )

                if isinstance(detalhes, dict):
                   detalhes["data_aquisicao_gratis"] = data_gratis

                slug_limpo = slug.replace("/", "_")
                caminho_saida = f"dados/raw/epic_gratis_{slug_limpo}.json"

                with open(caminho_saida, "w", encoding="utf-8") as f:
                    json.dump(detalhes, f, ensure_ascii=False, indent=4)
                print(f"   💾 Salvo com sucesso: epic_gratis_{slug_limpo}.json")
            else:
                print(f"   ❌ Jogo não encontrado na Epic Games.")

    except Exception as e:
        print(f"Erro critico ao buscar '{nome}': {e}")


            
                
        

