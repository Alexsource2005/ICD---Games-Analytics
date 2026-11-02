"""Consulta a nota media de jogadores da Epic Games Store via RatingsPolls.

Uso:
    from Ratings_Polls_Epic import obter_ratings_polls

    ratings = obter_ratings_polls(
        jogo_encontrado=jogo_encontrado,
        detalhes=detalhes,
        slug_principal=slug,
        user_agent=headers.get("User-Agent"),
    )

A consulta prioriza o campo `namespace` do resultado de catálogo como
sandboxId, conforme o fluxo usado pela API GraphQL da Epic. Em seguida,
tenta resolver o sandboxId por StorePageMapping, usando pageSlug.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse

import requests

GRAPHQL_ENDPOINT = "https://store.epicgames.com/graphql"
LOCALE_RATINGS = "US"

QUERY_MAPPING = """
query getMappingByPageSlug($pageSlug: String!) {
    StorePageMapping {
        mapping(pageSlug: $pageSlug) {
            pageSlug
            pageType
            sandboxId
        }
    }
}
"""

QUERY_RATING = """
query getProductResult($sandboxId: String!, $locale: String!) {
    RatingsPolls {
        getProductResult(sandboxId: $sandboxId, locale: $locale) {
            averageRating
        }
    }
}
"""


def _normalizar_page_slug(valor: Any) -> str | None:
    """Normaliza slug ou URL de produto, removendo /p/ e parâmetros."""
    if not isinstance(valor, str) or not valor.strip():
        return None

    valor = unquote(valor.strip())

    if valor.startswith(("http://", "https://")):
        caminho = urlparse(valor).path
        if "/p/" in caminho:
            valor = caminho.split("/p/", 1)[1]
        else:
            valor = caminho.strip("/")

    valor = valor.split("?", 1)[0].split("#", 1)[0].strip("/")

    if valor.startswith("p/"):
        valor = valor[2:]

    return valor or None


def _adicionar_slug(lista: list[str], valor: Any) -> None:
    slug = _normalizar_page_slug(valor)
    if not slug:
        return

    sem_home = slug[:-5].rstrip("/") if slug.endswith("/home") else slug
    for candidato in (sem_home, slug):
        if candidato and candidato not in lista:
            lista.append(candidato)


def _coletar_page_slugs(
    jogo_encontrado: dict[str, Any] | None,
    detalhes: dict[str, Any] | None,
    slug_principal: str | None,
) -> list[str]:
    """Prioriza pageSlug dos mappings; depois productSlug e urlSlug."""
    fontes = [x for x in (jogo_encontrado, detalhes) if isinstance(x, dict)]
    page_slugs: list[str] = []
    outros_slugs: list[str] = []

    def percorrer_mapeamentos(valor: Any) -> None:
        if isinstance(valor, list):
            for item in valor:
                percorrer_mapeamentos(item)
        elif isinstance(valor, dict):
            if valor.get("pageSlug"):
                _adicionar_slug(page_slugs, valor["pageSlug"])
            for chave in ("mappings", "catalogNs", "offerMappings", "pages"):
                if chave in valor:
                    percorrer_mapeamentos(valor[chave])

    for fonte in fontes:
        for chave in ("mappings", "catalogNs", "offerMappings", "pages"):
            if chave in fonte:
                percorrer_mapeamentos(fonte[chave])

    for fonte in fontes:
        _adicionar_slug(outros_slugs, fonte.get("productSlug"))
        _adicionar_slug(outros_slugs, fonte.get("urlSlug"))

    _adicionar_slug(outros_slugs, slug_principal)

    # IDs UUID não são pageSlug. Evita consultas de mapping com namespace/IDs.
    def parece_uuid(valor: str) -> bool:
        compacto = valor.replace("-", "")
        return len(compacto) == 32 and all(c in "0123456789abcdefABCDEF" for c in compacto)

    page_slugs = [s for s in page_slugs if not parece_uuid(s)]
    outros_slugs = [s for s in outros_slugs if not parece_uuid(s)]

    return page_slugs + [s for s in outros_slugs if s not in page_slugs]


def _coletar_sandbox_ids(
    jogo_encontrado: dict[str, Any] | None,
    detalhes: dict[str, Any] | None,
) -> list[str]:
    """Coleta identificadores que a resposta da Epic nomeia como namespace/sandboxId."""
    fontes = [x for x in (jogo_encontrado, detalhes) if isinstance(x, dict)]
    encontrados: list[str] = []

    def adicionar(valor: Any) -> None:
        if isinstance(valor, str) and valor.strip():
            valor = valor.strip()
            if valor not in encontrados:
                encontrados.append(valor)

    for fonte in fontes:
        # O namespace da oferta é utilizado como sandboxId na consulta RatingsPolls.
        adicionar(fonte.get("namespace"))
        adicionar(fonte.get("sandboxId"))

        # Algumas respostas incluem os identificadores dentro de pages/items.
        for chave in ("pages", "items"):
            itens = fonte.get(chave)
            if isinstance(itens, list):
                for item in itens:
                    if isinstance(item, dict):
                        adicionar(item.get("sandboxId"))
                        # Namespace de item é fallback; o namespace raiz vem primeiro.
                        adicionar(item.get("namespace"))

        for chave in ("mappings", "offerMappings"):
            itens = fonte.get(chave)
            if isinstance(itens, list):
                for item in itens:
                    if isinstance(item, dict):
                        adicionar(item.get("sandboxId"))

        catalog_ns = fonte.get("catalogNs")
        if isinstance(catalog_ns, dict):
            adicionar(catalog_ns.get("sandboxId"))
            adicionar(catalog_ns.get("namespace"))
            mappings = catalog_ns.get("mappings", [])
            if isinstance(mappings, list):
                for item in mappings:
                    if isinstance(item, dict):
                        adicionar(item.get("sandboxId"))

    return encontrados


def _graphql(
    query: str,
    variables: dict[str, Any],
    user_agent: str | None = None,
) -> dict[str, Any]:
    cabecalhos = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://store.epicgames.com",
        "Referer": "https://store.epicgames.com/",
        "User-Agent": user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    resposta = requests.post(
        GRAPHQL_ENDPOINT,
        json={"query": query, "variables": variables},
        headers=cabecalhos,
        timeout=20,
    )
    resposta.raise_for_status()

    payload = resposta.json()
    if payload.get("errors"):
        mensagens = "; ".join(
            str(erro.get("message", erro)) for erro in payload["errors"]
        )
        raise RuntimeError(f"Erro GraphQL: {mensagens}")

    return payload.get("data") or {}


def _obter_nota_media(
    sandbox_id: str,
    user_agent: str | None = None,
) -> float | None:
    dados = _graphql(
        QUERY_RATING,
        {"sandboxId": sandbox_id, "locale": LOCALE_RATINGS},
        user_agent=user_agent,
    )

    ratings = dados.get("RatingsPolls", {})
    resultado = ratings.get("getProductResult") if isinstance(ratings, dict) else None
    if not isinstance(resultado, dict):
        return None

    nota = resultado.get("averageRating")
    if nota is None:
        return None

    try:
        nota = float(nota)
    except (TypeError, ValueError):
        return None

    if not 0 < nota <= 5:
        return None

    return round(nota, 2)


def _obter_sandbox_id_por_slug(
    page_slug: str,
    user_agent: str | None = None,
) -> str | None:
    dados = _graphql(
        QUERY_MAPPING,
        {"pageSlug": page_slug},
        user_agent=user_agent,
    )

    store_mapping = dados.get("StorePageMapping", {})
    mapping = store_mapping.get("mapping") if isinstance(store_mapping, dict) else None
    if isinstance(mapping, dict) and mapping.get("sandboxId"):
        return str(mapping["sandboxId"])
    return None


def obter_ratings_polls(
    jogo_encontrado: dict[str, Any] | None,
    detalhes: dict[str, Any] | None,
    slug_principal: str | None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Retorna a nota média RatingsPolls e metadados de auditoria."""
    base = {
        "average_rating": None,
        "rating_scale": 5,
        "rating_count": None,
        "sandbox_id": None,
        "page_slug": None,
        "source": "Epic Games Store RatingsPolls",
    }

    ultimo_erro: str | None = None
    sandbox_ids = _coletar_sandbox_ids(jogo_encontrado, detalhes)
    slugs = _coletar_page_slugs(jogo_encontrado, detalhes, slug_principal)
    ids_testados: list[str] = []

    # 1. Primeiro testa namespace/sandboxId informado diretamente pelo catálogo.
    for sandbox_id in sandbox_ids:
        ids_testados.append(sandbox_id)
        try:
            nota = _obter_nota_media(sandbox_id, user_agent=user_agent)
            if nota is not None:
                return {
                    **base,
                    "average_rating": nota,
                    "sandbox_id": sandbox_id,
                    "status": "ok",
                    "identifier_source": "namespace_or_sandboxId",
                }
        except (requests.RequestException, ValueError, RuntimeError) as erro:
            ultimo_erro = str(erro)

    # 2. Se necessário, resolve o sandboxId por StorePageMapping.
    for page_slug in slugs:
        try:
            sandbox_id = _obter_sandbox_id_por_slug(
                page_slug,
                user_agent=user_agent,
            )
            if not sandbox_id:
                continue

            if sandbox_id not in ids_testados:
                ids_testados.append(sandbox_id)
                nota = _obter_nota_media(sandbox_id, user_agent=user_agent)
            else:
                # Evita repetir a mesma consulta caso o namespace já tenha sido testado.
                nota = _obter_nota_media(sandbox_id, user_agent=user_agent)

            if nota is not None:
                return {
                    **base,
                    "average_rating": nota,
                    "sandbox_id": sandbox_id,
                    "page_slug": page_slug,
                    "status": "ok",
                    "identifier_source": "StorePageMapping",
                }

            return {
                **base,
                "sandbox_id": sandbox_id,
                "page_slug": page_slug,
                "status": "nota_nao_disponivel",
            }

        except (requests.RequestException, ValueError, RuntimeError) as erro:
            ultimo_erro = str(erro)

    if ids_testados:
        resultado = {
            **base,
            "sandbox_id": ids_testados[0],
            "status": "nota_nao_disponivel" if not ultimo_erro else "erro_consulta",
        }
    else:
        resultado = {
            **base,
            "status": "sandbox_id_nao_encontrado",
        }

    if ultimo_erro:
        resultado["error"] = ultimo_erro

    return resultado
