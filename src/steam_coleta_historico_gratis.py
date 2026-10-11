import json
import os
import re
import time
from bs4 import BeautifulSoup
import requests

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

# Extrai os nomes limpos dos jogos, ignorando numerações da lista
nomes_jogos = []
for bloco in blocos_texto:
  # Remove numeração no início da linha (ex: "110. Jogo X" -> "Jogo X")
  bloco_sem_numero = re.sub(r"^\d+[\.\-\s]+", "", bloco).strip()

  match = re.split(r"[-–\(]", bloco_sem_numero)
  if match:
    nome_candidato = limpar_nome_jogo(match[0])

    if (
        len(nome_candidato) > 2
        and not nome_candidato.isdigit()
        and nome_candidato.lower()
        not in ["dlc", "dev", "jogo", "jogos", "gratis"]
        and nome_candidato not in nomes_jogos
        and not nome_candidato.lower().startswith("http")
    ):
      nomes_jogos.append(nome_candidato)

print(f"🔍 Identificados {len(nomes_jogos)} jogos limpos para buscar na Steam.")

def buscar_appid_steam(nome):
  search_url = "https://store.steampowered.com/api/storesearch/"
  params = {"term": nome, "l": "english", "cc": "US"}

  try:
    response = requests.get(search_url, params=params, headers=headers)
    if response.status_code == 200:
      data = response.json()
      items = data.get("items", [])

      if items:
        palavras_orig = set(nome.lower().split())
        nums_orig = re.findall(r"\d+", nome)

        for item in items[:5]:
          titulo_item = item.get("name", "").lower()
          palavras_item = set(titulo_item.split())
          nums_item = re.findall(r"\d+", titulo_item)

          if nums_orig != nums_item:
            continue

          intersecao = palavras_orig.intersection(palavras_item)
          if len(intersecao) >= max(1, len(palavras_orig) - 1):
            return item["id"], item["name"]

  except Exception as e:
    print(f"Erro durante a busca do AppID: {e}")
  return None, None

for indice, nome in enumerate(nomes_jogos, start=1):
  print(f"\n[{indice}/{len(nomes_jogos)}] Pesquisando na Steam: {nome}")

  app_id, nome_encontrado = buscar_appid_steam(nome)
  if app_id:
    details_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english"

    try:
      resp_detalhes = requests.get(details_url, headers=headers)
      if resp_detalhes.status_code == 200:
        detalhes_json = resp_detalhes.json()

        caminho_saida = f"dados/raw/steam_gratis_{app_id}.json"
        with open(caminho_saida, "w", encoding="utf-8") as f:
          json.dump(detalhes_json, f, ensure_ascii=False, indent=4)
        print(f"   💾 Salvo com sucesso: steam_gratis_{app_id}.json ("
            f"{nome_encontrado})")
      else:
        print(f"Falha ao obter detalhes do AppID {app_id}.")
    except Exception as e:
      print(f"Erro ao baixar detalhes do AppId {app_id}: {e}")
    
  else:
    print(f"Jogo não encontrado na Steam.")

  time.sleep(0.5)
      
      
    