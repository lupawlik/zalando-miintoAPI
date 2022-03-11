from __main__ import db
from datetime import datetime

# table with returned order on zalando
class Returns_db(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)    
    order_number = db.Column('order_number', db.String(30), nullable=False, unique=True)
    eans = db.Column('enas', db.String(200), nullable=False)
    data = db.Column('date', db.DateTime, nullable=False, default=datetime.utcnow)
    price = db.Column('price', db.String(16))

    def __init__(self, order_number, eans, price):
        self.order_number = order_number
        self.eans = eans
        self.price = price

# table with order on zalando
class ZalandoOrders(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)
    order_number = db.Column('order_number', db.String(30), nullable=False, unique=True)
    zalando_id = db.Column('zalando_id', db.String(50))
    price = db.Column('price', db.String(16))
    returned_price = db.Column('returned_price', db.String(16))
    currency = db.Column('currency', db.String(16))
    first_name = db.Column('first_name', db.String(100))
    last_name = db.Column('last_name', db.String(100))
    address_line_1 = db.Column('address_line_1', db.String(200))
    city = db.Column('city', db.String(100))
    zip_code = db.Column('zip_code', db.String(20))
    country_code = db.Column('country_code', db.String(20))
    status = db.Column('status', db.String(30))
    tracking_number = db.Column('tracking_number', db.String(30))
    return_tracking_number = db.Column('return_tracking_number', db.String(30))
    items_amount = db.Column('items_amount', db.Integer)
    items_returned_amount = db.Column('items_returned_amount', db.Integer)
    data = db.Column('date', db.DateTime, nullable=False, default=datetime.utcnow)
    data_end = db.Column('date_end', db.DateTime)

    def __init__(self, order_number, zalando_id, data, data_end, price, currency, first_name, last_name, address_line_1, city, zip_code, country_code, status, tracking_number, return_tracking_number, items_amount):
        self.order_number = order_number
        self.zalando_id = zalando_id
        self.data = data
        self.data_end = data_end
        self.price = price
        self.currency = currency
        self.first_name = first_name
        self.last_name = last_name
        self.address_line_1 = address_line_1
        self.city = city
        self.zip_code = zip_code
        self.country_code = country_code
        self.status = status
        self.tracking_number = tracking_number
        self.return_tracking_number = return_tracking_number
        self.items_amount = items_amount

# table with order on miinto
class MiintoOrdersDb(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    order_number = db.Column('order_number', db.String(30), nullable=False, unique=True)
    data = db.Column('date', db.DateTime, nullable=False)
    price = db.Column('price', db.String(16))
    price_pln = db.Column('price_pln', db.String(16))
    currency = db.Column('currency', db.String(16))
    country = db.Column('country', db.String(16))
    name = db.Column('name', db.String(250))
    products_names = db.Column('products_names', db.String(1500))
    eans = db.Column('eans', db.String(1000))
    products_id = db.Column('products_id', db.String(1500))
    main_id = db.Column('main_id', db.String(30), nullable=False, unique=True)

    def __init__(self, order_number, data, price, price_pln, currency, country, name, products_names, eans, products_id, main_id,):

        self.order_number = order_number
        self.data = data
        self.price = price
        self.price_pln = price_pln
        self.currency = currency
        self.country = country
        self.name = name
        self.products_names = products_names
        self.eans = eans
        self.products_id = products_id
        self.main_id = main_id
