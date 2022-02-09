import json, requests, time, os, sqlite3, yaml

from datetime import datetime, timedelta

from collections import Counter
from miinto.miinto_requests import create_mcc, MiintoRequest
from flask import request, redirect, url_for, render_template, session
from __main__ import app, db

# set main courses, used when course converter not working
coursers = {"EUR": 0.22, "DKK": 1.63, "PLN": 1, "SEK": 2.29}

from data_base_objects import MiintoOrdersDb


#  return exchange rate. Example currency_converter("EUR") will return pln to euro ratio
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
@app.route("/miinto/stats/<country>/<month>", methods=['POST', 'GET'])
def miinto_stats(country="", month=""):
    # loads all available countries
    countries = load_countries()
    labels = [co for co in countries]

    # if user is not searching by specific month, print orders for all months
    if not country or country == "all":

        # when users uses form to filter orders
        if request.method == "POST":
            req = request.form
            month = req.get('month')
            all_months = req.get('all')
            if all_months: # when user want to show all months
                return redirect(url_for('miinto_stats', country="all"))
            # when users search for specific month
            return redirect(url_for('miinto_stats', country="all", month=month))

        conn = sqlite3.connect("mrktplc_data.db")
        c = conn.cursor()

        order_number = []  # stores sum of orders from all countries in list
        sum = 0
        sum_of_orders = 0 # stores sum of orders from all countries summary

        for co in countries:  # go for every available country
            # get number of order by month or from all of time
            if not month:
                query = f"SELECT COUNT(*) FROM miinto_orders_db WHERE country = \"{co}\""
            else:
                year, month_q = month.split("-")
                query = f"SELECT COUNT(*) FROM miinto_orders_db WHERE country = \"{co}\" AND strftime('%m', date) = '{month_q}' AND strftime('%Y', date) = '{year}'"

            c.execute(query)
            temp_data = c.fetchall()
            order_number.append(temp_data[0][0])
            sum_of_orders += int(temp_data[0][0])

        # when user provide date in form
        # select from db with date
        if month:
            year, month = month.split("-")
            query = f"SELECT * FROM miinto_orders_db WHERE strftime('%m', date) = '{month}' AND strftime('%Y', date) = '{year}' ORDER BY date DESC"
        # else select all
        elif not month:
            query = f"SELECT * FROM miinto_orders_db ORDER BY date DESC"

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
        cursor = -1
        for single_price in date_with_price:
            if single_price[0] not in t_1:
                t_1.append(single_price[0])
                tab_price.append(single_price[1])
                cursor += 1
            elif single_price[0] in t_1:
                tab_price[cursor] += single_price[1]

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

        return render_template("miinto_stats.html", sum=sum_of_orders, labels=labels, values=order_number, date_labels=date_labels, values_o_number=values_o_number, avg_order_number=avg_order_number, percent_per_country=percent_per_country, summary_prices_pln=tab_price, sum_in_pln=round(pln_sum, 2), month=month)

    if request.method == "POST":
        req = request.form
        month = req.get('month')
        all_months = req.get('all')
        if all_months:
            return redirect(url_for('miinto_stats', country=country))

        return redirect(url_for('miinto_stats', country=country, month=month))

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
    cursor = -1
    for single_price in date_with_price:
        if single_price[0] not in t_1:
            t_1.append(single_price[0])
            tab_price.append(single_price[1])
            prices_in_pln.append(single_price[2])
            cursor += 1
        elif single_price[0] in t_1:
            tab_price[cursor] += single_price[1]
            prices_in_pln[cursor] += single_price[2]

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
    conn = sqlite3.connect("mrktplc_data.db")
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







