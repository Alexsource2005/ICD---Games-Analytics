import json
import os
import time
import requests

# --- SUAS CREDENCIAIS REAIS DA STEAM ---
API_KEY = "010187A20FDAB0733BE21A91A46BEB63"
STEAM_ID = "76561199557190797"

# 1. Garante que a pasta dados/raw/ existe no projeto
os.makedirs("dados/raw", exist_ok=True)

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

print("🔄 Buscando os jogos da sua biblioteca da Steam...")
url_owned = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={API_KEY}&steamid={STEAM_ID}&include_appinfo=true&format=json"

try:
  resposta_owned = requests.get(url_owned)
  dados_owned = resposta_owned.json()

  # Acessa a lista de jogos dentro do JSON retornado pela Steam
  lista_jogos = dados_owned.get("response", {}).get("games", [])

  # Extrai apenas os App IDs em formato de texto (string)
  app_ids = [str(jogo["appid"]) for jogo in lista_jogos]
  print(
      f" Sucesso! Encontrados {len(app_ids)} jogos na sua biblioteca.\n"
      "Iniciando download dos detalhes..."
  )

  # 2. Loop para percorrer cada ID obtido da biblioteca
  for indice, app_id in enumerate(app_ids, start=1):
    url_details = f"https://store.steampowered.com/api/appdetails?appids={app_id}"

    try:
      # Faz a requisição dos detalhes do jogo
      resposta_details = requests.get(url_details)
      dados_details = resposta_details.json()

      dados_reviews = buscar_reviews(app_id)

      if dados_reviews:
        if(app_id in dados_details and dados_details[app_id].get("success") and "data" in dados_details[app_id]):
          dados_details[app_id]["data"]["reviews"] = dados_reviews

          print(f"[Reviews] Dados incorporados ao jogo {app_id}.")
        else:
          print(f"[Reviews] Não foi possível incorporar as reviews ao jogo {app_id}: detalhes inválidos.")
      else:
        print(f"[Reviews] Reviews indisponíveis para o jogo {app_id}.")

      # Define o caminho do arquivo JSON bruto
      caminho_arquivo = f"dados/raw/steam_{app_id}.json"

      # Salva o dicionário em formato JSON na pasta correta
      with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados_details, f, ensure_ascii=False, indent=4)

      print(
          f"[{indice}/{len(app_ids)}] Salvo com sucesso: steam_{app_id}.json"
      )

    except Exception as e_jogo:
      print(f" Erro ao coletar o jogo ID {app_id}: {e_jogo}")

  print(
      "\n Processo de coleta da Steam concluído com sucesso! Todos os arquivos"
      " JSON foram salvos em dados/raw/"
  )

except Exception as e_bib:
  print(f" Erro crítico ao acessar a API da biblioteca da Steam: {e_bib}")