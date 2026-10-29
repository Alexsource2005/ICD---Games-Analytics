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

def buscar_tags_steamspy(app_id, max_tentativas=3):
  """Busca as tags da comunidade no SteamSpy."""
  url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"

  for tentativa in range(1, max_tentativas + 1):
    try:
      resp = requests.get(url, headers=headers, timeout=10)
      if resp.status_code == 200:
        dados = resp.json()
        tags_dict = dados.get("tags", {})
        if isinstance(tags_dict, dict):
          return list(tags_dict.keys())
    except Exception:
      if tentativa < max_tentativas:
        time.sleep(2)

  return []

def buscar_reviews(app_id, max_tentativas=3):
  """Busca o resumo das avaliações pelo novo endpoint da Steam"""
  url_reviews = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"

  params = {
    "input_json": json.dumps({
      "appid": int(app_id),
      "filter": 0,
      "language": "all",
      "review_type": 0,
      "purchase_type": 1,
      "num_per_page": 1
    })
  }

  for tentativa in range(1, max_tentativas + 1):
    try:
      resposta_reviews = requests.get(url_reviews, params=params, timeout=20)

      if resposta_reviews.status_code == 429:
        espera = tentativa * 10
        print(f"[Reviews] Limite de requisições. Aguardando {espera}s...")
        time.sleep(espera)
        continue

      resposta_reviews.raise_for_status()
      dados_reviews = resposta_reviews.json()

      if isinstance(dados_reviews, dict) and "response" in dados_reviews:
        dados_reviews = dados_reviews["response"]

      if not isinstance(dados_reviews, dict):
        raise ValueError("Formato JSON inesperado")

      if "query_summary" not in dados_reviews:
        print(f"[Reviews] Resposta sem query_summary para o jogo {app_id}.")
        return None

      return dados_reviews
    
    except(requests.RequestException, json.JSONDecodeError, ValueError) as e:
      print(f"[Reviews] Tentativa {tentativa}/{max_tentativas} falhou: {e}")

      if tentativa < max_tentativas:
        time.sleep(tentativa*3)
  return None

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
  params = {"term": nome, "l": "portuguese", "cc": "BR"}

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

def buscar_detalhes(app_id, max_tentativas=3):
  """Busca os detalhes do jogo Steam lidando com Rate Limits"""
  url_details = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=br&l=portuguese"

  for tentativa in range(1, max_tentativas + 1):
    try:
      resp = requests.get(url_details, headers=headers, timeout=15)

      if resp.status_code == 429:
        espera = tentativa * 10
        print(f"[Detalhes] Limite de requisições atingido. Aguardando {espera}s...")
        time.sleep(espera)
        continue

      if resp.status_code == 200:
        dados = resp.json()
        if isinstance(dados, dict):
          return dados

    except Exception:
      if tentativa < max_tentativas:
        time.sleep(tentativa*3)
  
  return None

for indice, nome in enumerate(nomes_jogos, start=1):
  print(f"\n[{indice}/{len(nomes_jogos)}] Pesquisando na Steam: {nome}")

  app_id, nome_encontrado = buscar_appid_steam(nome)
  if app_id:
    chave_app = str(app_id)
    detalhes_json = buscar_detalhes(app_id)
    dados_reviews = buscar_reviews(app_id)
    tags_steamspy = buscar_tags_steamspy(app_id)

    if (isinstance(detalhes_json, dict) and chave_app in detalhes_json and isinstance(detalhes_json[chave_app], dict)):
      app_data = detalhes_json[chave_app]

      if(app_data.get("success") and "data" in app_data and isinstance(app_data["data"], dict)):
        if dados_reviews:
          resumo = dados_reviews.get("query_summary", {})
          app_data["data"]["reviews"] = {"query_summary": resumo, "total_matching": dados_reviews.get("total_matching"), "day_range_used": dados_reviews.get("day_range_used")}
          print(f"[Reviews] Resumo incorporado: {resumo.get('total_reviews', 'N/D')} avaliações.")
        else:
          print(f"[Reviews] Não foi possível obter as avaliações para o jogo {app_id}.")

        app_data["data"]["steamspy_tags"] = tags_steamspy

        caminho_saida = f"dados/raw/steam_gratis_{app_id}.json"
        with open(caminho_saida, "w", encoding="utf-8") as f:
          json.dump(detalhes_json, f, ensure_ascii=False, indent=4)

        print(f"💾 Salvo com sucesso: steam_gratis_{app_id}.json ({nome_encontrado})")
      else:
        print(f"⚠️ Jogo {app_id} sem página pública ou indisponível na loja BR.")
    else:
      print(f"❌ Falha ao obter detalhes para o AppID {app_id}.")
  else:
    print(f"❌ Jogo não encontrado na Steam.")

    

  time.sleep(1)
      