import requests
from auth import creat_acces_token

# zalando api URL
URL = "https://api.merchants.zalando.com"

class ZalandoRequest:
    def __init__(self):
        self.token, self.merchant_id = creat_acces_token()

    # generate authorization and place request with given parameters
    # possible methods: "GET", "POST", "PATCH"
    # path = endpoint in zalando API e.g. /orders
    # body = e.g params in POST/PATCH method or if GET method additional params in url
    # return json response
    def place_request(self, method, path="", body=""):
        link = f"{URL}{path}"
        if "{merchant_id}" in link:
            link = link.replace("{merchant_id}", f"{creat_acces_token()[1]}")  # if {merchant_id} in text replace with merchant id

        headers = {
            'Authorization': f'Bearer {creat_acces_token()[0]}',
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'}

        if body and method == "GET":
            r = requests.get(link, headers=headers, params=body)

        if not body and method == "GET":
            r = requests.get(link, headers=headers)

        if method == "POST":
            headers = {'Authorization': f'Bearer {creat_acces_token()[0]}',
                       'Content-Type': 'application/json'}
            r = requests.post(link, json=body, headers=headers)

        if method == "PATCH":
           headers = {
            'Authorization': f'Bearer {creat_acces_token()[0]}',
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'}
           r = requests.patch(link, json=body, headers=headers)
           return r

        return r.json()