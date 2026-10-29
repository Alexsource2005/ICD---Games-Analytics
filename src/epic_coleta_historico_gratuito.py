import json
import os
import re
from bs4 import BeautifulSoup
from epicstore_api import EpicGamesStoreAPI
import requests

api = EpicGamesStoreAPI(country="BR", locale="pt-BR")

os.makedirs("dados/raw", exist_ok=True)

url = "https://www.nerdmaldito.com/2020/05/lista-com-todos-os-jogos-dados-pela.html"
headers = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; x64) AppleWebKit/537.36")
}

resposta = requests.get(url, headers=headers)
blocos_texto = []

if resposta.status_code == 200:
  soup = BeautifulSoup(resposta.text, "html.parser")
  post_body = soup.find("div", class_="post-body") or soup.find(
      "div", class_="entry-content"
  )

  if post_body:
    for elemento in post_body.find_all(["p", "li"]):
      texto = elemento.get_text().strip()
      if len(texto) > 3 and ("-" in texto or "–" in texto or "(" in texto):
        blocos_texto.append(texto)
  print(f"✅ Extraídos {len(blocos_texto)} blocos de texto da página.")
else:
  print(f"❌ Erro ao aceder ao site. Status code: {resposta.status_code}")

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
    "dezembro": 12, "dez": 12, "december": 12, "dec": 12,
}

def padronizar_data_aquisicao(texto_data, ano_contexto="2020"):
   """Converte diferentes formatos de data para 'dd/mm/aaaa - dd/mm/aaaa'."""
   if not texto_data or not isinstance(texto_data, str):
      return None

   texto = texto_data.strip()
   if not texto or texto.lower() in ["desconhecida", "n/a", "none", "null"]:
      return None

   # Se já estiver exatamente no formato dd/mm/aaaa - dd/mm/aaaa
   if re.fullmatch(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}", texto):
      return re.sub(r"\s*-\s*", " - ", texto)

   texto_lower = texto.lower()

   # Busca anos explicitos na string
   anos_encontrados = re.findall(r"\b(20\d{2})\b", texto_lower)
   ano_base = anos_encontrados[0] if anos_encontrados else ano_contexto

   # 1. Duas datas completas dd/mm/aaaa
   datas_completas = re.findall(r"\b(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})\b", texto_lower)
   if len(datas_completas) == 2:
      d1, m1, y1 = datas_completas[0]
      d2, m2, y2 = datas_completas[1]
      y1 = f"20{y1}" if len(y1) == 2 else y1
      y2 = f"20{y2}" if len(y2) == 2 else y2
      return f"{int(d1):02d}/{int(m1):02d}/{y1} - {int(d2):02d}/{int(m2):02d}/{y2}"

   # 2. Intervalo numérico ("12 a 19/12/2019" ou "12/12 a 19/12/2019")
   m_range_num = re.search(r"\b(\d{1,2})(?:[\/\.-](\d{1,2}))?\s*(?:a|-|–|à|até)\s*(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})\b", texto_lower)
   if m_range_num:
        dia_ini, mes_ini, dia_fim, mes_fim, ano = m_range_num.groups()
        ano = f"20{ano}" if len(ano) == 2 else ano
        mes_ini = mes_ini if mes_ini else mes_fim

        # Correção da virada de ano (Dezembro para janeiro)
        ano_fim = str(int(ano) + 1) if mes_ini == 12 and mes_fim == 1 else ano
        return f"{int(dia_ini):02d}/{int(mes_ini):02d}/{ano} - {int(dia_fim):02d}/{int(mes_fim):02d}/{ano_fim}"

   # 3. Intervalo por extenso ("31 de dezembro de 2020 a 7 de janeiro de 2021")
   m_extenso_duplo = re.search(r"(\d{1,2})\s*(?:de\s*)?([a-zç]+)(?:\s*de\s*(20\d{2}))?\s*(?:a|-|–|à|até)\s*(\d{1,2})\s*(?:de\s*)?([a-zç]+)(?:\s*de\s*(20\d{2}))?", texto_lower)
   if m_extenso_duplo and m_extenso_duplo.group(2) in MESES and m_extenso_duplo.group(5) in MESES:
      d1 = int(m_extenso_duplo.group(1))
      m1 = MESES[m_extenso_duplo.group(2)]
      ano1 = m_extenso_duplo.group(3)

      d2 = int(m_extenso_duplo.group(4))
      m2 = MESES[m_extenso_duplo.group(5)]
      ano2 = m_extenso_duplo.group(6)

      ano2 = ano2 or ano1
      ano1 = ano1 or ano2
      if ano1 and ano2:
         return f"{d1:02d}/{m1:02d}/{ano1} - {d2:02d}/{m2:02d}/{ano2}"
   
   # "2 a 16 de maio de 2019" ou "2 - 16 de maio de 2019"   
   m_extenso_simples = re.search(r"(\d{1,2})\s*(?:a|-|–|à|até)\s*(\d{1,2})\s*de\s*([a-zç]+)(?:\s*de\s*(20\d{2}))?", texto_lower)
   if m_extenso_simples and m_extenso_simples.group(3) in MESES:
      d1 = int(m_extenso_simples.group(1))
      d2 = int(m_extenso_simples.group(2))
      m_num = MESES[m_extenso_simples.group(3)]
      ano_match = m_extenso_simples.group(4) or re.search(r"\b(20\d{2})\b", texto_lower)
      ano = ano_match.group(1) if isinstance(ano_match, re.Match) else ano_match
      if ano:
         return f"{d1:02d}/{m_num:02d}/{ano} - {d2:02d}/{m_num:02d}/{ano}"

   # "Maio 2-16, 2019" ou "Maio 2 - Maio 16, 2019"
   m_mes_primeiro = re.search(r"([a-zç]+)\s*(\d{1,2})\s*[-–aà]\s*(?:([a-zç]+)\s*)?(\d{1,2})[,\s]+(20\d{2})", texto_lower)
   if m_mes_primeiro and m_mes_primeiro.group(1) in MESES:
      m1 = MESES[m_mes_primeiro.group(1)]
      d1 = int(m_mes_primeiro.group(2))
      m2_str = m_mes_primeiro.group(3)
      m2 = MESES[m2_str] if m2_str and m2_str in MESES else m1
      d2 = int(m_mes_primeiro.group(4))
      ano = m_mes_primeiro.group(5)
      return f"{d1:02d}/{m1:02d}/{ano} - {d2:02d}/{m2:02d}/{ano}"

   # 4. Apenas 1 data
   if len(datas_completas) == 1:
      d, m, y = datas_completas[0]
      y = f"20{y}" if len(y) == 2 else y
      return f"{int(d):02d}/{int(m):02d}/{y} - {int(d):02d}/{int(m):02d}/{y}"

   return None

def limpar_nome_jogo(nome):
  """Remove símbolos de marca registrada e caracteres especiais"""
  nome_limpo = re.sub(r"[™®©]", "", nome)
  nome_limpo = re.sub(r"[^\w\s\-\']", "", nome_limpo)
  return nome_limpo.strip()

nomes_jogos_epic = []
for bloco in blocos_texto:
  if re.search(r"repetido", bloco, re.IGNORECASE):
    continue
  
  # Verifica se é uma oferta GMG
  tem_gmg = bool(re.search(r"\bgmg\b", bloco, re.IGNORECASE))
  
  # Remove a numeração inicial do item da lista (ex: "110. Jogo X" vira "Jogo X")
  bloco_sem_numero = re.sub(r"^\d+[\.\-\s]+", "", bloco).strip()

  partes = re.split(r"[-–\(]", bloco_sem_numero, maxsplit=1)
  if partes:
    nome_candidato = limpar_nome_jogo(partes[0])

    if tem_gmg:
        data_gratis = None
    else:
       raw_data = partes[1].replace(")", "").strip() if len(partes) > 1 else ""
       data_gratis = padronizar_data_aquisicao(raw_data)

    # Filtros rigorosos para evitar números isolados ou palavras inúteis
    if (
        len(nome_candidato) > 2
        and not nome_candidato.isdigit()  # Ignora se for apenas um número
        and nome_candidato.lower()
        not in ["dlc", "dev", "jogo", "jogos", "gratis"]
        and nome_candidato not in nomes_jogos_epic
        and not nome_candidato.lower().startswith("http")
    ):
      if not any(j["nome"] == nome_candidato for j in nomes_jogos_epic):
         nomes_jogos_epic.append({"nome": nome_candidato, "data_gratis": data_gratis})

print(
    f"🔍 Identificados {len(nomes_jogos_epic)} jogos limpos para buscar na Epic"
    " Games."
)

# Loop de bisca e download dos metadados na Epic Games Store
for indice, item in enumerate(nomes_jogos_epic, start=1):
    nome = item["nome"]
    data_gratis = item["data_gratis"]

    print(f"\n[{indice}/{len(nomes_jogos_epic)}] Pesquisando na Epic: {nome} (Data: {data_gratis})")

    try:
        resultados = api.fetch_store_games(keywords=nome)
        elements = (
            resultados.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        )

        if not elements and ("-" in nome or ":" in nome):
            nome_curto = re.split(r"[:/-]", nome)[0].strip()
            if len(nome_curto) > 3:
                resultados = api.fetch_store_games(keywords=nome_curto)
                elements = (
                    resultados.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
                )

        jogo_encontrado = None
        if elements:
            palavras_originais = set(nome.lower().split())
            nums_orig = re.findall(r"\d+", nome)

            for produto in elements[:5]:
                titulo_prod = produto.get("title", "").lower()
                palavras_prod = set(titulo_prod.split())
                nums_prod = re.findall(r"\d+", titulo_prod)

                if nums_orig != nums_prod:
                    continue

                intersecao = palavras_originais.intersection(palavras_prod)
                if len(intersecao) >= max(1, len(palavras_originais) - 1):
                    jogo_encontrado = produto
                    break

            if jogo_encontrado:
            # Tenta encontrar o slug no campo padrão ou em alternativas comuns da Epic
                slug = (
                    jogo_encontrado.get("productSlug")
                    or jogo_encontrado.get("urlSlug")
                    or next(
                        (
                            m.get("pageSlug")
                            for m in jogo_encontrado.get("mappings", [])
                            if m.get("pageSlug")
                        ),
                        None,
                    )
                )

                detalhes = None
                if slug:
                    try:
                        detalhes = api.get_product(slug)
                    except Exception:
                        detalhes = jogo_encontrado  # Se falhar o detalhe profundo, usa o básico
                else:
                    # Se nenhum slug foi encontrado, aproveita os dados básicos do catálogo
                    detalhes = jogo_encontrado
                    #Cria um slug temporário limpo baseado no título do jogo
                    titulo_base = jogo_encontrado.get("title", "jogo_desconhecido")
                    slug = re.sub(r"[^\w\s-]", "", titulo_base).strip().lower()
                    slug = re.sub(r"\s+", "-", slug)
                    print(
                        f"   ⚠️ Slug direto não encontrado, usando catálogo básico para"
                        f" '{titulo_base}'."
                    )

                if isinstance(detalhes, dict):
                   detalhes["data_aquisicao_gratis"] = data_gratis

                slug_limpo = slug.replace("/", "_")
                caminho_saida = f"dados/raw/epic_gratis_{slug_limpo}.json"

                with open(caminho_saida, "w", encoding="utf-8") as f:
                    json.dump(detalhes, f, ensure_ascii=False, indent=4)
                print(f"   💾 Salvo com sucesso: epic_gratis_{slug_limpo}.json")
            else:
                print(f"   ❌ Jogo não encontrado na Epic Games.")

    except Exception as e:
        print(f"Erro critico ao buscar '{nome}': {e}")


