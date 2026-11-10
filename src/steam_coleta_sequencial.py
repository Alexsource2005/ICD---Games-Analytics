import json
import os
import time
import requests
from logger_utils import ativar_logger

API_KEY = "010187A20FDAB0733BE21A91A46BEB63"  

ativar_logger("Steam_Sequencial.txt")

DIRETORIO_SRC = os.path.dirname(os.path.abspath(__file__))
PASTA_RAIZ = os.path.dirname(DIRETORIO_SRC)
DIRETORIO_SAIDA = os.path.join(PASTA_RAIZ, "dados", "raw")

ALVO_JOGOS = 20000 #meta de jogos salvos
PAUSA_ENTRE_REQUISICOES = 1.2

os.makedirs(DIRETORIO_SAIDA, exist_ok=True)

headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def obter_lista_completa_appids():
    """Obtém a lista de AppIDs da Steam via IStoreService (com Key) ou via SteamSpy."""
    
    # 1. Tentativa via IStoreService (autenticado com API Key)
    if API_KEY:
        try:
            print("🔄 Tentando obter lista via Steam IStoreService (com API Key)...")
            url = f"https://api.steampowered.com/IStoreService/GetAppList/v1/?key={API_KEY}&include_games=true&max_results=50000"
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                dados = resp.json()
                apps = dados.get("response", {}).get("apps", [])
                if apps:
                    print(f"✅ Lista obtida via Steam IStoreService! Encontrados {len(apps)} AppIDs.")
                    return sorted(apps, key=lambda x: x["appid"])
            else:
                print(f"⚠️ IStoreService retornou status HTTP {resp.status_code}.")
        except Exception as e:
            print(f"⚠️ Tentativa IStoreService falhou: {e}")

    # 2. Fallback via SteamSpy (Retorna a lista global de todos os jogos ativos)
    try:
        print("🔄 Obtendo lista completa de AppIDs via SteamSpy...")
        url_spy = "https://steamspy.com/api.php?request=all"
        resp = requests.get(url_spy, headers=headers, timeout=40)
        if resp.status_code == 200:
            dados = resp.json()
            if isinstance(dados, dict):
                apps = [{"appid": int(k)} for k in dados.keys() if k.isdigit()]
                if apps:
                    print(f"✅ Lista obtida via SteamSpy! Encontrados {len(apps)} AppIDs.")
                    return sorted(apps, key=lambda x: x["appid"])
        else:
            print(f"⚠️ SteamSpy retornou status HTTP {resp.status_code}.")
    except Exception as e:
        print(f"⚠️ Tentativa SteamSpy falhou: {e}")

    return []

def buscar_tags_steamspy(app_id, max_tentativas=3):
    """Busca as tags da comunidade no SteamSpy"""
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
    """Busca o resumo das avaliações na API de User Revies"""
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
            resp = requests.get(url_reviews, params=params, headers=headers, timeout=20)
            if resp.status_code == 429:
                espera = tentativa * 15
                print(f"[Reviews] Rate limit (429). Aguardando {espera}s...")
                time.sleep(espera)
                continue

            resp.raise_for_status()
            dados = resp.json()

            if isinstance(dados, dict) and "response" in dados:
                dados = dados["response"]

            if isinstance(dados, dict) and "query_summary" in dados:
                return dados
            return None
        except Exception as e:
            if tentativa < max_tentativas:
                time.sleep(tentativa*3)
    return None

def buscar_detalhes(app_id, max_tentativas=3):
    """Busca os detalhes da loja Steam lidando com Rate Limits"""
    url_details = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=br&l=portuguese"

    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = requests.get(url_details, headers=headers, timeout=15)
            if resp.status_code == 429:
                espera = tentativa * 30
                print(f"[Detalhes] Rate limit atingido! Pausando por {espera}s...")
                time.sleep(espera)
                continue

            if resp.status_code == 200:
                dados = resp.json()
                if isinstance(dados, dict):
                    return dados
        except Exception as e:
            if tentativa < max_tentativas:
                time.sleep(tentativa*3)
    return None

def coletar_jogos_sequenciais():
    lista_apps = obter_lista_completa_appids()

    if not lista_apps:
        print("⚠️ Usando gerador numérico de IDs...")
        app_ids_para_processar = [str(i) for i in range(10, 3000000)]
    else:
        app_ids_para_processar = [str(item["appid"]) for item in lista_apps]

    jogos_coletados = 0
    if os.path.exists(DIRETORIO_SAIDA):
        for arq in os.listdir(DIRETORIO_SAIDA):
            if arq.startswith("steam_") and arq.endswith(".json"):
                jogos_coletados += 1

    print(f"📊 Progresso atual: {jogos_coletados}/{ALVO_JOGOS} jogos salvos em '{DIRETORIO_SAIDA}'.")

    for app_id in app_ids_para_processar:
        if jogos_coletados >= ALVO_JOGOS:
            print(f"🎉 Meta de {ALVO_JOGOS} jogos alcançada com sucesso!")
            break

        caminho_arquivo = os.path.join(DIRETORIO_SAIDA, f"steam_{app_id}.json")

        # Pula se o ID já foi coletado
        if os.path.exists(caminho_arquivo):
            continue

        print(f"[{jogos_coletados + 1}/{ALVO_JOGOS}] [AppID: {app_id}] Verificando...")

        detalhes = buscar_detalhes(app_id)
        time.sleep(PAUSA_ENTRE_REQUISICOES)

        if not detalhes or app_id not in detalhes or not detalhes[app_id].get("success"):
            continue

        app_data = detalhes[app_id].get("data", {})
        tipo_item = app_data.get("type", "").lower()

        if tipo_item != "game":
            continue

        nome_jogo = app_data.get("name", "Sem Nome")

        dados_reviews = buscar_reviews(app_id)
        if dados_reviews:
            app_data["reviews"] = dados_reviews

        tags = buscar_tags_steamspy(app_id)
        app_data["steamspy_tags"] = tags

        conteudo_salvar = detalhes
        conteudo_salvar[app_id]["data"] = app_data

        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(conteudo_salvar, f, ensure_ascii=False, indent=4)

        jogos_coletados +=1
        print(f"💾 Salvo: {nome_jogo} -> steam_{app_id}.json")

if __name__ == "__main__":
    coletar_jogos_sequenciais()