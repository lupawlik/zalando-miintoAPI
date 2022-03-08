# contains all functions communicating with api zalando
import time
import datetime
from datetime import timedelta
from string import Template
import workers
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
        try:
            if not r['data']:
                return "NIE MA TAKIEGO ZAMOWIENIA"
            return r
        except:
            return "NIE MA TAKIEGO ZAMOWIENIA"

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

    # return order created after given date, used in zalando orders worker
    def get_order_to_date(self, date, status=None):
        date = date.strftime("%Y-%m-%dT%H:%M:%S")+"+01:00"
        print(date)
        # stores list of all data from all sites
        list_of_all_orders = []
        params={
            'page[size]': 1000,
            'created_after': date,
            'include': 'order_lines',
            }
        if status:
            params['order_status'] = status

        r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)
        list_of_all_orders.append(r)
        # check if request contains more than 1000 result if true, make another requests until all orders will be collected
        is_next_site = False
        next_site = 0
        if "next" in r['links']:
            # get next order number from url
            next_site = int(r['links']['next'][-1])
            is_next_site = True
            print(f"Wczytano: {next_site*1000} ofert")

        while is_next_site:
            time.sleep(1)
            params = {
                'page[size]': 1000,
                'created_after': date,
                'page[number]': next_site,
                'include': 'order_lines',
            }
            r = self.place_request("GET", "/merchants/{merchant_id}/orders", params)
            list_of_all_orders.append(r)
            if "next" in r['links']:
                # get next order number from url
                next_site += 1
                print(f"Wczytano: {next_site*1000} ofert")
            else:
                is_next_site = False
                print("Wczytano wszystko")

        try:
            return list_of_all_orders
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
                order_number = orders_data['data'][0]['attributes']['order_number']
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
                price = orders_data['included'][i]['attributes']['price']['amount']

                url = "/merchants/{merchant_id}"+f"/orders/{order_id}/items/{item_ids[i]}"
                item_data = self.place_request("GET", url)

                # get ean/price/simpleid from article id
                item_code = item_data['data']['attributes']['article_id']         
                item_ean = self.get_ean(item_code)

                try:
                    # price in order and eans in order
                    item_ean = item_ean['data']['psr']['product_models']['items'][0]['product_configs'][0]['product_simples'][0]['ean']
                
                except:  # when get_ean request failure
                    item_ean = "Nie mozna wczytac eanu"

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

            for index, item in enumerate(result["orders"]):
                    order_id = item[f"{index+1}"]["id_details"]["order_id"]
                    line_id = item[f"{index+1}"]["id_details"]["order_line_id"]
                    item_id = item[f"{index+1}"]["id_details"]["order_item_id"]
                    order_number = item[f"{index+1}"]["id_details"]["order_number"]
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
                    if index!=0:  # when is more then one product in order to update
                        time.sleep(5)
            return r

    # max ean update send in one request is 1000. When sending 1000 rate limit is 1 minute
    def set_quantity(self, list_of_eans, list_of_quantitys, sales_channel):
        # generate list of chunked listo of eans, max chunk = 1000
        def chunk_list(list, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(list), n):
                yield list[i:i + n]
        # create payload from list in params
        # loop is every 1000 eans

        # stores if is ean successfully changed quantity or not
        report_data = []
        chunked_list = list(chunk_list(list_of_eans, 999))
        for i in chunked_list:
            payload = {"items": []}
            # go for every ean in list and add data
            print(i)
            for j, v in enumerate(i):
                payload["items"].append(
                    {
                        "sales_channel_id": f"{sales_channel}",
                        "ean": f"{list_of_eans[j]}",
                        "quantity": f"{list_of_quantitys[j]}"
                    }
                )
            # updates ean with given quantity
            url = "/merchants/{merchant_id}" +"/stocks"
            r = dict(self.place_request("POST", url, payload))
            print(r)

            # get ean and status list and save in report_data
            # if code == 0, stock is changed
            for product in r['results']:
                if product['result']['code'] != 0:
                    report_data.append((product['item']['ean'], "FAILURE"))
                else:
                    report_data.append((product['item']['ean'], "ACCEPTED"))

            # wait 1 minute if is more than 1000 eans
            if len(list(chunked_list)) > 1:
                time.sleep(61)
        print("Successfully changed quantity")
        print(report_data)
        workers.del_from_list("ZerowanieIlosciZalando")
        return report_data

