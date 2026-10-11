import json
import os
import re
from epicstore_api import EpicGamesStoreAPI 

# Inicializa a API da Epic Games
api = EpicGamesStoreAPI()

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
    if arquivo.startswith("steam_") and arquivo.endswith(".json"):
        caminho = os.path.join(pasta_steam, arquivo)
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = json.load(f)
            app_id = arquivo.replace("steam_", "").replace(".json", "")
            try:
                if conteudo.get(str(app_id), {}).get("success"):
                    nome_jogo = conteudo[str(app_id)]["data"]["name"]
                    jogos_para_buscar.append(nome_jogo)
            except Exception:
                continue

print(
    f"Encontrados {len(jogos_para_buscar)} nomes de jogos da Steam para bucar na"
    " Epic."
)

#Bucas e coletar os dados correspondentes na Epic Games
for indice, nome in enumerate(jogos_para_buscar, start=1):
    nome_busca = limpar_nome_jogo(nome)

    print(f"\n[{indice}] Pesquisando: {nome}")
    if nome_busca != nome:
        print(f"↳ Nome limpo: {nome_busca}")

    try:
        #Tentativa 1: Busca com o nome limpo principal
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
            # Procura na lista de resultados o item cuja correspondência de título seja mais fidedigna
            palavra_chave_principal = nome_busca.split()[0].lower()  # Ex: pega a primeira palavra principal
            for produto in elements:
                titulo_prod = produto.get("title", "").lower()
                # Validação básica para evitar falsos positivos grosseiros
                if palavra_chave_principal in titulo_prod:
                    jogo_encontrado = produto
                    break

        if jogo_encontrado:
            slug = jogo_encontrado.get("productSlug")
        
            if slug:
                try:
                    detalhes = api.get_product(slug)
                except Exception as e_detalhes:
                    print(
                        f" Erro ao puxar detalhes profundos ({e_detalhes}), salvando"
                        " dados ao catálogo básico"
                    )
                    detalhes = jogo_encontrado

                slug_limpo = slug.replace("/", "_")
                caminho_saida = f"dados/raw/epic_{slug_limpo}.json"

                with open(caminho_saida, "w", encoding="utf-8") as f:
                    json.dump(detalhes, f, ensure_ascii=False, indent=4)
                print(f"Salvo com sucesso: epic_{slug_limpo}.json")
            else:
                print(f"Slug não encontrado para '{nome}'.")
        else:
            print(f"Nenhum jogo encontrado na Epic para '{nome}'.")
    except Exception as e:
        print("Erro crítico ao buscar '{nome}': {e}")