import json
import os
import re
import time
import requests

os.makedirs("dados/raw", exist_ok=True)

headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")}

pasta_raw = "dados/raw"
nomes_jogos = set()

print("🔄 Lendo nomes de jogos coletados anteriormente nas pastas locais (Steam e Epic)...")

for arquivo in os.listdir(pasta_raw):
    if arquivo.endswith(".json") and (arquivo.startswith("steam_") or arquivo.startswith("epic_")):
        caminho = os.path.join(pasta_raw, arquivo)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                data = json.load(f)

                nome_jogo = None

                if "steam_" in arquivo:
                    for key, val in data.items():
                        if isinstance(val, dict) and "data" in val:
                            nome_jogo = val["data"].get("name")
                            break
                elif "epic_" in arquivo:
                    nome_jogo = data.get("title") or data.get("appName")

                if nome_jogo:
                    nome_limpo = re.sub(r"[™®©]", "", nome_jogo).strip()
                    if nome_limpo:
                        nomes_jogos.add(nome_limpo)
        except Exception:
            continue

print(f"✅ Total de jogos únicos extraídos para busca na GOG: {len(nomes_jogos)}")

def limpar_nome(nome):
    nome_limpo = re.sub(r"[™®©]", "", nome)
    nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
    return nome_limpo.strip()

def buscar_jogo_gog(nome_original):
    nome_busca = limpar_nome(nome_original)
    url = "https://catalog.gog.com/v1/catalog"
    params = {
        "limit": 5,
        "productType": "in:game",
        "query": f"like:{nome_busca}",
        "locale": "en-US",
        "countryCode": "BR",
        "currencyCode": "BRL",
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            products = dados.get("products", [])

            if products:
                palavras_orig = set(nome_busca.lower().split())
                nums_orig = re.findall(r"\d+", nome_busca)

                for prod in products:
                    titulo_prod = prod.get("title", "").lower()
                    palavras_prod = set(titulo_prod.split())
                    nums_prod = re.findall(r"\d+", titulo_prod)

                    if nums_orig != nums_prod:
                        continue

                    intersecao = palavras_orig.intersection(palavras_prod)
                    if len(intersecao) >= max(1, len(palavras_orig) - 1):
                        return prod
    except Exception as e:
        print(f"⚠️ Erro na consulta à GOG para '{nome_original}': {e}")
    return None

for indice, nome in enumerate(sorted(nomes_jogos), start=1):
    print(f"\n[{indice}/{len(nomes_jogos)}] pesquisando na GOG: {nome}")
    produto_gog = buscar_jogo_gog(nome)

    if produto_gog:
        prod_id = produto_gog.get("id")
        titulo_gog = produto_gog.get("title")

        detalhes_url = f"https://api.gog.com/products/{prod_id}?locale=en_US"
        try:
            resp_detalhes = requests.get(detalhes_url, headers=headers, timeout=10)
            if resp_detalhes.status_code == 200:
                detalhes_json = resp_detalhes.json()
                detalhes_json["price"] = produto_gog.get("price")
                # Registra a moeda solicitada para o ETL, sem fazer conversão cambial.
                detalhes_json["_price_currency_requested"] = "BRL"
            else:
                detalhes_json = produto_gog
        except Exception:
            detalhes_json = produto_gog

        if isinstance(detalhes_json, dict):
            detalhes_json["_price_currency_requested"] = "BRL"

        caminho_saida = f"dados/raw/gog_{prod_id}.json"
        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(detalhes_json, f, ensure_ascii=False, indent=4)

        print(f"   💾 Salvo com sucesso: gog_{prod_id}.json ({titulo_gog})")
    else:
        print(f"   ❌ Jogo não encontrado na GOG.")

    time.sleep(0.5)