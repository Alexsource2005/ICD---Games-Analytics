
import json
import os
import re
import time
import math
import requests
from logger_utils import ativar_logger

ativar_logger("gog_log.txt")

os.makedirs("dados/raw", exist_ok=True)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

pasta_raw = "dados/raw"
nomes_jogos = set()

print(
    "🔄 Lendo nomes de jogos coletados anteriormente "
    "nas pastas locais (Steam e Epic)..."
)

for arquivo in os.listdir(pasta_raw):
    if arquivo.endswith(".json") and (
        arquivo.startswith("steam_") or arquivo.startswith("epic_")
    ):
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

print(
    f"✅ Total de jogos únicos extraídos para busca "
    f"na GOG: {len(nomes_jogos)}"
)


def limpar_nome(nome):
    nome_limpo = re.sub(r"[™®©]", "", nome)
    nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
    return nome_limpo.strip()


MAPA_TAGS = {
    "Action": "Ação",
    "Adventure": "Aventura",
    "Atmospheric": "Atmosférico",
    "Cozy": "Aconchegante",
    "Difficult": "Difícil",
    "Open World": "Mundo Aberto",
    "Physics": "Física",
    "Racing": "Corrida",
    "Rally": "Corrida",
    "Relaxing": "Relaxante",
    "Shooter": "Tiro",
    "Simulation": "Simulação",
    "Story Rich": "Rico em História",
    "Strategy": "Estratégia",
    "Survival": "Sobrevivência",
}

def traduzir_estrutura(lista_itens):
    """Traduz o campo 'name' em listas de tags ou gêneros retornadas pela GOG."""
    if not isinstance(lista_itens, list):
        return lista_itens
    
    itens_traduzidos = []
    for item in lista_itens:
        if isinstance(item, dict):
            nome_en = item.get("name", "")
            item_copia = item.copy()
            # Substitui 'name' pelo termo em PT-BR (ou mantém o original se não estiver no dicionário)
            item_copia["name"] = MAPA_TAGS.get(nome_en, nome_en)
            item_copia["name_en"] = nome_en  # Opcional: preserva o nome original em inglês
            itens_traduzidos.append(item_copia)
        else:
            itens_traduzidos.append(item)
            
    return itens_traduzidos

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
        "expand": "genres, tags",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

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
        print(
            f"⚠️ Erro na consulta à GOG "
            f"para '{nome_original}': {e}"
        )

    return None


def converter_inteiro(valor):
    """Converte valores de contagem retornados pela API para int."""
    try:
        if valor is None:
            return None

        return int(float(valor))

    except (TypeError, ValueError):
        return None


def normalizar_nota_review(valor):
    """
    Normaliza a nota de uma avaliação individual para escala de 0 a 5.

    A API antiga da GOG representa estrelas multiplicadas por 10
    (30 = 3 estrelas).
    """
    try:
        nota = float(valor)

    except (TypeError, ValueError):
        return None

    if 0 <= nota <= 5:
        return nota

    if 0 < nota <= 50:
        return nota / 10

    return None


def normalizar_nota_media(valor):
    """Normaliza a média do endpoint reviews.gog.com para escala de 0 a 5."""
    try:
        nota = float(valor)

    except (TypeError, ValueError):
        return None

    if 0 <= nota <= 5:
        return round(nota, 2)

    # Algumas respostas GOG representam a média em décimos de estrela.
    if 0 < nota <= 50:
        return round(nota / 10, 2)

    # Fallback: API de detalhes da GOG usa rating em escala de 0 a 500.
    if 0 < nota <= 500:
        return round(nota / 100, 2)

    return None


def localizar_lista_reviews(payload):
    """
    Localiza a lista de avaliações em estruturas aninhadas como _embedded.

    Retorna a primeira lista cujos itens tenham algum campo de nota.
    """
    chaves_nota = {
        "rating",
        "overallRating",
        "stars",
        "score"
    }

    fila = [payload]
    listas_vazias = []

    while fila:
        atual = fila.pop(0)

        if isinstance(atual, dict):
            for valor in atual.values():

                if isinstance(valor, list):
                    if valor and any(
                        isinstance(item, dict)
                        and any(chave in item for chave in chaves_nota)
                        for item in valor
                    ):
                        return valor

                    if not valor:
                        listas_vazias.append(valor)

                    else:
                        fila.append(valor)

                elif isinstance(valor, dict):
                    fila.append(valor)

        elif isinstance(atual, list):
            fila.extend(atual)

    return listas_vazias[0] if listas_vazias else []



def extrair_nota_individual(review):
    """Extrai e normaliza a nota de uma avaliação individual."""

    if not isinstance(review, dict):
        return None

    # Estrutura utilizada pela API atual da GOG:
    # rating = {"value": 30, ...}
    rating = review.get("rating")

    if isinstance(rating, dict):
        for campo in ("value", "rating", "stars", "score"):
            if rating.get(campo) is not None:
                return normalizar_nota_review(rating[campo])

    # Compatibilidade com estruturas alternativas
    elif rating is not None:
        return normalizar_nota_review(rating)

    for campo in ("overallRating", "stars", "score", "value"):
        if review.get(campo) is not None:
            return normalizar_nota_review(review[campo])

    return None


def obter_chave_review(review):
    """Gera uma chave para evitar contar duas vezes avaliações repetidas."""
    if not isinstance(review, dict):
        return None

    for campo in ("id", "reviewId", "_id"):
        if review.get(campo) is not None:
            return str(review[campo])

    return json.dumps(
        review,
        sort_keys=True,
        ensure_ascii=False
    )

def fazer_requisicao_com_retry(url, params=None, headers=None, timeout=20, max_tentativas=3):
    """Realiza uma requisição HTTP com re-tentativas automáticas em caso de erro de conexão ou timeout"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            resposta = requests.get(url, params=params, headers=headers, timeout=timeout)
            resposta.raise_for_status()
            return resposta
        except requests.RequestException as e:
            if tentativa < max_tentativas:
                tempo_espera = tentativa*3
                print(f"⚠️ Instabilidade (tentativa {tentativa}/{max_tentativas}) na URL... Aguardando {tempo_espera}s: {e}")
                time.sleep(tempo_espera)
            else:
                raise e

def coletar_reviews_gog(prod_id, produto_gog=None, detalhes_json=None):
    """
    Consulta o endpoint público de reviews da GOG.

    Registra quantidade e média mesmo quando a lista individual não pode
    ser totalmente recuperada.

    Só calcula a porcentagem positiva quando todas as avaliações
    contabilizadas foram coletadas e possuem nota.

    Considera positiva nota >= 4 estrelas.
    """

    url = f"https://reviews.gog.com/v1/products/{prod_id}/reviews"

    limite = 60
    max_paginas = 1000

    params_base = {
        "order": "desc:votes",
        "limit": limite
        # Não aplicamos filtro de idioma para não restringir a população.
    }

    resumo_api = {}
    reviews_por_id = {}
    paginas_total = None
    total_reviews = None
    media = None
    coleta_completa = False
    erro_consulta = None

    try:
        resposta = fazer_requisicao_com_retry(url, params={**params_base, "page":1}, headers=headers, timeout=20)

        primeira_pagina = resposta.json()

        if not isinstance(primeira_pagina, dict):
            raise ValueError(
                "Resposta inesperada da API de avaliações."
            )

        resumo_api = primeira_pagina

        total_reviews = converter_inteiro(
            primeira_pagina.get("reviewCount")
        )

        paginas_total = converter_inteiro(
            primeira_pagina.get("pages")
        )

        media = normalizar_nota_media(
            primeira_pagina.get("overallAvgRating")
        )

        if media is None:
            media = normalizar_nota_media(
                primeira_pagina.get("filteredAvgRating")
            )

        paginas_a_consultar = paginas_total

        if paginas_a_consultar is None and total_reviews is not None:
            paginas_a_consultar = math.ceil(
                total_reviews / limite
            )

        if paginas_a_consultar is None:
            # Sem total e sem número de páginas, não presumimos que
            # a primeira página represente o conjunto completo.
            paginas_a_consultar = 1

        if paginas_a_consultar > max_paginas:
            print(
                f"   ⚠️ GOG informou {paginas_a_consultar} páginas; "
                f"limite de segurança: {max_paginas}."
            )

        paginas_limite = min(
            paginas_a_consultar,
            max_paginas
        )

        paginas_ok = True
        ultima_pagina_tinha_menos_que_limite = False

        for pagina in range(1, paginas_limite + 1):

            if pagina == 1:
                dados_pagina = primeira_pagina

            else:
                try:
                    resp_pagina = fazer_requisicao_com_retry(url, params={**params_base, "page":pagina}, headers=headers, timeout=20)
                    dados_pagina = resp_pagina.json()

                except (requests.RequestException, ValueError) as erro:
                    print(
                        f"   ⚠️ Falha na página {pagina} "
                        f"de reviews da GOG: {erro}"
                    )

                    paginas_ok = False
                    break

                time.sleep(0.15)

            reviews = localizar_lista_reviews(dados_pagina)

            if not reviews:
                ultima_pagina_tinha_menos_que_limite = True

                if total_reviews == 0:
                    break

                # Se a API declarou mais páginas, uma página vazia
                # antes do final significa que a coleta não foi completa.
                if pagina < paginas_limite:
                    paginas_ok = False

                break

            ultima_pagina_tinha_menos_que_limite = (
                len(reviews) < limite
            )

            novos_na_pagina = 0

            for review in reviews:
                chave = obter_chave_review(review)

                if chave is None or chave in reviews_por_id:
                    continue

                reviews_por_id[chave] = review
                novos_na_pagina += 1

            # Uma página repetida pode indicar que o parâmetro de
            # paginação não foi reconhecido pelo endpoint.
            if pagina > 1 and novos_na_pagina == 0:
                paginas_ok = False
                break

        if paginas_total is not None:
            todas_paginas_consultadas = (
                paginas_ok and paginas_total <= max_paginas
            )

        elif total_reviews is not None:
            todas_paginas_consultadas = (
                paginas_ok
                and len(reviews_por_id) >= total_reviews
            )

        else:
            # Sem metadados de paginação, só consideramos completa
            # quando a última página tem menos itens que o limite.
            todas_paginas_consultadas = (
                paginas_ok
                and ultima_pagina_tinha_menos_que_limite
            )

        reviews_coletadas = list(reviews_por_id.values())

        notas = [
            nota
            for nota in (
                extrair_nota_individual(review)
                for review in reviews_coletadas
            )
            if nota is not None
        ]

        # Se a API não informar a contagem agregada, usa a quantidade
        # efetivamente recuperada, desde que a paginação tenha terminado.
        if total_reviews is None and todas_paginas_consultadas:
            total_reviews = len(reviews_coletadas)

        coleta_completa = (
            todas_paginas_consultadas
            and total_reviews is not None
            and len(reviews_coletadas) == total_reviews
            and len(notas) == len(reviews_coletadas)
        )

        positivas = (
            sum(1 for nota in notas if nota >= 4)
            if coleta_completa
            else None
        )

        percentual_positivo = (
            round((positivas / total_reviews) * 100, 2)
            if (
                coleta_completa
                and total_reviews
                and positivas is not None
            )
            else None
        )

    except (
        requests.RequestException,
        ValueError,
        TypeError
    ) as erro:

        erro_consulta = str(erro)

        reviews_coletadas = []
        notas = []
        positivas = None
        percentual_positivo = None
        coleta_completa = False

    # Se o endpoint de reviews não forneceu média, tenta a propriedade
    # rating do endpoint de detalhes da GOG (escala de 0 a 500).
    if media is None:

        candidatos_media = []

        if isinstance(detalhes_json, dict):
            candidatos_media.append(
                detalhes_json.get("rating")
            )

        if isinstance(produto_gog, dict):
            candidatos_media.append(
                produto_gog.get("rating")
            )

        for candidato in candidatos_media:
            media = normalizar_nota_media(candidato)

            if media is not None:
                break

    # Só usa zero como quantidade quando a API explicitamente informou zero.
    status = "ok"

    if total_reviews == 0:
        status = "sem_avaliacoes"

    elif coleta_completa:
        status = "calculado_com_todas_as_reviews"

    elif media is not None or total_reviews is not None:
        status = "dados_agregados_disponiveis_percentual_indisponivel"

    else:
        status = "nota_media_indisponivel"

    resultado = {
        "review_count": total_reviews,
        "positive_review_count": positivas,
        "positive_percentage": percentual_positivo,
        "average_rating": media,
        "positive_threshold_stars": 3,
        "reviews_collected": len(reviews_por_id),
        "reviews_with_rating": len(notas),
        "all_reviews_collected": coleta_completa,
        "source": "GOG reviews API",
        "status": status
    }

    if erro_consulta:
        resultado["error"] = erro_consulta

    print(
        "   ↳ Reviews GOG: "
        f"total={resultado['review_count']}, "
        f"positivas={resultado['positive_review_count']}, "
        f"percentual={resultado['positive_percentage']}, "
        f"média={resultado['average_rating']}, "
        f"status={resultado['status']}"
    )

    return resultado


# ---------------------------------------------------------
# COLETA DOS JOGOS NA GOG
# ---------------------------------------------------------

for indice, nome in enumerate(sorted(nomes_jogos), start=1):

    print(
        f"\n[{indice}/{len(nomes_jogos)}] "
        f"pesquisando na GOG: {nome}"
    )

    produto_gog = buscar_jogo_gog(nome)

    if produto_gog:

        prod_id = produto_gog.get("id")
        titulo_gog = produto_gog.get("title")

        detalhes_url = (
            f"https://api.gog.com/products/{prod_id}?locale=en_US"
        )

        try:
            resp_detalhes = requests.get(
                detalhes_url,
                headers=headers,
                timeout=10
            )

            if resp_detalhes.status_code == 200:
                detalhes_json = resp_detalhes.json()

                detalhes_json["price"] = produto_gog.get("price")

            else:
                detalhes_json = produto_gog

        except Exception:
            detalhes_json = produto_gog

        detalhes_json["genres"] = (
            detalhes_json.get("genres")
            or produto_gog.get("genres", [])
        )

        detalhes_json["tags"] = (
            detalhes_json.get("tags")
            or produto_gog.get("tags", [])
        )

        # Consulta total de avaliações, percentual positivo e nota média.
        detalhes_json["gog_reviews"] = coletar_reviews_gog(
            prod_id=prod_id,
            produto_gog=produto_gog,
            detalhes_json=detalhes_json
        )

        detalhes_json["genres"] = traduzir_estrutura(detalhes_json.get("genres", []))
        detalhes_json["tages"] = traduzir_estrutura(detalhes_json.get("tags", []))

        caminho_saida = f"dados/raw/gog_{prod_id}.json"

        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(
                detalhes_json,
                f,
                ensure_ascii=False,
                indent=4
            )

        print(
            f"   💾 Salvo com sucesso: "
            f"gog_{prod_id}.json ({titulo_gog})"
        )

    else:
        print("   ❌ Jogo não encontrado na GOG.")

    time.sleep(0.5)
