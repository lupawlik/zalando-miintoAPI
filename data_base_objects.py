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
class Orders_db(db.Model):
    id = db.Column('id', db.Integer, primary_key = True) 
    order_number = db.Column('order_number', db.String(30), nullable=False, unique=True)
    data = db.Column('date', db.DateTime, nullable=False, default=datetime.utcnow)
    price = db.Column('price', db.String(16))

    def __init__(self, order_number, data, price):
        self.order_number = order_number
        self.data = data
        self.price = price

# table with order on miinto
class MiintoOrdersDb(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)
    order_number = db.Column('order_number', db.String(30), nullable=False, unique=True)
    data = db.Column('date', db.DateTime, nullable=False)
    price = db.Column('price', db.String(16))
    price_pln = db.Column('price_pln', db.String(16))
    currency = db.Column('currency', db.String(16))
    country = db.Column('country', db.String(16))

    def __init__(self, order_number, data, price, price_pln, currency, country):
        self.order_number = order_number
        self.data = data
        self.price = price
        self.price_pln = price_pln
        self.currency = currency
        self.country = country
