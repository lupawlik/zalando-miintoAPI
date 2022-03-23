import requests, json, datetime, hmac, hashlib, urllib, random, yaml
from hashlib import sha256

URL = "https://api-order.miinto.net"
HOST = "api-order.miinto.net"

# loads secrets from file
try:
    with open("pw.yaml", "r") as f:
        y = yaml.safe_load(f)
        CLIENT_ID = y['MIINTO_ID']
        CLIENT_SECRET = y['MIINTO_SECRET']
except Exception:
    print("Paste data in pw.yaml. Miinto login failed")

# creats file with miinto token and creats file with countries available on miinto
def create_mcc():
    data = {
        "identifier": CLIENT_ID,
        "secret": CLIENT_SECRET
    }
    headers = {"Content-Type": "application/json", }
    try:
        r = requests.post(f"https://api-auth.miinto.net/channels", headers=headers, data=json.dumps(data))
        r.raise_for_status()
        data = r.json()["data"]
        with open('miinto/mcc.txt', 'w+') as f:
            f.write(str(data))
        print("MCC generated miinto/mcc.txt")

        countries_dict = {}
        with open('miinto/countries.txt', 'w+') as f:
            list_of_countriest = list(data['privileges'].keys())
            del list_of_countriest[0]

            # saves keys with countries codes to dict
            for i in list_of_countriest:
                countries_dict[f"{i}"] = list(data['privileges'][i]['ShopAdmin'].keys())[0]
            f.write(str(countries_dict))
        print("File with countries generated miinto/countries.txt")
        return data

    except requests.exceptions.HTTPError as err:
        return err

# class used to place request Miinto API
class MiintoRequest:
    def __init__(self):
        self.identifier = CLIENT_ID
        self.secret = CLIENT_SECRET

    # return timestamp
    def _timestamp(self):
        return str(datetime.datetime.now().timestamp()).split(".")[0]

    def _creat_sign(self, method, path, timestamp, seed, body):
        method = method.upper()
        # check if MCC file is created, if not - create and laod data
        try:
            with open("miinto/mcc.txt") as f:
                string_data = f.readlines()[0].replace("\'", "\"")
                json_data = json.loads(string_data)
        except:
            create_mcc()
            with open("miinto/mcc.txt") as f:
                string_data = f.readlines()[0].replace("\'", "\"")
                json_data = json.loads(string_data)

        self.id = json_data['id']
        self.token = json_data['token']
        self.accessorId = json_data['data']['accessorId']
        # creating sign, documentation https://miintoauthserviceapi.docs.apiary.io/#introduction/signature-generation
        if method == "GET":
            first_step = f"{method}\n{HOST}\n{path}\n{body}"
            resourceSig = sha256(first_step.encode('utf-8')).hexdigest()

            auth_type = "MNT-HMAC-SHA256-1-0"
            second_step = f"{self.id}\n{timestamp}\n{seed}\n{auth_type}"
            headerSig = sha256(second_step.encode('utf-8')).hexdigest()

            third_step = ""
            payloadSig = sha256(third_step.encode('utf-8')).hexdigest()

            message = f"{resourceSig}\n{headerSig}\n{payloadSig}"
            signature = hmac.new(bytes(self.token, 'utf-8'), msg=bytes(message, 'utf-8'), digestmod=hashlib.sha256).hexdigest()
            return signature

    # send request to miinto api. Possible method values: "GET"
    def place_request(self, method, path="", body=""):
        timestamp = self._timestamp()
        seed = random.randint(0, 100)
        link = f"{URL}{path}"
        if body and method == "GET":
            url_params = urllib.parse.urlencode(body)  # if method get parse parameters from body to url
            link = f"{URL}{path}?{url_params}"
            sign = self._creat_sign(method, path, timestamp, seed, url_params)

        if not body and method == "GET":
            sign = self._creat_sign(method, path, timestamp, seed, body)  # parse parameters directly in body
        # creat headers for miinto api
        headers = {
            'Miinto-Api-Auth-Seed': f"{seed}",
            'Miinto-Api-Auth-Signature': f"{sign}",
            'Miinto-Api-Auth-ID': f"{self.id}",
            'Miinto-Api-Auth-Timestamp': f"{timestamp}",
            'Miinto-Api-Auth-Type': 'MNT-HMAC-SHA256-1-0',
            'Miinto-Api-Control-Flavour': 'Miinto-Generic',
            'Miinto-Api-Control-Version': '2.6',
            'Content-Type': 'application/json',
            }
        r = requests.get(link, headers=headers)
        # print(headers)
        # print(link)
        # print(r.text)
        return r.json()