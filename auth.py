import datetime, requests, json, base64, yaml
from datetime import timedelta

URL = 'https://api.merchants.zalando.com'

try:
    with open("pw.yaml", "r") as f:
        y = yaml.safe_load(f)
        CLIENT_ID = y['ZALANDO_ID']
        CLIENT_SECRET = y['ZALANDO_SECRET']
except Exception:
    print("Paste data in pw.yaml. Zalando login failed")

def creat_acces_token():

    def gen_token(id, secret):
        key = f'{id}:{secret}'
        key_bytes = key.encode('ascii')
        base64_key = base64.b64encode(key_bytes).decode("utf-8")

        data = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'grant_type': 'client_credentials',
            'scope': 'access_token_only',
            }
        headers={'Authorization': f'Basic {base64_key}'}

        print("Generowanie tokenu...")
        r = requests.post(f'{URL}/auth/token', data = data, headers = headers)
        if r:
            print("Poprawnie wygenerowano nowy token")
        json_token = json.loads(r.text)
        return json_token

    def auth_me(token):
        headers={'Authorization': f'Bearer {token}'}
        r = requests.get(f'{URL}/auth/me', headers = headers)
        json_data = json.loads(r.text)
        if r:
            print("Autoryzacja uzyskana")
        return json_data['bpids']
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
    time_to_nex_gen = now+timedelta(0, 7000)
    check_if_file_exist = False

    while not check_if_file_exist:
        try:
            with open("token.txt") as f: 
                check_if_file_exist = True
                lines = str(f.readline())
                exp_time = json.loads(lines)['exp_in']
                exp_time = datetime.datetime.strptime(exp_time, "%Y-%m-%d %H:%M:%S")
                if (now>=exp_time):
                    token_data = gen_token(CLIENT_ID, CLIENT_SECRET)
                    token = token_data['access_token']
                
                    with open("token.txt", "w") as f: 
                        data = {"token": token,
                                "exp_in": str(time_to_nex_gen),
                                "merchant_id": json.loads(lines)['merchant_id']}
                        data = json.dumps(data)
                        f.writelines(data)

                    return token, json.loads(lines)['merchant_id']
        except:
            with open("token.txt", "w+") as f:
                token_data = gen_token(CLIENT_ID, CLIENT_SECRET)
                token = token_data['access_token']
                merchant_id = auth_me(token)[0]
                print(merchant_id)
                data = {"token": token,
                        "exp_in": str(time_to_nex_gen),
                        "merchant_id": merchant_id}
                data = json.dumps(data)
                f.writelines(data)
    
    token = json.loads(lines)['token']
    merchant_id = json.loads(lines)['merchant_id']

    return token, merchant_id

    