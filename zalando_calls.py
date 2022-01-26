# contains all functions communicating with api zalando

import time
import datetime
from datetime import timedelta
from string import Template
from zalando_requests import ZalandoRequest

# class contains all necessary api requests
class ZalandoCall(ZalandoRequest):
    #  return order list, with all data
    def get_orders(self, site, number, data, *args):  # site = number of page with orders, number = max orders per page max 1000, data = order of orders
        params = {}
        
        params['page[size]'] = number
        params['page[number]'] = site
        if data == "newest":
            params['sort'] = '-order_date'
        elif data == "oldest":
            params['sort'] = 'order_date'
        if args:  # if  user pass a order number include it
            if args[0] != 'all':
                params['order_number'] = args[0]
        params['include'] = "order_lines"
        r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)

        # when result are empty
        if not r['data']:
            return "NIE MA TAKIEGO ZAMOWIENIA"
        return r

    # return list of all orders with "approved" status
    def get_approved_orders(self):
        params = {
            'page[size]': 1000,
            'sort': 'order_date',
            'order_status': 'Approved',
            'include': 'order_lines',
            }
        page = 0
        data_tab = []  # list of response data
        # add 1 to page and go for all pages when is more than 1000 to view
        while True:
            params['page[number]'] = page
            r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)
            page += 1
            # when result are empty
            if not r['data']:
                break
            data_tab.append(r)
        return data_tab

    # return order from last hour, used in zalando orders worker
    def get_last_hour_orders(self):
        now = (datetime.datetime.now() - timedelta(hours=2)).replace(microsecond=0).isoformat()  # get time -2 hours
        now = str(now)+"Z"
        params={
            'page[size]': 1000,
            'created_after': now,
            }

        r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)
        try:
            return r
        except:
            return 0

    # takes ean and return all product by ean
    # uses graphql templates
    def get_all_product_by_one_ean(self, ean):
        # body to search by ean
        query_template = Template("""
        {
          psr {
            product_models(
              input:
              { merchant_ids: ["$merchant_id"]
              , status_clusters: []
              , season_codes: []
              , brand_codes: []
              , country_codes: []
              , limit: 10
              , search_value: "$item"
              }) {
              items {
                product_configs {
                  product_simples {
                    zalando_product_simple_id
                  }
                }
              }
            }
          }
        }
            """)

        # graphql template declaration
        query = query_template.substitute(item=ean, merchant_id=self.merchant_id)
        params = {'query': query}
        r = self.place_request("POST", "/graphql", params)
        if not r['data']['psr']['product_models']['items']:  # if product not exist
            return ""
        # return zalando id of product by ean, used in another request to search all eans of one product
        simple_id = r['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples'][0]['zalando_product_simple_id'][0:13]

        query_template = Template("""
        {
          psr {
            product_models(
              input:
              { merchant_ids: ["$merchant_id"]
              , status_clusters: []
              , season_codes: []
              , brand_codes: []
              , country_codes: []
              , limit: 40
              , search_value: "$item"
              }) {
              items {
                product_configs {
                  product_simples {
                    zalando_product_simple_id
                    ean
                    offers {
                      offer_status {
                            status_detail_code
                            status_cluster
                            short_description { en }
                        }
                      country { code localized { en } }
                      stock { amount }
                      price {
                        regular_price { amount currency }
                        discounted_price { amount currency }
                      }         
                    }
                  }
                }
              }
            }
          }
        }
            """)
        query = query_template.substitute(item=simple_id, merchant_id=self.merchant_id)
        params = {'query': query}
        r = self.place_request("POST", "/graphql", params)
        # return all products in final_date list
        r = r['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples']
        final_data = []
        for product in r:
            final_data.append(product)
        return final_data

    # return ean and info about product by product_code
    def get_ean(self, product_code):
        query_template = Template("""
            {
              psr {
                product_models(
                  input:
                  { merchant_ids: ["$merchant_id"]
                  , status_clusters: []
                  , season_codes: []
                  , brand_codes: []
                  , country_codes: []
                  , limit: 40
                  , search_value: "$item"
                  }) {
                  items {
                    product_configs {
                      product_simples {
                        zalando_product_simple_id
                        ean
                        offers {
                          price {
                            regular_price { amount currency }
                            discounted_price { amount currency }
                          }         
                        }
                      }
                    }
                  }
                }
              }
            }
                """)
        # these query returns price/ean/simpleid
        query = query_template.substitute(item=product_code, merchant_id=self.merchant_id)
        params = {'query': query}
        r = self.place_request("POST", "/graphql", params)
        return r

    # takes order number or data from get_orders() to order_number param.
    # if data from get_orders(), from_data param need to be True
    # returns list of dict of every order given (order details and all id)
    def get_details_of_order(self, order_number, from_data=False):
            if not from_data:  # when user give order_number
                orders_data = self.get_orders(0, 1, "newest", order_number)
            elif from_data:  # if user pass data from get_orders() instead order_number
                orders_data = order_number
            if orders_data == 'NIE MA TAKIEGO ZAMOWIENIA':  # when order data are empty
                return 'NIE MA TAKIEGO ZAMOWIENIA'

            order_id = orders_data['data'][0]['id']

            item_lines_ids = []  # contains zalando lines id of order
            item_ids = []  # contains zalando items id of order
            order_details = {"orders":[]}  # contains list of dict of order detail

            # go for every order in list
            for i in range(len(orders_data['included'])):
                item_lines_ids.append(orders_data['included'][i]['attributes']['order_line_id'])
                item_ids.append(orders_data['included'][i]['attributes']['order_item_id'])
                
                url = "/merchants/{merchant_id}"+f"/orders/{order_id}/items/{item_ids[i]}"
                item_data = self.place_request("GET", url)

                # get ean/price/simpleid from article id
                item_code = item_data['data']['attributes']['article_id']         
                item_ean = self.get_ean(item_code)

                try:
                    # price in order and eans in order
                    price = item_ean['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples'][0]['offers'][0]['price']['regular_price']['amount']
                    item_ean = item_ean['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples'][0]['ean']
                
                except:  # when get_ean request failure
                    item_ean = "Nie mozna wczytac eanu"
                    price = "0"

                # add record to list of order
                order_details['orders'].append(
                    {
                        f"{i+1}": {
                            # order details contains detail, id details contains all necessary ids and order number
                            "order_details":{
                                "article_id": item_data['data']['attributes']['article_id'],
                                "description": item_data['data']['attributes']['description'],
                                "quantity_shipped": item_data['data']['attributes']['quantity_shipped'],
                                "quantity_returned": item_data['data']['attributes']['quantity_returned'],
                                "ean": f"{item_ean}",
                                "price": f"{price}",
                            },
                            "id_details":{
                                "order_id": order_id,
                                "order_line_id": orders_data['included'][i]['attributes']['order_line_id'],
                                "order_item_id": orders_data['included'][i]['attributes']['order_item_id'],
                                "order_number": order_number,
                                }  
                            }
                        }           
                    )
            return order_details  # will return list of dict specified above

    # order_data = takes get_details_of_order(), reasons are specified in html file
    def update_status_to_returned(self, order_data, reason=0):
        order_id = order_data["order_id"]
        line_id = order_data["order_line_id"]
        item_id = order_data["order_item_id"]
        order_number = order_data["order_number"]

        payload = {
                    "data":{
                    "id": line_id,
                    "type":"OrderLine",
                    "attributes":{
                      "status":"returned",
                      "reason": reason
                        }
                     }
                  }
        url = "/merchants/{merchant_id}"+f"/orders/{order_id}/items/{item_id}/lines/{line_id}"
        # request to set status of items in order to "returned"
        r = self.place_request("PATCH", url, payload)
        if r.ok:
            mess = f"[{order_number}]Status poprawnie zaktualizowany na Returned"
            print(mess)
            return mess
        else:
            mess = f"[{order_number}]Cos poszlo nie tak i nie udalo sie zaktualizowac statusu. Sprobuj jeszcze raz."
            print(mess)
            return mess

    # update labels and status of order
    def update_tracking(self, order_number, tracking_number, return_tracking_number, status):
        data = self.get_orders(0, 1, "newest", order_number)
        order_id = data['data'][0]['id']

        link = '/merchants/{merchant_id}/orders'+f'/{order_id}'

        payload = {
                   "data":{
                     "type":"Order",
                     "id": f"{order_id}",
                     "attributes":{
                       "tracking_number": f"{tracking_number}",
                       "return_tracking_number":f"{return_tracking_number}"
                     }
                   }
                 }
        r = self.place_request("PATCH", link, payload) # add tracking

        if status != "": # when user want to add trackings AND change status
            time.sleep(5)  # from zalando documentation
            result = self.get_details_of_order(data, True)  # loads details of order from given data set

            for i, v in enumerate(result["orders"]):
                order_id = result["orders"][i][str(i+1)]["id_details"]["order_id"]
                line_id = result["orders"][i][str(i+1)]["id_details"]["order_line_id"]
                item_id = result["orders"][i][str(i+1)]["id_details"]["order_item_id"]
                order_number = result["orders"][i][str(i+1)]["id_details"]["order_number"]

                link = '/merchants/{merchant_id}/orders'+f'/{order_id}/items/{item_id}/lines/{line_id}'
                payload = {
                      "data": {
                        "id": line_id,
                        "type": "OrderLine",
                        "attributes": {
                          "status": f"{status}"
                        }
                      }
                    }
                r = self.place_request("PATCH", link, payload)  # set status
                return r
