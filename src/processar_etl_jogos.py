import json
import os
import re
import pandas as pd

os.makedirs("dados/processed", exist_ok=True)

pasta_raw = "dados/raw"
jogos_consolidados = {}

def extrair_preco_original_steam(dados_json):
    """Extrai o preço cheio/original da Steam."""
    if not isinstance(dados_json, dict):
        return "N/A"

    for val in dados_json.values():
        if not isinstance(val, dict) or not val.get("success"):
            continue

        data = val.get("data")
        if not isinstance(data, dict):
            continue

        if data.get("is_free"):
            return "Grátis"

        price_info = data.get("price_overview")
        if not isinstance(price_info, dict):
            continue

        if price_info.get("currency") != "BRL":
            return "Preço em BRL indisponível"

        preco_formatado = price_info.get("initial_formatted")
        if preco_formatado:
            return preco_formatado

        preco_centavos = price_info.get("initial")
        if preco_centavos is not None:
            return f"R$ {preco_centavos / 100:.2f}".replace(".", ",")

        preco_atual = price_info.get("final_formatted")
        if preco_atual:
            return preco_atual

        preco_final = price_info.get("final")
        if preco_final is not None:
            return f"R$ {preco_final / 100:.2f}".replace(".", ",")
    return "N/A"

def extrair_preco_original_epic(dados_json):
    """Extrai o preço cheio/original da Epic Games"""
    price_info = dados_json.get("price", {}).get("totalPrice", {})
    fmt_price = price_info.get("fmtPrice", {})

    orig_fmt = fmt_price.get("originalPrice")
    if orig_fmt:
        return orig_fmt

    orig_cents = price_info.get("originalPrice")
    if orig_cents is not None:
        if orig_cents == 0:
            return "Grátis"
        return f"R$ {orig_cents / 100:.2f}".replace(".", ",")
    return "N/A"

def extrair_preco_original_gog(dados_json):
    """Extrai o preço cheio/original da GOG"""
    price_info = dados_json.get("price", {})

    base_price = (price_info.get("baseMoney", {}).get("amount") or price_info.get("baseAmount") or price_info.get("base"))
    if base_price is not None:
        try:
            # Remover simbolos de cifrão e espaços extras
            texto_limpo = re.sub(r"[^\d.,]", "", str(base_price)).strip()

            # Tratar virgulas decimais
            if "," in texto_limpo and "." in texto_limpo:
                texto_limpo = texto_limpo.replace(",", "")
            elif "," in texto_limpo:
                texto_limpo = texto_limpo.replace(",", ".")

            val_float = float(texto_limpo)
            if val_float == 0:
                return "Grátis"

            # Se o preço veio em dólares, aplica o fator de conversão
            if "$" in str(base_price) or ("R$" not in str(base_price) and val_float < 1000):
                valor_convertido = val_float * 1.934
                return f"R$ {valor_convertido:.2f}".replace(".", ",")

            return f"R$ {val_float:.2f}".replace(".", ",")
        
        except Exception:
            return str(base_price)

    return "N/A"

def normalizar_nome(nome):
    if not nome:
        return ""
    return re.sub(r"[^\w\s]", "", nome).lower().strip()

def formatar_data(data):
    if not data:
        return None

    if isinstance(data, str) and re.match(r"^\d{4}-\d{2}-\d{2}", data):
        data_convertida = pd.to_datetime(data, errors="coerce", utc=True)
    else:
        data_convertida = pd.to_datetime(data, errors="coerce", dayfirst=True)

    if pd.notna(data_convertida):
        return data_convertida.strftime("%d/%m/%Y")
    return data

print("Processando e cruzando ficheiros JSON de todas as três plataformas...")

# Fase de extração e agrupamento por jogo

for arquivo in os.listdir(pasta_raw):
    if not arquivo.endswith(".json"):
        continue

    caminho = os.path.join(pasta_raw, arquivo)
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue

    nome_jogo = None
    origem = ""

    if arquivo.startswith("steam_"):
        origem = "steam"
        for key, val in data.items():
            if isinstance(val, dict) and "data" in val:
                nome_jogo = val["data"].get("name")
    elif arquivo.startswith("epic_"):
        origem = "epic"
        nome_jogo = data.get("title") or data.get("appName")
    elif arquivo.startswith("gog_"):
        origem = "gog"
        nome_jogo = data.get("title")

    if not nome_jogo:
        continue

    chave = normalizar_nome(nome_jogo)
    if not chave:
        continue

    # Inicializa o dicionário do jogo se for a primeira vez que o vemos
    if chave not in jogos_consolidados:
        jogos_consolidados[chave] = {
            "nome_original": nome_jogo,
            # Flags de presença nas plataformas
            "tem_steam": False,
            "tem_epic": False,
            "tem_gog": False,
            # Steam Data
            "steam_generos": [],
            "steam_lancamento": None,
            "steam_preco": None,
            "steam_donos": "Desconhecido",
            "steam_reviews_qtd": 0,
            "steam_reviews_pct_positiva": None,
            # Epic Data
            "epic_generos": [],
            "epic_lancamento": None,
            "epic_preco": None,
            "epic_gratis_data": None,
            # GOG Data
            "gog_generos": [],
            "gog_lancamento": None,
            "gog_preco": None,
        }

    # Fase de transformação por plataforma
    reg = jogos_consolidados[chave]

    if origem == "steam":
        reg["tem_steam"] = True
        reg["steam_preco"] = extrair_preco_original_steam(data)

        for key, val in data.items():
            if isinstance(val, dict) and "data" in val:
                d = val["data"]
                reg["steam_lancamento"] = d.get("release_date", {}).get("date")

                genres = d.get("genres", [])
                if genres:
                    reg["steam_generos"] = [g.get("description") for g in genres]
                    # Quantidade de reviews / recomendações

                reviews = d.get("reviews", {})
                resumo = reviews.get("query_summary", {}) if isinstance(reviews, dict) else {}

                total_positivas = resumo.get("total_positive")
                total_negativas = resumo.get("total_negative")
                total_resumo = resumo.get("total_reviews")

                # Prioriza o total agregado; se não existir, somar positiva com negativa
                if total_resumo is not None:
                    reg["steam_reviews_qtd"] = int(total_resumo)
                elif total_positivas is not None and total_negativas is not None:
                    reg["steam_reviews_qtd"] = int(total_negativas + total_positivas)
                else:
                    reg["steam_reviews_qtd"] = None

                #Percentual positivo calculado apenas com contagens agregadas
                if(total_positivas is not None and total_negativas is not None and (total_positivas + total_negativas) > 0):
                    reg["steam_reviews_pct_positiva"] = round((total_positivas/(total_positivas+total_negativas)) * 100, 3)
                else:
                    reg["steam_reviews_pct_positiva"] = None

                recs = d.get("recommendations", {}).get("total")
                # Lógica da Valve Multiplier para estimar a quantidade de donos de determinado jogo através da quantidade de reviews e um fator médio
                if recs is not None and recs > 0:
                    min_donos = int(recs * 30)
                    max_donos = int(recs * 50)
                    reg["steam_donos"] = f"{min_donos:,} - {max_donos:,}"
                else:
                    reg["steam_donos"] = "Desconhecido"

    elif origem == "epic":
        reg["tem_epic"] = True
        reg["epic_lancamento"] = data.get("effectiveDate") or data.get("releaseDate")
        price_info = data.get("price", {}).get("totalPrice", {})
        reg["epic_preco"] = extrair_preco_original_epic(data)

        tags = data.get("tags") or data.get("categories", [])
        tag_names = []
        for t in tags:
            if isinstance(t, dict):
                tag_names.append(t.get("name") or t.get("groupName"))
            elif isinstance(t, str):
                tag_names.append(t)
        if tag_names:
            reg["epic_generos"] = [t for t in tag_names if t and not t.startswith("vfx")]

        if "gratis" in arquivo:
            reg["epic_gratis_data"] = data.get("data_aquisicao_gratis")

    elif origem == "gog":
        reg["tem_gog"] = True
        reg["gog_lancamento"] = data.get("release_date")
        reg["gog_preco"] = extrair_preco_original_gog(data)

        genres_gog = data.get("genres", [])
        if genres_gog:
            reg["gog_generos"] = [g.get("name") if isinstance(g, dict) else g for g in genres_gog]

# Consolidar linhas finais para o DataFrame
linhas_tabela = []

for chave, reg in jogos_consolidados.items():
    # Define gênero primário e secundário priorizando a Steam, dps Epic, dps GOG
    todos_generos = (reg["steam_generos"] + reg["epic_generos"] + reg["gog_generos"])
    generos_unicos = list(dict.fromkeys(todos_generos))

    genero_primario = (generos_unicos[0] if len(generos_unicos) > 0 else "Desconhecido")
    genero_secundario = (generos_unicos[1] if len(generos_unicos) > 1 else "Não especificado")
 
    #Data de lançamento unificada e padronizada
    lancamento = (reg["steam_lancamento"] or reg["epic_lancamento"] or reg["gog_lancamento"])
    lancamento = formatar_data(lancamento)

    linhas_tabela.append({
        "Jogo": reg["nome_original"],
        "Gênero primário": genero_primario,
        "Gênero secundário": genero_secundario,
        "Data de lançamento": lancamento,
        "Preço Steam": reg["steam_preco"],
        "Preço Epic": reg["epic_preco"],
        "Preço GOG": reg["gog_preco"],
        "Data Aquisição Gratuita Epic": reg["epic_gratis_data"],
        "Estimativa Donos Steam": reg["steam_donos"],
        "Qtd Reviews Steam": reg["steam_reviews_qtd"],
        "% Positivas Steam": reg["steam_reviews_pct_positiva"],
        "Disponível na Steam": "Sim" if reg["tem_steam"] else "Não",
        "Disponível na Epic": "Sim" if reg["tem_epic"] else "Não",
        "Disponível na GOG": "Sim" if reg["tem_gog"] else "Não",
    })

# Criar o dataframe final
df = pd.DataFrame(linhas_tabela)

df["Qtd Reviews Steam"] = df["Qtd Reviews Steam"].astype("Int64")

caminho_csv = "dados/processed/tabela_comparativa_jogos.csv"
df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")

print(f"\n🎉 Tabela criada com sucesso com {len(df)} jogos únicos! Guardada em: {caminho_csv}")