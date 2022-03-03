import json, requests, time, os, sqlite3, yaml

from datetime import datetime, timedelta, date
from calendar import monthrange
from collections import Counter
from miinto.miinto_requests import create_mcc, MiintoRequest
from flask import request, redirect, url_for, render_template, session
from __main__ import app, db


# set main courses, used when course converter not working
coursers = {"EUR": 0.22, "DKK": 1.63, "PLN": 1, "SEK": 2.29}

from data_base_objects import MiintoOrdersDb


# return exchange rate. Example currency_converter("EUR") will return pln to euro ratio
def currency_converter(to: str, date=''):
    # when searching for historically coursers
    if date:
        status = 404  # 404 means "not courses data from this day" - used in weekends
        counter_of_skipped_days = 0
        while status == 404:
            r = requests.get(f"http://api.nbp.pl/api/exchangerates/rates/a/{to}/{date}/")
            # when courses are loaded correctly from given day
            if r.ok:
                course = r.json()['rates'][0]['mid']
                course = round(100/(round(float(course), 2)*100), 2)  # reverse number and round to 2 digits after ,
                print(f"Wczytano kurs {to}: {course}")
                return course
            # when is weekend retry loop with day -1 in date, to get courses of prev day
            else:
                date = datetime.strptime(date, '%Y-%m-%d')
                date = date - timedelta(days=1)
                date = date.strftime('%Y-%m-%d')
                print(date)
                # check if is problem with api (if returns non stop 404)
                counter_of_skipped_days += 1
                if counter_of_skipped_days > 5:
                    break
        print(f"Nie udalo sie pobrac kurs pln - {to} z NBP")
        return coursers[to]
    # when searching for current course
    else:
        try:
            r = requests.get(f"http://api.nbp.pl/api/exchangerates/rates/a/{to}/")
            course = r.json()['rates'][0]['mid']
            course = round(100/(round(float(course), 2)*100), 2)  # reverse number and round to 2 digits after ,
            print(f"Wczytano kurs {to}: {course}")
            return course
        except:
            print(f"Nie udalo sie pobrac kursu pln - {to} z NBP")
            return coursers[to]

#  if file with countries exist load it. File is generated with create_mcc() function and returns list of available countries on miinto
def load_countries():
    try:
        with open("miinto/countries.txt") as f:
            string_data = f.readlines()[0].replace("\'", "\"")
            json_data = json.loads(string_data)
    except:
        # generate new token (mcc.txt) and list of countries(countries.txt)
        create_mcc()
        with open("miinto/countries.txt") as f:
            string_data = f.readlines()[0] .replace("\'", "\"")
            json_data = json.loads(string_data)
    return json_data

class MiintoApi(MiintoRequest):

    # return singler order by id
    def get_order(self, country, id):
        return self.place_request("GET", f"/shops/{country}/orders/{id}")

    # return list of countries
    def get_order_list(self, country, status="accepted", offset="0", limit="50"):
        data = {
            "status[]": status,
            "limit": limit,
            "offset": offset,
            # "sort": "-createdAt",
            # "query": "text"
            }
        return self.place_request("GET", f"/shops/{country}/orders", data)

# route to print statistic from miinto, using data from database nad chart.js library
@app.route("/miinto/", methods=['POST', 'GET'])
@app.route("/miinto/stats/", methods=['POST', 'GET'])
@app.route("/miinto/stats/<country>/", methods=['POST', 'GET'])
@app.route("/miinto/stats/<country>/<year>/", methods=['POST', 'GET'])
@app.route("/miinto/stats/<country>/<year>/<month>/", methods=['POST', 'GET'])
def miinto_stats(country=None, year=None, month=None):
    # loads all available countries
    countries = load_countries()
    labels_counties_names = [co for co in countries]
    print(labels_counties_names)
    # if year and month are not declared, get current year/month
    if not year:
        todays_date = date.today()
        year = todays_date.year
        # if county not declared load data's from db for all of time
        if not country:
            country = 'all'
        return redirect(url_for("miinto_stats", country=country, year=year, month=None))

    # when is year specified but month not
    # shows monthly statistics
    if year and not month:
        conn = sqlite3.connect("mrktplc_data.db", check_same_thread=False)
        c = conn.cursor()
        # get all monts with current year
        time_labels = [f"{year}-0{x}" if x < 10 else f"{year}-{x}" for x in range(1, 13)]
        print(time_labels)
        if not country or country == "all":
            query = f"SELECT * FROM miinto_orders_db WHERE strftime('%Y', date) = '{year}'"
        else:
            query = f"SELECT * FROM miinto_orders_db WHERE country = \"{country}\" AND strftime('%Y', date) = '{year}'"

        c.execute(query)
        orders_list = list(c.fetchall())
        currency_symbol = None
        order_number_per_month = []
        summary_prices_per_month_pln = []
        summary_prices_per_month_currency = []
        for single_month in time_labels:
            # get order number per single month
            o_n = [order for order in orders_list if single_month in order[2]]
            order_number_per_month.append(len(o_n))

            # get sum of prices in orders for single_month
            price_sum = sum([float(price[4]) for price in o_n])
            summary_prices_per_month_pln.append(round(price_sum, 2))

            # when users is searching for specific country, get prices in these country currency and currency code
            if country and country != "all":
                price_sum = sum([float(price[3]) for price in o_n])
                summary_prices_per_month_currency.append(round(price_sum, 2))
                try:
                    currency_symbol = orders_list[0][5]
                except:
                    currency_symbol = None

        # get number of orders per country if searching for all countries
        number_of_orders_per_country = []
        percent_domination = []
        if country == "all" or not country:
            for country_miinto in labels_counties_names:
                o_n_per_country = [order for order in orders_list if country_miinto in order[6]]
                number_of_orders_per_country.append(len(o_n_per_country))
                try:
                    percent_domination.append(round((len(o_n_per_country)/len(orders_list)*100),2))
                except ZeroDivisionError:
                    percent_domination.append(0)

        return render_template("miinto_stats.html", country=country, year=year, month=None, time_labels=time_labels, labels_counties_names=labels_counties_names, order_number_per_month=order_number_per_month,
                                summary_prices_per_month_pln=summary_prices_per_month_pln, summary_prices_per_month_currency=summary_prices_per_month_currency, currency_symbol=currency_symbol,
                                number_of_orders_per_country=number_of_orders_per_country, percent_domination=percent_domination)


    # if from jinja2 is request to get current year
    if month == "get_current_month":
        todays_date = date.today()
        month = todays_date.month
        return redirect(url_for('miinto_stats', country=country, year=year, month=month))

    # when year and month are specified
    # add '0' if month < november
    if len(month) < 2:
        month = '0' + str(month)
    # if month is january and client want prev month - change year and redirect. If is december an button is next change year
    if int(month) == 0:
        return redirect(url_for('miinto_stats', country=country, year=int(year)-1, month=12))
    elif int(month) == 13:
        return redirect(url_for('miinto_stats', country=country, year=int(year)+1, month=1))

    # get labels to chart - label is list of all day in month ex ['01.01, 02.01, 03.01...]
    days_in_month = monthrange(int(year), int(month))[1]
    time_labels = [f"{str(month)}-0{str(x)}" if x < 10 else f"{str(month)}-{str(x)}" for x in range(1, days_in_month+1)]
    conn = sqlite3.connect("mrktplc_data.db", check_same_thread=False)
    c = conn.cursor()
    # get all months with current year

    print(time_labels)
    if not country or country == "all":
        query = f"SELECT * FROM miinto_orders_db WHERE strftime('%Y', date) = '{year}'"
    else:
        query = f"SELECT * FROM miinto_orders_db WHERE country = \"{country}\" AND strftime('%Y', date) = '{year}'"

    c.execute(query)
    orders_list = list(c.fetchall())
    currency_symbol = None
    order_number_per_month = []
    summary_prices_per_month_pln = []
    summary_prices_per_month_currency = []
    for single_month in time_labels:
        # get order number per single month
        o_n = [order for order in orders_list if single_month in order[2]]
        order_number_per_month.append(len(o_n))

        # get sum of prices in orders for single_month
        price_sum = sum([float(price[4]) for price in o_n])
        summary_prices_per_month_pln.append(round(price_sum, 2))

        # when users is searching for specific country, get prices in these country currency and currency code
        if country and country != "all":
            price_sum = sum([float(price[3]) for price in o_n])
            summary_prices_per_month_currency.append(round(price_sum, 2))
            try:
                currency_symbol = orders_list[0][5]
            except:
                currency_symbol = None

    # get number of orders per country if searching for all countries
    number_of_orders_per_country = []
    percent_domination = []
    if country == "all" or not country:
        for country_miinto in labels_counties_names:
            o_n_per_country = [order for order in orders_list if country_miinto in order[6] and f"{year}-{month}" in order[2]]
            number_of_orders_per_country.append(len(o_n_per_country))
            try:
                percent_domination.append(round((len(o_n_per_country) / len(orders_list) * 100), 2))
            except ZeroDivisionError:
                percent_domination.append(0)

    return render_template("miinto_stats.html", country=country, year=year, month=month, time_labels=time_labels,
                           labels_counties_names=labels_counties_names, order_number_per_month=order_number_per_month,
                           summary_prices_per_month_pln=summary_prices_per_month_pln,
                           summary_prices_per_month_currency=summary_prices_per_month_currency,
                           currency_symbol=currency_symbol,
                           number_of_orders_per_country=number_of_orders_per_country,
                           percent_domination=percent_domination)


# worker update db with new orders
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

            ord = MiintoOrdersDb(order_id, time_to_db, price_in_order, price_pln, currency, co, customer_name)
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
        coursers["EUR"] = currency_converter("EUR")
        coursers["DKK"] = currency_converter("DKK")
        coursers["SEK"] = currency_converter("SEK")
        coursers["PLN"] = 1
        # sprawdz ostatnia date importu (z pliku)
        # jezeli plik nie istnieje wczytaj wszystkie zamowienia
        # znajduje wszystkie zamowienia z kazdego kraju z listy do ostatniej daty importu - zoptymalizowane do minimalnej ilosci requestow
        # zapisuj zamowienia do bazy dancyh (data, cena, kraj, imie i nazwisko) biorac pod uwage date ostatniego importu z pliku-10min

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
            # check if token is expired - gen new. If new token is no working skip this country

            if order_list['meta']['status'] == "failure": #jezeli token wygasnie generuje jeszcze raz
                print("Problem z requestem na miinto. Generowanie nowego tokenu...")
                create_mcc()
                order_list = MiintoApi().get_order_list(country_id, "accepted", "0", "0")
                if order_list['meta']['status'] == "failure":
                    print(f"Problem z pobraniem danych z {countries[co]}")
                    continue
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

        now = datetime.now() - timedelta(hours=1)
        dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
        with open("miinto/last_import.txt", "w") as f:
            f.write(dt_string)
        time.sleep(delay)

# shows orders from db
@app.route('/miinto/orders/', methods=['POST', 'GET'])
@app.route('/miinto/orders/<country>/<amount_on_site>/<offset>/<date_start>/<date_end>/', methods=['POST', 'GET'])
@app.route('/miinto/orders/<country>/<amount_on_site>/<offset>/<date_start>/<date_end>/<order_number>', methods=['POST', 'GET'])
def order_site_miinto(country="all", amount_on_site="500", offset="0", date_start="all", date_end="all", order_number=''):
    conn = sqlite3.connect("mrktplc_data.db", check_same_thread=False)
    c = conn.cursor()

    if request.method == "POST":
        # handle a next and prev button
        if request.form['forwardBtn'] == 'nex':  # add 1 to offset
            # offset is not changing when order_number is specified
            if not order_number:
                new_offset = int(offset)+1
            else:
                new_offset = offset
            return redirect(url_for("order_site_miinto", country=country, amount_on_site=amount_on_site, offset=new_offset, date_start=date_start, date_end=date_end, order_number=order_number))
        if request.form['forwardBtn'] == 'prev':  # add 1 to offset

            # offset is not changing when order_number is specified
            if not order_number:
                # offset cannot be <0
                if int(offset)-1 < 0:
                    new_offset = 0
                elif int(offset)-1 >= 0:
                    new_offset = int(offset)-1
            else:
                new_offset = offset
            return redirect(url_for("order_site_miinto", country=country, amount_on_site=amount_on_site, offset=new_offset, date_start=date_start, date_end=date_end, order_number=order_number))
        # when user set filters and search for these orders - get filters and redirect for this page but with filters
        if request.form['forwardBtn'] == 'go':
            req = request.form
            session['number_of_orders'] = req.get('number_of_orders')
            session['date_of_order'] = req.get('date_of_order')
            session['order_number_input'] = req.get('order_number_input')
            session['country_name'] = req.get('country_name')
            session['date_start'] = req.get('date_start')
            session['date_end'] = req.get('date_end')

            # when user not searching by date, pass in url "all" to get data from all periods
            if not session['date_start']:
                session['date_start'] = "all"
            if not session['date_end']:
                session['date_end'] = "all"
            # redirect to same site with filters
            return redirect(url_for("order_site_miinto", country=session['country_name'], amount_on_site=session['number_of_orders'], offset="0", date_start=session['date_start'], date_end=session['date_end'], order_number=session['order_number_input']))
            # if order_number is searched by user - print it

    # when site is loaded for first time or loaded with filters, print last 500 orders
    query = f"SELECT * FROM miinto_orders_db ORDER BY date DESC LIMIT 500"
    # if user pass order number: print only this order
    if order_number:
        query = f"SELECT * FROM miinto_orders_db WHERE order_number = \"{session['order_number_input']}\""
    # if user didn't pass order number
    else:
        # when user not searching for ALL countries
        if country == "all":
            # when user searching for specific date (between two dates)
            if date_start != "all" and date_end != "all":
                query = f"SELECT * FROM miinto_orders_db WHERE date(date) BETWEEN date('{session['date_start']}') AND date('{session['date_end']}') ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"
            # when user searching for specific date (after some date - if only date_start is specified)
            elif date_start != "all" and date_end == "all":
                query = f"SELECT * FROM miinto_orders_db WHERE date(date) >= date('{session['date_start']}') ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"
            # when user searching for specific date (before some date - if only date_end is specified)
            elif date_start == "all" and date_end != "all":
                query = f"SELECT * FROM miinto_orders_db WHERE date(date) <= date('{session['date_end']}') ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"

            # when user NOT searching for specific date
            else:
                query = f"SELECT * FROM miinto_orders_db ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"

        # when user searching for SPECIFIC countries
        else:
            # when user searching for specific date
            if date_start != "all" and date_end != "all":
                query = f"SELECT * FROM miinto_orders_db WHERE country = \"{session['country_name']}\" AND date(date) BETWEEN date('{session['date_start']}') AND date('{session['date_end']}') ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"
            # when user searching for specific date (after some date - if only date_start is specified)
            elif date_start != "all" and date_end == "all":
                query = f"SELECT * FROM miinto_orders_db WHERE country = \"{session['country_name']}\" AND date(date) >= date('{session['date_start']}') ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"
            # when user searching for specific date (before some date - if only date_end is specified)
            elif date_start == "all" and date_end != "all":
                query = f"SELECT * FROM miinto_orders_db WHERE country = \"{session['country_name']}\" AND date(date) <= date('{session['date_end']}') ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"
            # when user not searching for specific date
            else:
                query = f"SELECT * FROM miinto_orders_db WHERE country = \"{session['country_name']}\" ORDER BY date DESC LIMIT {int(amount_on_site)} OFFSET {int(amount_on_site)*int(offset)}"

    visible_orders_count = int(amount_on_site), int(offset)  # used to calculate order number and offset number in jinja2
    print(query)
    c.execute(query)
    orders = c.fetchall()
    return render_template("miinto_orders.html", orders=orders, visible_orders_count=visible_orders_count)







