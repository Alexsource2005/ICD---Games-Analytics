import json
import os
import re
from bs4 import BeautifulSoup
import requests

pasta_raw = "dados/raw"
headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")}

print("Iniciando varredura e scraping de reviews para Epic Games e GOG...")

for arquivo in os.listdir(pasta_raw):
    if not arquivo.endswith(".json"):
        continue

    caminho = os.path.join(pasta_raw, arquivo)
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    # PROCESSAMENTO GOG
    if arquivo.startswith("gog_"):
        gog_id = arquivo.replace("gog_", "").replace(".json", "")
        titulo = data.get("title", "Desconhecido")
        print(f"\n[GOG] Analisando: {titulo} (ID: {gog_id})")

        #endpoint interno da GOG de resumo de reviews
        url_reviews_gog = (f"https://reviews.gog.com/v1/products/{gog_id}/summary?rating=all")
        try:
            resp = requests.get(url_reviews_gog, headers=headers, timeout=5)
            if resp.status_code == 200:
                rev_data = resp.json()
                total_reviews = rev_data.get("ratingCount", 0)
                average_score = rev_data.get("averageRating", 0) # Geralmente de 0 a 5

                # Converte a nota média em porcentagem aproximada (4.5/5 -> 90%)
                pct_positiva = (round((average_score/5.0)*100, 1) if average_score > 0 else None)

                print(f"✅ GOG Reviews encontrados -> Qtd: {total_reviews}, Média: {average_score} ({pct_positiva}%")

                # Atualiza o JSON local com os dados encontrados
                data["reviews_qtd_scrapping"] = total_reviews
                data["reviews_pct_scrapping"] = pct_positiva
                with open(caminho, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            else:
                print("⚠️ Sem resumo de reviews disponível na API da GOG.")
        except Exception as e:
            print(f"   ❌ Erro ao buscar reviews da GOG: {e}")

    # PROCESSAMENTO EPIC GAMES
   