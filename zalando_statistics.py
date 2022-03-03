from __main__ import app, db
import sqlite3
from calendar import monthrange
from flask import Flask, render_template, redirect, url_for
from datetime import date
import workers

# site showing statistics (orders, returns etc. by date)
@app.route("/zalando_stats/")
@app.route("/zalando_stats/<country>/<year>/<month>")
def zalando_stats_page(year=None, month=None, country='DE', orders_on_page=1000, offset=0):
    # get current year - to show only from this year and redirect to correct page with date
    if not year:
        todays_date = date.today()
        year = todays_date.year
        month = todays_date.month
        return redirect(url_for('zalando_stats_page', country=country, year=year, month=month))

    # when year and month are specified
    # add '0' if month < november
    if len(month) < 2:
        month = '0' + str(month)
    # if month is january and client want prev month - change year and redirect. If is december an button is next change year
    if int(month) == 0:
        return redirect(url_for('zalando_stats_page', country=country, year=int(year)-1, month=12))
    elif int(month) == 13:
        return redirect(url_for('zalando_stats_page', country=country, year=int(year)+1, month=1))

    conn = sqlite3.connect("mrktplc_data.db", check_same_thread=False)
    c = conn.cursor()

    # get orders for given year and month
    query = f"SELECT * FROM zalando_orders WHERE strftime('%Y', date) = '{year}' AND strftime('%m', date) = '{month}' AND country_code = '{country}' AND status != 'initial' ORDER BY date DESC"
    c.execute(query)
    print(query)
    orders = list(c.fetchall())

    # get orders for given year and month
    query = f"SELECT * FROM returns_db WHERE strftime('%Y', date) = '{year}' AND strftime('%m', date) = '{month}' ORDER BY date DESC"
    c.execute(query)
    returns = list(c.fetchall())

    # get labels to chart - label is list of all day in month ex ['01.01, 02.01, 03.01...]
    days_in_month = monthrange(int(year), int(month))[1]
    days_labels = [f"{str(month)}-0{str(x)}" if x < 10 else f"{str(month)}-{str(x)}" for x in range(1, days_in_month+1)]
    # get number of orders/returns per day in days_labes
    order_number_per_day = []
    returns_number_per_day = []
    price_sum_per_day = []
    returns_price_sum_per_day = []
    orders_returned_each_day = []
    returns_to_order_ratio = []
    for day in days_labels:
        # get orders created in given day
        o_n = [order for order in orders if day in order[17]]
        # get return created in given day
        r_n = [return_1 for return_1 in returns if day in return_1[3]]
        price_sum = sum([float(price[3]) for price in o_n])
        return_price_sum = sum([float(returns[4]) for returns in r_n])

        # counts how many order from this day was returned
        orders_returned = [is_returned for is_returned in orders if day in is_returned[17] and is_returned[16]]
        orders_returned_each_day.append(len(orders_returned))
        price_sum_per_day.append(round(price_sum, 2))
        returns_price_sum_per_day.append(round(return_price_sum, 2))
        order_number_per_day.append(len(o_n))
        returns_number_per_day.append(len(r_n))

        try:
            returns_to_order_ratio.append(round((len(orders_returned)/len(o_n))*100, 2))
        except ZeroDivisionError:
            returns_to_order_ratio.append(0)

    ## ZMIENIC ORDERS I RETURNS NA SUMY
    return render_template("zalando_stats.html", workers=workers.get_list_of_threads(), country=country, year=year,
                           month=month, days_labels=days_labels, order_per_day=order_number_per_day, return_per_day=returns_number_per_day,
                           orders=orders, price_sum_per_day=price_sum_per_day, returns_price_sum_per_day=returns_price_sum_per_day, returns=returns,
                           orders_returned_each_day=orders_returned_each_day, returns_to_order_ratio=returns_to_order_ratio)