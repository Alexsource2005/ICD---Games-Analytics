import json
import os
import re
import pandas as pd

os.makedirs("dados/processed", exist_ok=True)

pasta_raw = "dados/raw"
jogos_consolidados = {}

MESES = {
    "janeiro": 1, "jan": 1, "january": 1,
    "fevereiro": 2, "fev": 2, "february": 2, "feb": 2,
    "março": 3, "marco": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4,
    "maio": 5, "mai": 5, "may": 5,
    "junho": 6, "jun": 6, "june": 6,
    "julho": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "setembro": 9, "set": 9, "september": 9, "sep": 9,
    "outubro": 10, "out": 10, "october": 10, "oct": 10,
    "novembro": 11, "nov": 11, "november": 11,
    "dezembro": 12, "dez": 12, "december": 12, "dec": 12
}

EPIC_TAG_MAP = {
    "1216": "Ação",
    "21109": "Ação",
    "1117": "Aventura",
    "1367": "RPG",
    "1188": "Corrida",
    "21121": "Corrida",
    "1212": "Direção",
    "1218": "Tiro",
    "1185": "Primeira Pessoa",
    "18051": "Estratégia",
    "21122": "Estratégia",
    "1088": "Roguelite",
    "1151": "Plataforma",
    "1181": "Cartas",
    "1298": "Puzzle",
    "1263": "Indie",
    "1084": "Stealth",
    "1381": "Exploração",
    "1400": "Simulação"
}

def inferir_generos_texto(texto):
    """Extrai gêneros a partir do título ou descrição caso metadados faltem"""
    if not texto:
        return []
    txt = texto.lower()
    generos = []

    if any(k in txt for k in ["rally", "corrida", "racing"]):
        generos.append("Corrida")
    if any(k in txt for k in ["ação", "action", "combate", "fighting", "assassino", "assassin"]):
        generos.append("Ação")
    if any(k in txt for k in ["aventura", "adventure"]):
        generos.append("Aventura")
    if any(k in txt for k in ["rpg", "dungeon", "role-playing"]):
        generos.append("RPG")
    if any(k in txt for k in ["cartas", "card", "baralho", "deck", "deck-building"]):
        generos.append("Cartas")
    if any(k in txt for k in ["roguelike", "rogue-like"]):
        generos.append("Roguelike")
    if any(k in txt for k in ["roguelite", "rogue-lite"]):
        generos.append("Roguelite")
    if any(k in txt for k in ["plataforma", "plataformas", "platform", "platformer"]):
        generos.append("Plataforma")
    if any(k in txt for k in ["puzzle", "quebra-cabeça"]):
        generos.append("Puzzle")
    if any(k in txt for k in ["tiro", "shooter", "fps"]):
        generos.append("Tiro")
    if any(k in txt for k in ["indie"]):
        generos.append("Indie")
    return generos

def padronizar_data_acquisicao(texto_data):
    """Garante a formatação dd/mm/aaaa - dd/mm/aaaa no ETL."""
    if not texto_data or not isinstance(texto_data, str):
        return None
    
    texto = texto_data.strip()
    if not texto or texto.lower() in ["desconhecida", "n/a", "none", "null"]:
        return None

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}", texto):
        return re.sub(r"\s*-\s*", " - ", texto)

    texto_lower = texto.lower()
    anos = re.findall(r"\b(20\d{2})\b", texto_lower)
    ano_base = anos[0] if anos else "2020"

    datas_completas = re.findall(r"\b(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})\b", texto_lower)
    if len(datas_completas) == 2:
        d1, m1, y1 = datas_completas[0]
        d2, m2, y2 = datas_completas[1]
        y1 = f"20{y1}" if len(y1) == 2 else y1
        y2 = f"20{y2}" if len(y2) == 2 else y2
        return f"{int(d1):02d}/{int(m1):02d}/{y1} - {int(d2):02d}/{int(m2):02d}/{y2}"

    m_range_num = re.search(r"\b(\d{1,2})(?:[\/\.-](\d{1,2}))?\s*(?:a|-|–|à|até)\s*(\d{1,2})[\/\.-](\d{1,2})(?:[\/\.-](\d{2,4}))?\b", texto_lower)
    if m_range_num:
        dia_ini, mes_ini, dia_fim, mes_fim, ano_str = m_range_num.groups()
        ano = f"20{ano_str}" if ano_str and len(ano_str) == 2 else (ano_str or ano_base)
        m_ini = int(mes_ini) if mes_ini else int(mes_fim)
        m_fim = int(mes_fim)
        ano_fim = str(int(ano) + 1) if m_ini == 12 and m_fim == 1 else ano
        return f"{int(dia_ini):02d}/{m_ini:02d}/{ano} - {int(dia_fim):02d}/{m_fim:02d}/{ano_fim}"

    m_mes_primeiro = re.search(r"([a-zç]+)\s*(\d{1,2})\s*[-–aà]\s*(?:([a-zç]+)\s*)?(\d{1,2})(?:[,\s]+(20\d{2}))?", texto_lower)
    if m_mes_primeiro and m_mes_primeiro.group(1) in MESES:
        m1 = MESES[m_mes_primeiro.group(1)]
        d1 = int(m_mes_primeiro.group(2))
        m2_str = m_mes_primeiro.group(3)
        m2 = MESES[m2_str] if m2_str and m2_str in MESES else m1
        d2 = int(m_mes_primeiro.group(4))
        ano = m_mes_primeiro.group(5) or ano_base
        ano_fim = str(int(ano) + 1) if m1 == 12 and m2 == 1 else ano
        return f"{d1:02d}/{m1:02d}/{ano} - {d2:02d}/{m2:02d}/{ano_fim}"

    if len(datas_completas) == 1:
        d, m, y = datas_completas[0]
        y = f"20{y}" if len(y) == 2 else y
        return f"{int(d):02d}/{int(m):02d}/{y} - {int(d):02d}/{int(m):02d}/{y}"

    return texto_data

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
    """Extrai o preço original da Epic somente quando a moeda é BRL."""
    price_info = dados_json.get("price", {}).get("totalPrice", {})
    fmt_price = price_info.get("fmtPrice", {})

    orig_cents = price_info.get("originalPrice")
    if orig_cents == 0:
        return "Grátis"

    currency = (
        price_info.get("currencyCode")
        or price_info.get("currency")
        or dados_json.get("currencyCode")
    )
    orig_fmt = fmt_price.get("originalPrice")

    if isinstance(orig_fmt, str) and orig_fmt.strip():
        if "R$" in orig_fmt:
            return orig_fmt.strip()
        return "Preço em BRL indisponível"

    if currency == "BRL" and orig_cents is not None:
        return f"R$ {orig_cents / 100:.2f}".replace(".", ",")

    return "Preço em BRL indisponível"

def extrair_preco_original_gog(dados_json):
    """Extrai o preço original da GOG sem converter valores de outras moedas."""
    price_info = dados_json.get("price", {})
    if not isinstance(price_info, dict):
        return "Preço em BRL indisponível"

    money = price_info.get("baseMoney") or price_info.get("finalMoney") or {}
    if not isinstance(money, dict):
        money = {}

    currency = (
        money.get("currency")
        or money.get("currencyCode")
        or price_info.get("currencyCode")
        or price_info.get("currency")
    )
    base_price = (
        money.get("amount")
        if money.get("amount") is not None
        else price_info.get("baseAmount", price_info.get("base"))
    )

    formatted = (
        price_info.get("baseFormatted")
        or price_info.get("formatted")
        or money.get("formattedAmount")
    )
    if isinstance(formatted, str) and formatted.strip():
        if "R$" in formatted:
            return formatted.strip()
        if currency and currency != "BRL":
            return "Preço em BRL indisponível"

    if base_price is None:
        return "N/A"

    try:
        texto = str(base_price).strip()
        if texto in {"0", "0.0", "0.00"}:
            return "Grátis"

        if currency and currency != "BRL":
            return "Preço em BRL indisponível"
        if currency != "BRL" and dados_json.get("_price_currency_requested") != "BRL":
            return "Preço em BRL indisponível"

        texto_limpo = re.sub(r"[^\d.,]", "", texto)
        if "," in texto_limpo and "." in texto_limpo:
            if texto_limpo.rfind(",") > texto_limpo.rfind("."):
                texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
            else:
                texto_limpo = texto_limpo.replace(",", "")
        elif "," in texto_limpo:
            texto_limpo = texto_limpo.replace(",", ".")

        valor = float(texto_limpo)
        return f"R$ {valor:.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "N/A"

def normalizar_nome(nome):
    if not nome:
        return ""
    return re.sub(r"[^\w\s]", "", nome).lower().strip()

def formatar_data(data):
    """padroniza qualquer data de lançamento para o formato dd/mm/aaaa"""
    if not data or not isinstance(data, str) or pd.isna(data):
        return None
    texto = data.strip().lower()

    if any(p in texto for p in ["breve", "anunciar", "coming soon", "to be announced", "trimestre"]):
        return None

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        return texto.upper()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", texto):
        d_conv = pd.to_datetime(data, errors="coerce", utc=True)
        if pd.notna(d_conv):
            return d_conv.strftime("%d/%m/%Y")

    match_slash = re.fullmatch(r"(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})", texto)
    if match_slash:
        d, m, y = match_slash.groups()
        y = f"20{y}" if len(y) == 2 else y
        return f"{int(d):02d}/{int(m):02d}/{y}"

    m_ext = re.search(r"(\d{1,2})\s*(?:\bde\s+)?([a-zç]+)\.?\s*(?:\bde\s+)?,?\s*(20\d{2}|19\d{2})", texto)
    if m_ext:
        dia = int(m_ext.group(1))
        mes_str = m_ext.group(2)
        ano = m_ext.group(3)
        if mes_str in MESES:
            return f"{dia:02d}/{MESES[mes_str]:02d}/{ano}"

    m_ext_rev = re.search(r"([a-zç]+)\.?\s*(\d{1,2})\s*,?\s*(20\d{2}|19\d{2})", texto)
    if m_ext_rev:
        mes_str = m_ext_rev.group(1)
        dia = int(m_ext_rev.group(2))
        ano = m_ext_rev.group(3)
        if mes_str in MESES:
            return f"{dia:02d}/{MESES[mes_str]:02d}/{ano}"

    try:
        d_conv = pd.to_datetime(data, errors="coerce", dayfirst=True)
        if pd.notna(d_conv):
            return d_conv.strftime("%d/%m/%Y")
    except Exception:
        pass

    return None

print("Processando e cruzando ficheiros JSON de todas as três plataformas...")

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
    descricao_texto = ""

    if arquivo.startswith("steam_"):
        origem = "steam"
        for key, val in data.items():
            if isinstance(val, dict) and "data" in val:
                nome_jogo = val["data"].get("name")
                descricao_texto = val["data"].get("short_description", "")
    elif arquivo.startswith("epic_"):
        origem = "epic"
        nome_jogo = data.get("title") or data.get("appName")
        descricao_texto = data.get("description", "")
    elif arquivo.startswith("gog_"):
        origem = "gog"
        nome_jogo = data.get("title")
        descricao_texto = ""

    if not nome_jogo:
        continue

    chave = normalizar_nome(nome_jogo)
    if not chave:
        continue

    if chave not in jogos_consolidados:
        jogos_consolidados[chave] = {
            "nome_original": nome_jogo,
            "descricao": descricao_texto,
            "tem_steam": False,
            "tem_epic": False,
            "tem_gog": False,
            "steam_generos": [],
            "steam_lancamento": None,
            "steam_preco": None,
            "steam_donos": "Desconhecido",
            "steam_reviews_qtd": 0,
            "steam_reviews_pct_positiva": None,
            "epic_generos": [],
            "epic_lancamento": None,
            "epic_preco": None,
            "epic_gratis_data": None,
            "gog_generos": [],
            "gog_lancamento": None,
            "gog_preco": None,
        }

    reg = jogos_consolidados[chave]
    if not reg["descricao"] and descricao_texto:
        reg["descricao"] = descricao_texto

    if origem == "steam":
        reg["tem_steam"] = True
        reg["steam_preco"] = extrair_preco_original_steam(data)

        for key, val in data.items():
            if isinstance(val, dict) and "data" in val:
                d = val["data"]
                reg["steam_lancamento"] = d.get("release_date", {}).get("date")

                steam_gens = []
                genres = d.get("genres", [])
                if genres:
                    steam_gens.extend([g.get("description") for g in genres if isinstance(g, dict) and g.get("description")])

                # Inclui as tags coletadas via SteamSpy
                steamspy_tags = d.get("steamspy_tags", [])
                if isinstance(steamspy_tags, list):
                    for tag in steamspy_tags:
                        if isinstance(tag, str) and tag not in steam_gens:
                            steam_gens.append(tag)
                elif isinstance(steamspy_tags, dict):
                    for tag in steamspy_tags.keys():
                        if tag not in steam_gens:
                            steam_gens.append(tag)

                reg["steam_generos"] = steam_gens

                reviews = d.get("reviews", {})
                resumo = reviews.get("query_summary", {}) if isinstance(reviews, dict) else {}

                total_positivas = resumo.get("total_positive")
                total_negativas = resumo.get("total_negative")
                total_resumo = resumo.get("total_reviews")

                if total_resumo is not None:
                    reg["steam_reviews_qtd"] = int(total_resumo)
                elif total_positivas is not None and total_negativas is not None:
                    reg["steam_reviews_qtd"] = int(total_negativas + total_positivas)
                else:
                    reg["steam_reviews_qtd"] = None

                if total_positivas is not None and total_negativas is not None and (total_positivas + total_negativas) > 0:
                    reg["steam_reviews_pct_positiva"] = round((total_positivas / (total_positivas + total_negativas)) * 100, 3)
                else:
                    reg["steam_reviews_pct_positiva"] = None

                recs = d.get("recommendations", {}).get("total")
                if recs is not None and recs > 0:
                    min_donos = int(recs * 30)
                    max_donos = int(recs * 50)
                    reg["steam_donos"] = f"{min_donos:,} - {max_donos:,}"
                else:
                    reg["steam_donos"] = "Desconhecido"

    elif origem == "epic":
        reg["tem_epic"] = True
        reg["epic_lancamento"] = data.get("effectiveDate") or data.get("releaseDate")
        reg["epic_preco"] = extrair_preco_original_epic(data)

        tags = data.get("tags") or []
        epic_gens = []
        for t in tags:
            if isinstance(t, dict):
                tid = str(t.get("id"))
                tname = t.get("name") or t.get("groupName") or EPIC_TAG_MAP.get(tid)
                if tname and tname not in epic_gens:
                    epic_gens.append(tname)
        reg["epic_generos"] = epic_gens

        if "gratis" in arquivo:
            raw_gratis = data.get("data_aquisicao_gratis")
            reg["epic_gratis_data"] = padronizar_data_acquisicao(raw_gratis)

    elif origem == "gog":
        reg["tem_gog"] = True
        reg["gog_lancamento"] = data.get("release_date")
        reg["gog_preco"] = extrair_preco_original_gog(data)

        # Inclui gêneros e tags retornados do GOG
        genres_gog = data.get("genres", []) or []
        tags_gog = data.get("tags", []) or []

        gog_gens = []
        for g in genres_gog:
            nome = g.get("name") if isinstance(g, dict) else str(g)
            if nome and nome not in gog_gens:
                gog_gens.append(nome)

        for t in tags_gog:
            nome = t.get("name") if isinstance(t, dict) else str(t)
            if nome and nome not in gog_gens:
                gog_gens.append(nome)

        reg["gog_generos"] = gog_gens

# Consolidar linhas finais para o DataFrame
linhas_tabela = []

for chave, reg in jogos_consolidados.items():
    todos_generos = (reg["steam_generos"] + reg["epic_generos"] + reg["gog_generos"])
    generos_unicos = list(dict.fromkeys(todos_generos))

    generos_texto = inferir_generos_texto(f"{reg['nome_original']} {reg['descricao']}")
    for g in generos_texto:
        if g not in generos_unicos:
            generos_unicos.append(g)

    genero_primario = generos_unicos[0] if len(generos_unicos) > 0 else "Desconhecido"
    genero_secundario = generos_unicos[1] if len(generos_unicos) > 1 else "Não especificado"

    lancamento_bruto = (reg["steam_lancamento"] or reg["epic_lancamento"] or reg["gog_lancamento"])
    lancamento = formatar_data(lancamento_bruto)

    if not lancamento:
        continue

    preco_steam = reg["steam_preco"]
    preco_epic = reg["epic_preco"]
    preco_gog = reg["gog_preco"]

    sem_preco = {"N/A", "Preço em BRL indisponível", None}
    if preco_steam in sem_preco and preco_epic in sem_preco and preco_gog in sem_preco:
        continue

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

df = pd.DataFrame(linhas_tabela)
df["Qtd Reviews Steam"] = df["Qtd Reviews Steam"].astype("Int64")

caminho_csv = "dados/processed/tabela_comparativa_jogos.csv"
df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")

print(f"\n🎉 Tabela criada com sucesso com {len(df)} jogos únicos! Guardada em: {caminho_csv}")