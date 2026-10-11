import json
import os
import requests

# --- SUAS CREDENCIAIS REAIS DA STEAM ---
API_KEY = "010187A20FDAB0733BE21A91A46BEB63"
STEAM_ID = "76561199557190797"

# 1. Garante que a pasta dados/raw/ existe no projeto
os.makedirs("dados/raw", exist_ok=True)

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