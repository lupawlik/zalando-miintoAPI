import json, requests, time, os, sqlite3, yaml

from datetime import datetime, timedelta

from collections import Counter
from miinto.miinto_requests import create_mcc, MiintoRequest
from flask import request, redirect, url_for, render_template
from __main__ import app, db

# set main courses
coursers = {"EUR": 0.22, "DKK": 1.63, "PLN": 1, "SEK": 2.29}

from data_base_objects import MiintoOrdersDb

try:  # loads api key to currency converter from yaml
    with open("pw.yaml", "r") as f:
        y = yaml.safe_load(f)
        CURR_CONVERTER_KEY = y['CURRENCY_API']
except Exception:
    print("Paste data in pw.yaml. Currency login failed")

#  return exchange rate. example currency_converter(PLN, EUR) will return pln to euro ratio
def currency_converter(base_c, in_c):
    params = {
        'apikey': CURR_CONVERTER_KEY,
        'base_currency': base_c,
        }
    print(f"Downloading {base_c} to {in_c} course")
    try:
        r = requests.get(f'https://freecurrencyapi.net/api/v2/latest', params=params).json()
        return r["data"][in_c]
    except:
        print(f'Error sending request https://freecurrencyapi.net/api/v2/latest. It was impossible to dowload new courses\n Used {coursers[in_c]}')
        return coursers[in_c] # when is impossible to load new course, use these from dict


#  if file with countries exist load it. File is generated with create_mcc() function and returns list of available countries
def load_countries():
    try:
        with open("miinto/countries.txt") as f:
            string_data = f.readlines()[0] .replace("\'", "\"")
            json_data = json.loads(string_data)
    except:
        create_mcc()  # generate new token (mcc.txt) and list of countries(countries.txt)
        with open("miinto/countries.txt") as f:
            string_data = f.readlines()[0] .replace("\'", "\"")
            json_data = json.loads(string_data)
    return json_data

class MiintoApi(MiintoRequest):
    def get_order(self, country, id):
        return self.place_request("GET", f"/shops/{country}/orders/{id}")

    def get_order_list(self, country, status="accepted", offset="0", limit="50"):
        data = {
            "status[]": status,
            "limit": limit,
            "offset": offset,
            # "sort": "-createdAt",
            # "query": "text"
            }
        return self.place_request("GET", f"/shops/{country}/orders", data)

#wczytuje liste krajow

@app.route("/miinto/stats/", methods=['POST', 'GET'])
@app.route("/miinto/stats/<country>/", methods=['POST', 'GET'])
@app.route("/miinto/stats/<country>/<month>", methods=['POST', 'GET'])
def miint_stats(country="", month=""):
    countries = load_countries()
    labels = [co for co in countries]
    if not country or country == "all":
        if request.method == "POST":
            req = request.form
            month = req.get('month')
            all_months = req.get('all')
            if all_months:
                return redirect(url_for('miint_stats', country="all"))

            return redirect(url_for('miint_stats', country="all", month=month))
        order_number = []
        sum = 0
        conn = sqlite3.connect("mrktplc_data.db")
        c = conn.cursor()

        sum_of_orders = 0
        for co in countries:
            if not month:
                query = f"SELECT COUNT(*) FROM miinto_orders_db WHERE country = \"{co}\""
            else:
                year, month_q = month.split("-")
                query = f"SELECT COUNT(*) FROM miinto_orders_db WHERE country = \"{co}\" AND strftime('%m', date) = '{month_q}' AND strftime('%Y', date) = '{year}'"

            c.execute(query)
            temp_data = c.fetchall()
            order_number.append(temp_data[0][0])
            sum_of_orders += int(temp_data[0][0])
        print(f"Wczytano\t{sum}\tzamowien\tz\tSuma")

        if month:
            year, month = month.split("-")
            query = f"SELECT * FROM miinto_orders_db WHERE strftime('%m', date) = '{month}' AND strftime('%Y', date) = '{year}' ORDER BY date DESC"
            query2 = f"SELECT price, currency FROM miinto_orders_db WHERE strftime('%m', date) = '{month}' AND strftime('%Y', date) = '{year}' ORDER BY date DESC"

        elif not month:
            query = f"SELECT * FROM miinto_orders_db ORDER BY date DESC"
            query2 = f"SELECT price, currency FROM miinto_orders_db ORDER BY date DESC"
        c.execute(query)

        rows = list(c.fetchall())

        #wyliczanie sumy kwot w pln z kazdego kraju
        dates = []
        date_with_price = []

        pln_sum = 0
        for row in rows:
            single_date = row[2].split(" ")[0]

            dates.append(single_date)
            date_with_price.append((single_date, float(row[4])))
            pln_sum += float(row[4])

        t_1 = []
        tab_price = []
        coursor = -1
        for single_price in date_with_price:
            if single_price[0] not in t_1:
                t_1.append(single_price[0])
                tab_price.append(single_price[1])
                coursor += 1
            elif single_price[0] in t_1:
                tab_price[coursor] += single_price[1]


        for i in range(len(tab_price)):
            tab_price[i] = round(tab_price[i], 2)
        tab_price = tab_price[::-1]
        #--------------------------------------

        date_dict = dict(Counter(dates))
        if not date_dict:
            return render_template("miinto_stats.html", sum=0, labels=0, values=0)
        date_labels, values_o_number = zip(*date_dict.items())
        date_labels = list(date_labels)[::-1]
        values_o_number = list(values_o_number)[::-1]

        avg_order_number = round(sum_of_orders/len(date_labels), 1)
        percent_per_country = []
        for i in order_number:
            percent_per_country.append(str(round(int(i)/int(sum_of_orders), 4)*100))

        return render_template("miinto_stats.html", sum=sum_of_orders, labels=labels, values=order_number, date_labels=date_labels, values_o_number=values_o_number, avg_order_number = avg_order_number, percent_per_country = percent_per_country, summary_prices_pln=tab_price, sum_in_pln=round(pln_sum, 2))

    if request.method == "POST":
        req = request.form
        month = req.get('month')
        all_months = req.get('all')
        if all_months:
            return redirect(url_for('miint_stats', country=country))

        return redirect(url_for('miint_stats', country=country, month=month))

    platform_name = f"Platform-{country.upper()}"

    if platform_name not in countries.keys():
        return render_template("miinto_stats.html", sum=0, labels=0, values=[0])
    conn = sqlite3.connect("mrktplc_data.db")
    c = conn.cursor()

    if month:
        year, month = month.split("-")
        query = f"SELECT * FROM miinto_orders_db WHERE country = \"{platform_name}\" AND strftime('%m', date) = '{month}' AND strftime('%Y', date) = '{year}' ORDER BY date DESC"
        print(query)
    else:
        query = f"SELECT * FROM miinto_orders_db WHERE country = \"{platform_name}\"  ORDER BY date DESC"
        print(query)
    c.execute(query)

    rows = list(c.fetchall())
    dates = []
    price_sum = 0
    prices_sum_pln = 0
    date_with_price = []
    temp_price_date = ""

    for row in rows:
        single_date = row[2].split(" ")[0]

        dates.append(single_date)
        date_with_price.append((single_date, float(row[3]), float(row[4])))
        price_sum += float(row[3])
        prices_sum_pln += float(row[4])

    t_1 = []
    tab_price = []
    prices_in_pln = []
    coursor = -1
    for single_price in date_with_price:
        if single_price[0] not in t_1:
            t_1.append(single_price[0])
            tab_price.append(single_price[1])
            prices_in_pln.append(single_price[2])
            coursor += 1
        elif single_price[0] in t_1:
            tab_price[coursor] += single_price[1]
            prices_in_pln[coursor] += single_price[2]

    for i in range(len(tab_price)):
        tab_price[i] = round(tab_price[i], 2)
    tab_price = tab_price[::-1]
    prices_in_pln = prices_in_pln[::-1]

    date_dict = dict(Counter(dates))
    if not date_dict:
        return render_template("miinto_stats.html", sum=0, labels=0, values=0)
    date_labels, values_o_number = zip(*date_dict.items())
    date_labels = list(date_labels)[::-1]
    values_o_number = list(values_o_number)[::-1]

    currency = rows[0][5]

    if month:
        query = f"SELECT COUNT(*) FROM miinto_orders_db WHERE country = \"{platform_name}\" AND strftime('%m', date) = '{month}' AND strftime('%Y', date) = '{year}'"
    else:
        query = f"SELECT COUNT(*) FROM miinto_orders_db WHERE country = \"{platform_name}\""
    c.execute(query)

    sum = c.fetchall()
    course = coursers[currency]

    return render_template("miinto_stats_details.html", order_number=int(sum[0][0]), price = price_sum, prices_sum_pln=round(prices_sum_pln, 2), currency = currency, course=course, date_labels=date_labels, values_o_number=values_o_number, price_date_values=tab_price, country=country, all_country_list=labels, prices_in_pln=prices_in_pln)

def orders_worker_miinto(delay):
    def get_data_from_product_list(order_list, date_to_import):
        for order_data in order_list['data']:
            created_date = order_data['parentOrder']['createdAt'].split('T')
            created_date_1 = created_date[0] + " " + created_date[1].split("+")[0]

            created_date = time.strptime(created_date_1, "%Y-%m-%d %H:%M:%S")
            time_to_db = datetime.strptime(created_date_1, "%Y-%m-%d %H:%M:%S")

            if created_date < date_to_import:
                return True

            order_id = order_data['parentOrder']['id']
            customer_name = order_data['billingInformation']['name']
            price_in_order = 0
            currency = order_data['currency']

            for single_price in order_data['acceptedPositions']:
                price_in_order += int(single_price['price']) / 100

            price_pln = round(price_in_order / coursers[currency.upper()], 2)

            ord = MiintoOrdersDb(order_id, time_to_db, price_in_order, price_pln, currency, co)
            db.session.add(ord)
            try:
                db.session.commit()
                print(f"{order_id} added to Miinto {co} orders")
            except Exception as e:
                db.session.rollback()
                print(f"{order_id} skipped Miinto order")
        return False

    while True:
        global coursers
        coursers["EUR"] = currency_converter("PLN", "EUR")
        coursers["DKK"] = currency_converter("PLN", "DKK")
        coursers["SEK"] = currency_converter("PLN", "SEK")
        coursers["PLN"] = 1
        #sprawdz ostatnia date importu (z pliku)
        #jezeli plik nie istnieje wczytaj wszystkie zamowienia
        #znajduje wszystkie zamowienia z kazdego kraju z listy do ostatniej daty importu - zoptymalizowane do minimalnej ilosci requestow
        #zapisuj zamowienia do bazy dancyh (data, cena, kraj, imie i nazwisko) biorac pod uwage date ostatniego importu z pliku-10min

        date_to_import = "2021-12-01 08:00:00"
        if not os.path.isfile('miinto/last_import.txt'):
           date_to_import = time.strptime(date_to_import, "%Y-%m-%d %H:%M:%S")
           with open("miinto/last_import.txt", "w+") as f:
                f.write(f"2021-12-01 08:00:00")
        else:
            with open('miinto/last_import.txt') as f:
                date_to_import = f.readline()
                date_to_import = time.strptime(date_to_import, "%Y-%m-%d %H:%M:%S")

        countries = load_countries()

        for co in countries:
            country_id = countries[co]
            order_list = MiintoApi().get_order_list(country_id, "accepted", "0", "0")
            if order_list['meta']['status'] == "failure": #jezeli token wygasnie generuje jeszcze raz
                print("Problem z requestem na miinto. Generowanie nowego tokenu...")
                create_mcc()
                order_list = MiintoApi().get_order_list(country_id, "accepted", "0", "0")
            add_to_offset = int(int(order_list['meta']['totalItemCount'])/50)+1

            trigger = False
            print(f"Checking miinto orders {co}")
            for i in range(0, add_to_offset):
               if not trigger:
                   if i == add_to_offset:
                       k = int(order_list['meta']['totalItemCount']) - 50*add_to_offset
                       order_list = MiintoApi().get_order_list(country_id, "accepted", str(i*50), str(k))
                   else:
                       order_list = MiintoApi().get_order_list(country_id, "accepted", str(i*50), "50")
                   trigger = get_data_from_product_list(order_list, date_to_import)

        now = datetime.now() - timedelta(minutes=15)
        dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
        with open("miinto/last_import.txt", "w") as f:
            f.write(dt_string)
        time.sleep(delay)







