  "# ICD---Games-Analytics" 
  Integrantes:
    Alessandra Cardoso Fernandes (Alexander)

  FASE 1:

  Tema do projeto: 
    Dados sobre o mercado de jogos digital com recorte específico para o PC (Steam, Epic Games e GoG Galaxy)

  Abordagem de coleta de dados:
    APIs: SteamWorks WEB API, SteamSpy API, GraphQL (epic games/JSON), Datasets da comunidade(derivados que forem encontrados no github), API REST do catalogo           GOG
    Web scrapping: especificamente na página https://www.nerdmaldito.com/2020/05/lista-com-todos-os-jogos-dados-pela.html para buscar as datas em que jogos                       ficaram gratuitos na Epic Games desde o final de 2018.

  FASE 2:

  Descrição do conjunto de dados: 
  O conjunto de dados reunidos na pasta dados/raw engloba as informações comparativas de jogos eletrônicos para PC vendidas nas plataformas de distribuição Steam, Epic e GOG. Cada JSON possui o prefixo que identifica de qual loja os metadados foram tirados, logo "gog_", "epic_" e "steam_", seguidos por seus titulos (Epic) ou seus IDs nas respectivas lojas (Steam, GOG). 
  O conjunto de dados processados integra as métricas comerciais (preço em BRL), data de lançamento padronizada, classificação por genêros primário e secundário, disponibilidade multiplataforma (com algumas especificidades), estimativa de donos e o volume de avaliações dos usuários.
  Além disso, o dataset tambem registra o histórico de ofertas gratuitos oferecidos pela Epic Games de forma padronizada (dd/mm/aaaa - dd/mm/aaaa). O objetivo desse dataset é oferecer uma visão unificada do mercado de jogos digitais nas plataformas mais famosas.

  Descrição do processo de coleta de dados:
  Steam: Os metadados foram coletados via chamadas à API pública da Steam Store (appdetails e appreviews) para coletar as informações básicas como preço e para coletar a quantidade total de reviews e a quantidade de reviews positivas para o cálculo da porcentagem de reviews positivas em relação ao total. Além disso, tambem foi utilizada a API não oficial SteamSpy para completar a classificação de genêro de alguns jogos, coletando as tags postadas pela própria comunidade. Além disso, importante ressaltar o cálculo para estimar a quantidade de donos que um jogo tem baseado na quantidade total de reviews e um fator médio.
  
  Epic: A coleta utilizou a API GRAPHQL/REST da loja (epicstore_api) aplicando busca por Fuzzy Matching com algoritmos de similaridade textual (difflib.SequenceMatcher) e filtragem estrita por tipo de oferta (evitar DLCs, bundles, etc). Foram capturados preços base, tags categorizadas (seus IDs), e suas notas médias da funcionalidade interna Ratings & Polls.
  A listagem dos intervalos de tempo em que um jogo foi ofertado gratuitamente na Epic Store foi coletado via Web Scrapping (Beautiful Soup) de um registro público mantido pela comunidade (https://www.nerdmaldito.com/2020/05/lista-com-todos-os-jogos-dados-pela.html) e padronizado em um formato dd/mm/aaaa - dd/mm/aaaa.

  GOG: A coleta dos metadados de preço, data de lançamento, tags categorizadas foram todas feitos via a API da plataforma. com os endpoints "catalog.gog.com/v1/catalog" para os metadados base e "reviews.gog.com/v1/products/{prod_id}/reviews" para coletar a quantidade total de reviews e determinar um parâmtro de quais avaliações seriam positivas (4 ou mais estrelas) e calcular a porcentagem de quantas reviews são positivas em relação ao total através dele.

  Descrição da estrutura da tabela:
| COLUNA | DESCRIÇÃO | EXEMPLO |
| :--- | :--- | :--- |
| **Jogo** | Nome do jogo como aparece na loja | "Batman Arkham Knight" |
| **Gênero primário** | Categoria principal do jogo (priorizando Steam) | "Ação" |
| **Gênero secundário** | Categoria secundária ou complementar | "Aventura" |
| **Data de lançamento** | Data oficial de lançamento padronizada (DD/MM/AAAA) | "23/06/2015" |
| **Preço Steam** | Preço em BRL na Steam | "R$89,99" |
| **Preço Epic** | Preço em BRL na Epic | "R$49,99" |
| **Preço GOG** | Preço em BRL na GOG | "R$49,99" |
| **Data Aquisição Gratuita Epic** | Intervalo de datas em que o jogo esteve gratuito | "19/09/2019 - 26/09/2019" |
| **Estimativa donos Steam** | Faixa estimada do número de proprietários na Steam | "3,376,080 - 5,626,800" |
| **Qtd Reviews Steam** | Quantidade total de avaliações de usuários registradas na Steam | "76009" |
| **% positivas Steam** | Porcentagem de avaliações positivas em relação ao todo | "87.995" |
| **Nota média Epic** | Nota média do jogo no sistema Rating & Polls da Epic | "4.82" |
| **Qtd Reviews GOG** | Quantidade total de avaliações de usuários registradas na GOG | "225" |
| **% positivas GOG** | Porcentagem de avaliações positivas em relação ao todo. Com estrelas >= 4. | "84.0" |
| **Nota Média GOG** | Nota média do jogo no sistema de estrelas da GOG | "4.4" |
| **Disponível na Steam** | Indica se o jogo possui página de venda na Steam | "sim" |
| **Disponível na Epic** | Indica se o jogo possui página de venda na Epic | "sim" |
| **Disponível na GOG** | Indica se o jogo possui página de venda na GOG | "sim" |
