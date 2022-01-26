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

        if not r['data']:
            return "NIE MA TAKIEGO ZAMOWIENIA"
        return r

    # return all orders with "approved" status
    def get_approved_orders(self):
        params = {
            'page[size]': 1000,
            'sort': 'order_date',
            'order_status': 'Approved',
            'include': 'order_lines',
            }
        r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)
        if not r['data']:
            return "NIE MA TAKIEGO ZAMOWIENIA"
        return r

    # return order from last hour, used in zalando orders worker
    def get_last_hour_orders(self):
        now = (datetime.datetime.now() - timedelta(hours=2)).replace(microsecond=0).isoformat()  # get time -2 hours
        now = str(now)+"Z"
        params={
            'page[size]': 1000,
            'created_after': now,
            }

        r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)
        #print(f'Wyszukiwanie zamowien, request status: {r.reason}')
        try:
            return r
        except:
            return 0

    # take
    def get_all_product_by_one_ean(self, ean):
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
        query = query_template.substitute(item=ean, merchant_id=self.merchant_id)
        params = {'query': query}
        r = self.place_request("POST", "/graphql", params)
        if not r['data']['psr']['product_models']['items']:
            return ""
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
        r = r['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples']
        final_data = []
        for product in r:
            final_data.append(product)
        return final_data

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
        query = query_template.substitute(item=product_code, merchant_id=self.merchant_id)
        params = {'query': query}
        r = self.place_request("POST", "/graphql", params)
        return r

    def get_details_of_order(self, order_number, from_data=False):

            if not from_data:
                orders_data = self.get_orders(0, 1, "newest", order_number)
            elif from_data:
                orders_data = order_number  # if user pass as parameter order information
            if orders_data == 'NIE MA TAKIEGO ZAMOWIENIA':
                return 'NIE MA TAKIEGO ZAMOWIENIA'

            order_id = orders_data['data'][0]['id']

            item_lines_ids = []
            item_ids = []
            order_details = {"orders":[]}
            for i in range(len(orders_data['included'])):
                item_lines_ids.append(orders_data['included'][i]['attributes']['order_line_id'])
                item_ids.append(orders_data['included'][i]['attributes']['order_item_id'])
                
                url = "/merchants/{merchant_id}"+f"/orders/{order_id}/items/{item_ids[i]}"
                item_data = self.place_request("GET", url)

                item_code = item_data['data']['attributes']['article_id']         
                item_ean = self.get_ean(item_code)

                try:
                    price = item_ean['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples'][0]['offers'][0]['price']['regular_price']['amount']
                    item_ean = item_ean['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples'][0]['ean']
                
                except:
                    item_ean = "Nie mozna wczytac eanu"
                    price = "0"
                order_details['orders'].append(
                    {
                        f"{i+1}": {
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
            return order_details

    def update_status_to_returned(self, order_data, reason=0): #takes get_details_of_order() datas
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

        r = self.place_request("PATCH", url, payload)
        if r.ok:
            mess = f"[{order_number}]Status poprawnie zaktualizowany na Returned"
            print(mess)
            return mess
        else:
            mess = f"[{order_number}]Cos poszlo nie tak i nie udalo sie zaktualizowac statusu. Sprobuj jeszcze raz."
            print(mess)
            return mess

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
        r = self.place_request("PATCH", link, payload)

        if status != "":
            time.sleep(5)  # from zalando documentation
            result = self.get_details_of_order(data, True)
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
                r = self.place_request("PATCH", link, payload)
                print(r)
