import json
import requests

url = (
    "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
)

params = {
    "input_json": json.dumps({
        "appid": 400,
        "filter": 0,
        "language":"all",
        "review_type": 1,
        "num_per_page": 1
    })
}

try:
    res = requests.get(url, params=params, timeout=20)

    print("Status HTTP:", res.status_code)
    print("Content-Type:", res.headers.get("Content-Type"))
    res.raise_for_status()

    dados = res.json()
    print(json.dumps(dados, indent=2, ensure_ascii=False)[:5000])

except (requests.RequestException, ValueError) as e:
    print("Erro ao consultar avaliações", e)
    if "res" in locals():
        print("Resposta recebida:", res.text[:1000])