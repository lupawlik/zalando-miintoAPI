import json, time, datetime
from datetime import timedelta
import threading
from flask import Flask, request, redirect, url_for, session, jsonify, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
import sqlite3
import pandas as pd

from zalando_calls import ZalandoCall
import workers

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mrktplc_data.db'
db = SQLAlchemy(app)

from data_base_objects import Returns_db, Orders_db
import miinto.miintoApi as miintoApi


# example function to test @app.route("/run_test_thread/")
def test_fun(delay):
    while True:
        print("Test thread running...")
        time.sleep(delay)
# example url to run worker from ulr
@app.route("/run_test_thread/")
def tracking_and_status_worker():
    info = workers.run_new_thread("Testowy worker", test_fun, 5)
    return jsonify({'info': info})

# url used to stop thread, takes name of thread, returns json info
# if name is not defined return json with possible workers to kill
@app.route("/kill_worker/")
@app.route("/kill_worker/<name>")
def kill_worker(name=None):
    info = workers.kill_thread(name)
    if name:
        return jsonify({'info': info})

    return jsonify({'Workery mozliwe do zatrzymania': workers.get_list_of_threads(),
                    'Podaj nazwe w linku np': 'http://127.0.0.1:5000/kill_worker/nazwa'})

# main page of app, shows number of orders, returns and names of running workers
@app.route('/')
def index():
    conn = sqlite3.connect("mrktplc_data.db")
    today = datetime.date.today()
    today_first = str(today) + " 00:00:00.00"
    today_end = str(today) + " 23:59:59.99"

    # get number of orders and returns from zalando, print in html
    db_df = pd.read_sql_query(f"SELECT COUNT(id) FROM returns_db WHERE date(date) BETWEEN date('{today_first}') AND date('{today_end}')", conn)
    returns_number = str(db_df['COUNT(id)'][0])

    db_df = pd.read_sql_query(f"SELECT COUNT(id) FROM orders_db WHERE date(date) BETWEEN date('{today_first}') AND date('{today_end}')", conn)
    orders_number = str(db_df['COUNT(id)'][0])

    return render_template('index.html', workers=workers.get_list_of_threads(), returns_number=returns_number, orders_number=orders_number)

# route shows zalando orders by api
# site = page number, count = number of orders on page, date = order of showing orders, ord_number = order number (takes number or "all" value)
@app.route('/orders/', methods=['POST', 'GET'])
@app.route('/orders/<site>/<count>/<date>/<ord_number>', methods=['POST', 'GET'])
def order_site(site=0, count=10, date='newest', ord_number='all'):
    if request.method == "POST":
        if request.form['forwardBtn'] == 'go':  # if user use form to pass datas, use this if and get data from form
            req = request.form
            number = req.get('number_of_orders')
            data = req.get('date_of_order')
            order_number = req.get('order_number_input')

            if order_number:  # if user pass specific order numebr redirect to this order
                return redirect(url_for('order_site', site=0, count=1, date=data, ord_number=order_number))
            return redirect(url_for('order_site', site=0, count=number, date=data, ord_number='all'))  # redirect to searched result

        # handle a next and prev button
        if request.form['forwardBtn'] == 'nex':
            return redirect(url_for('order_site', site=int(site) + 1, count=count, date=date, ord_number=ord_number))
        if request.form['forwardBtn'] == 'prev':
            if site == '0' or site == 0:  # if page is 0, block this button
                return redirect(url_for('order_site', site=0, count=count, date=date, ord_number=ord_number))
            return redirect(url_for('order_site', site=int(site) - 1, count=count, date=date, ord_number=ord_number))

    orders_data = ZalandoCall().get_orders(site, count, date, ord_number) # used when route is loaded/get orders

    visible_orders_count = int(site), int(count)  # used to calculate order number in jinja2

    if count == '1':
        json_data = orders_data  # used to show all json data in jnija2 if user searched for specific order
        return render_template('orders.html', orders=orders_data, visible_orders_count=visible_orders_count, json_data=json_data)
    else:
        return render_template('orders.html', orders=orders_data, visible_orders_count=visible_orders_count)

# shows orders that can be realized, download list as excel column
@app.route('/orders/approved/', methods=['POST', 'GET'])
def order_site_approved():
    #  download list of orders in xlsx
    if request.method == "POST":
        list_of_order_numbers = []
        if request.form['forwardBtn'] == 'download_xlsx':
            orders_data = ZalandoCall().get_approved_orders()
            single_order_data = [i["data"] for i in orders_data]
            for order in single_order_data: # get from tab of response order number
                for numbers in order:
                    list_of_order_numbers.append(numbers["attributes"]["order_number"])
        df = pd.DataFrame()
        df['Order_number'] = list_of_order_numbers
        df.to_excel('approved_orders.xlsx', index=False)
        return send_file('approved_orders.xlsx', as_attachment=True)

    orders_data = ZalandoCall().get_approved_orders()
    return render_template('orders_approved.html', orders=orders_data)


@app.route("/returns/", methods=['POST', 'GET'])
def return_site():
    if request.method == "POST":  # if user send data in form
        req = request.form
        # get order number data (check forwardBtn)
        order_id = req.get('order_id')
        button_data = req.get('forwardBtn')
        if button_data == "search":  # run when user search only order number, loads details of orders, items etc.
            session['products_data'] = ZalandoCall().get_details_of_order(order_id)

            return render_template('returns.html', product_list=session['products_data'])

        if button_data == "process":  # run when user check checkbox with product thats want to return
            product_input = req.getlist('product_input')
            return_reason = int(req.get('return_reason'))

            action_info = "Nie wybrano towaru z listy, status nie zostal zmieniony. Prosze wprowadzic numer zamowienia jeszcze raz."
            print(product_input)
            if product_input:
                eans = ''
                price = 0
                for i in range(len(product_input)):  # go for all checked products
                    #  from all loaded data in "search" button, get only product checked in "product input"
                    one_final_product = session['products_data']['orders'][int(product_input[i])-1][product_input[i]]["order_details"]
                    one_final_product_id = session['products_data']['orders'][int(product_input[i])-1][product_input[i]]["id_details"]

                    # change status, save data to commit to db
                    action_info = ZalandoCall().update_status_to_returned(one_final_product_id, return_reason)
                    print(one_final_product)
                    eans += one_final_product["ean"] + ' '
                    price += float(one_final_product["price"])

                # add order to db (order number, ean string, price(string))
                order_id = one_final_product_id["order_number"]

                ret = Returns_db(order_id, eans, str(price))
                db.session.add(ret)
                try:
                    db.session.commit()
                except:
                    print("Nie dodano nowego rekordu. Prawdopodobnie wpis juz istniej")

            return render_template('returns.html', action_info=action_info) # action_info = shows info about request status

        if button_data == "download_csv":  # run when user want to download report of returned items from db
            returns = Returns_db.query.all()
            orders = Orders_db.query.all()
            session['date_start'] = f"{req.get('db_date_start')} 00:00:00.000000"
            session['date_end'] = f"{req.get('db_date_end')} 00:00:00.000000"
            if session['date_start'] == session['date_end']:  # if date same, get data from all day
                session['date_end'] = f"{req.get('db_date_end')} 23:59:59.000000"

            conn = sqlite3.connect("mrktplc_data.db")
            db_df = pd.read_sql_query(f"SELECT * FROM returns_db WHERE date(date) BETWEEN date('{session['date_start']}') AND date('{session['date_end']}')", conn)  # get data returns between date
            db_df.to_excel('returns_raport.xlsx', index=False)  # save data in excel format

            print(f"SELECT * FROM returns_db WHERE date(date) BETWEEN date('{session['date_start']}') AND date('{session['date_end']})'")
            print(session["date_start"])
            print(session["date_end"])
            conn.close()

            return send_file('returns_raport.xlsx', as_attachment=True)  # download excel format file

    return render_template('returns.html')  # if nothing is passed in url, shows clear template


# shows products details, ean in url
@app.route("/products/", methods=['POST', 'GET'])
@app.route("/products/<ean>", methods=['POST', 'GET'])
def product_site(ean=0):
    if request.method == "POST":
        if request.form['forwardBtn'] == 'check':
            req = request.form
            ean_number = req.get('ean_number')
            return redirect(url_for('product_site', ean=ean_number))

    data = ZalandoCall().get_all_product_by_one_ean(ean)  # returns product data
    return render_template('products.html', data=data)

# if tracking worker is running, uses these variables
done_tracking = 0
tracking_to_import = 0
# worker to upload label, return label and status. Takes list of tuples[(order_number, label, return_label), (order_number, label, return_label)...]
def zalando_labels_worker(data_set, worker_name):
    global done_tracking
    global tracking_to_import
    report = []
    for i in data_set:
        print(f"Adding tracking {i[1]}, return tracking {i[2]} to order {i[0]}")
        try:
            r = ZalandoCall().update_tracking(i[0], i[1], i[2], "shipped")
            report.append((i[0], r.status_code))
        except:
            report.append((i[0], "404"))
        done_tracking +=1
    print(report)
    workers.del_from_list(worker_name)
    done_tracking = 0
    tracking_to_import = 0


#  url to update order status and pass tracking numbers
@app.route("/tracking/", methods=['POST', 'GET'])
def tracking_site():
    if request.method == "POST":
        if request.form['forwardBtn'] == 'single_upload':
            req = request.form
            session['order_nr'] = req.get('order_id')
            session['tracking'] = req.get('track_num')
            session['return_tracking'] = req.get('ret_track')
            session['stauts'] = req.get('status')
            ZalandoCall().update_tracking(session['order_nr'], session['tracking'], session['return_tracking'], session['stauts'])  # tracking, return_tracking, statsu CAN be empty
        # import data from xlsx file, run worker to uploads all tracking to zalando.
        # show progress on html pag
        # when worker stops, remove from worker list and send mail to user
        if request.form['forwardBtn'] == 'multiple_upload':
            imported_file = request.files['file']
            imported_file = pd.read_excel(imported_file)

            # get columns name
            columns = [x for x in imported_file]

            # loads all columns
            order_number_list = imported_file[columns[0]]
            tracking_list = imported_file[columns[1]]
            return_tracking_list = imported_file[columns[2]]

            # creates data to worker
            data_set = []
            for i, v in enumerate(order_number_list):
                data_set.append((order_number_list[i], tracking_list[i], return_tracking_list[i]))

            # set name of worker
            worker_name = f"ZalandoLabels{len(data_set)}"
            global tracking_to_import
            tracking_to_import = len(data_set)
            workers.run_new_thread(worker_name, zalando_labels_worker, data_set, worker_name)

    return render_template('tracking.html', tracking_upload_status=done_tracking, number_to_import=tracking_to_import)

# NOT FINISHED
# url used to send to another app package with data about orders with api
# takes data list (example orders number) print it in jinja2
# for every order, get details and makes session['data_set'], then send it by POST method to another app
# details of order can be modified before sending by api
@app.route("/tracking/adjustment/", methods=['POST', 'GET'])
@app.route("/tracking/adjustment/<order_number>", methods=['POST', 'GET'])
def tracking_adjustment_site(order_number=''):
    order_details = ''
    data = ['10105351216227', '10103353955240', '10103353189027', '10104353187413', '10103352965041', '10103352983322', '10103353000214', '10103354003415']  # example
    session['ean_list'] = []

    if order_number != '':
        session['order_number'] = order_number

        session['order_data'] = ZalandoCall().get_orders(0, 1, "newest", order_number)  # get orders data to use in get_details_of_order()
        order_details = session['order_data']

        order_data = ZalandoCall().get_details_of_order(session['order_number'])
        for i, v in enumerate(order_data["orders"]):
            single_ean = order_data["orders"][i][str(i+1)]["order_details"]["ean"]
            session['ean_list'].append(single_ean)
    # if user send new data, create json
    if request.method == "POST":
        if request.form['forwardBtn'] == 'submit_new_data':
            req = request.form
            session['name'] = req.get('name')
            session['customer_number'] = req.get('customer_number')
            session['surname'] = req.get('surname')
            session['address'] = req.get('address')
            session['city'] = req.get('city')
            session['zip_code'] = req.get('zip_code')
            session['country'] = req.get('country')
            session['mail'] = req.get('mail')
            session['ean_list'] = req.getlist('ean_list')

            session['data_set'] = {
                'customer_number': session['customer_number'],
                'name': session['name'],
                'surname': session['surname'],
                'address1': session['address'],
                'city': session['city'],
                'zip_code': session['zip_code'],
                'country': session['country'],
                'mail': session['mail'],
                'ean_list': session['ean_list']
            }
            session['data_set'] = json.dumps(session['data_set'])
            session['data_set'] = json.loads(session['data_set'])

            # request POST to api print(session['data_set'])
    return render_template('tracking_adjustment.html', data=data, order_number=order_number,
                           order_details=order_details, ean_list=session['ean_list'])


# translate time for jinja2
@app.context_processor
def time_edit():
    # takes zalando time format and return %H:%M:%S | %d.%m.%Y
    def change_time(given_time):
        try:
            order_time = datetime.datetime.strptime(given_time[:-10], "%Y-%m-%dT%H:%M:%S")
            final_time = order_time + datetime.timedelta(hours=1)
            final_time = final_time.strftime('%H:%M:%S | %d.%m.%Y')
            return final_time
        except:
            return "brak danych"

    # used to check if order is late, takes zalando time to realize order, return green or red if order is late or not
    def get_time_delay(given_time):
        now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        now = datetime.datetime.strptime(now, "%Y-%m-%dT%H:%M:%S")
        try:
            order_time = datetime.datetime.strptime(given_time[:-10], "%Y-%m-%dT%H:%M:%S")
            final_time = order_time + datetime.timedelta(hours=1)
        except:
            return "brak danych"

        if now < final_time:
            return "green"

        elif now >= final_time:
            return "red"

    return dict(change_time=change_time, get_time_delay=get_time_delay)


# ZALANDO ORDER WORKER #
# run with treading, takes time in seconds to next run
# import orders from zalando to db every time
def orders_worker(delay):
    try:
        while True:
            print("\nWorker zalando orders")
            print("************************************")
            orders_data = ZalandoCall().get_last_hour_orders()  # return orders from last hour

            for single_order in orders_data['data']:
                order_number = single_order["attributes"]["order_number"]
                order_date = datetime.datetime.strptime(single_order["attributes"]["order_date"][:-10], "%Y-%m-%dT%H:%M:%S")  # get date of order to pass to db

                final_time = order_date + timedelta(hours=1)
                order_price = single_order["attributes"]["order_lines_price_amount"]  # get price in order to pass to db
                ord = Orders_db(order_number, final_time, str(order_price))  # add order
                db.session.add(ord)
                try:
                    db.session.commit()
                    print(f"{order_number} added to Zalando orders {final_time}")  # if the order has already been added, skip it. If not add
                except Exception as e:
                    db.session.rollback()
                    print(f"{order_number} skipped Zalando order {final_time}")
                    #print(e)
            print("************************************\n")
            time.sleep(delay)
    except:
        return 0


# function that starts the thread
# workers.run_new_thread(name_of_worker, function, params)
def thread_starter():
    workers.run_new_thread("ZamowieniaZalando5m", orders_worker, 300)  # runs zalando orders worker
    workers.run_new_thread("ZamowieniaMiinto1h", miintoApi.orders_worker_miinto, 3600)  # runs miinto orders worker

if __name__ == '__main__':
    app.secret_key = ".."
    # run flask app and workers with threading. "0.0.0.0" for run in local network
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)).start()
    db.create_all()

    thread_controll = threading.Thread(target=thread_starter)
    thread_controll.deamon = True
    thread_controll.start()