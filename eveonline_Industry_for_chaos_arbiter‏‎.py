# coding:utf-8
import wx,traceback
import wx.grid
import os, datetime, time, threading, pathlib,sys
import pandas as pd
import numpy as np
import random,datetime
import requests,urllib
import json,xmltodict,yaml


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', 200)
pd.set_option('display.width', 280)

class EVEonline:
    itemlist_filepath = 'd:/eve_data/typeids.csv'
    blueprint_filepath = 'd:/eve_data/blueprints.yaml'
    typeids_filepath = 'd:/eve_data/s_typeIDs.yaml'
    watchlist_filepath = 'd:/eve_data/watchlist.csv'
    prices={}
    watchlist=None
    productlist=None
    costs={}
    win=None
    itemlist=None
    buleprints=None
    user_buleprints={}
    inventions={}
    typeids=None
    productitems=None
    dashboard = {}
    materials_region = 'Jita'
    manufacture_region='Josameto'
    tax = 0.05
    


    region={'Jita':'30000142',
            'Perimeter':'30000144',
            'Amarr VIII':'30002187',
            'Dodixie':'60011866',
            'Rens':'60004588',
            'Hek':'60005686',
            'Josameto':'30000156',
            '4-HWWF':'30000240'
            }
    region_area={'Jita':'10000002','Amarr VIII':'10000043','4-HWWF':'10000003'}

    def __init__(self,win):
        self.window = win
        self.load_watchlist()
    
    def load_watchlist(self):
        if os.path.exists(self.watchlist_filepath):
            self.watchlist = pd.read_csv(self.watchlist_filepath, index_col=0)
       
    
    def save_watchlist(self):
        self.watchlist.to_csv(self.watchlist_filepath)

    def add_watchlist(self,id):
        self.check_init()
        ids = []
        ids.append(id)
        buleprints=self.fetch_buleprint_by_product_ids(ids)
        rs = self.analysis_buleprints(buleprints,True)
        self.watchlist = pd.concat([self.watchlist,rs], ignore_index=True)
        self.save_watchlist()
        self.flush_watchlist('ALL','profit_pre_day')

    def reflush_watchlist(self):
        self.check_init()
        ids=[]
        if self.watchlist.shape[0]>0:
            for index,r in self.watchlist.iterrows():
                ids.append(r['product_id'])
            print('reflush_watchlist:ids->',ids)
            buleprints=self.fetch_buleprint_by_product_ids(ids)
            rs = self.analysis_buleprints(buleprints,True)
            if rs.shape[0]>0:
                self.watchlist = rs
                self.save_watchlist()
                self.flush_watchlist('ALL','profit_pre_day')


    
    def data_init(self):
        print('load_prices ')
        self.print_text('正在读取市场价格')
        self.load_prices()
        print('load_system_cost ')
        self.print_text('正在读取生产系数')
        self.load_system_cost()
        print('load_typeids ')
        self.print_text('正在读取物品列表')
        self.load_typeids()
        print('load_buleprints ')
        self.print_text('正在读取蓝图列表')
        self.load_buleprints()
        print('process_buleprints ')
        self.print_text('正在处理蓝图数据')
        self.process_buleprints()
        print('load_market')
        self.print_text('正在读取市场数据')
        self.load_market(self.materials_region)
        print('process_products')
        self.print_text('正在处理产品列表')
        self.process_products()
    
    def print_text(self,text):
        self.window.SetStatusText(text)

    def fetch_orderbook(self,typeid,region):
        orderbooks={'buy':{},'sell':{}}
        region_area = self.region_area[region]
        region_id = self.region[region]
        headers = {'user-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        myurl = "https://esi.evetech.net/latest/markets/"+region_area+"/orders/?datasource=tranquility&order_type=all&page=1&type_id="+typeid
        req = urllib.request.Request(url = myurl,headers = headers)
        try:
            res = urllib.request.urlopen(req)
           
        except Exception as e:
            return '0'
        rs = res.read().decode('utf-8')
        rs = json.loads(rs)
        for r in rs:
            # if str(r['system_id'])!=region_id:
            #     continue
            if r['is_buy_order']:
                if orderbooks['buy'].__contains__(r['price']):
                    orderbooks['buy'][r['price']]+=int(r['volume_remain'])
                else:
                    orderbooks['buy'][r['price']]=int(r['volume_remain'])
            else:
                if orderbooks['sell'].__contains__(r['price']):
                    orderbooks['sell'][r['price']]+=int(r['volume_remain'])
                else:
                    orderbooks['sell'][r['price']]=int(r['volume_remain'])
        
        return orderbooks



    
    def load_prices(self):
        headers = {'user-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        myurl = "https://esi.evetech.net/latest/markets/prices/?datasource=tranquility"
        req = urllib.request.Request(url = myurl,headers = headers)
        try:
            res = urllib.request.urlopen(req)
           
        except Exception as e:
            return '0'
        rs = res.read().decode('utf-8')
        rs = json.loads(rs)
        for r in rs:
            try:
                self.prices[str(r['type_id'])] = r['average_price']
            except Exception as e:
                print('wronging at load_prices:',r)
                continue
    
    def load_system_cost(self):
        headers = {'user-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        myurl = "https://esi.evetech.net/latest/industry/systems/?datasource=tranquility"
        req = urllib.request.Request(url = myurl,headers = headers)
        try:
            res = urllib.request.urlopen(req)
           
        except Exception as e:
            return '0'
        rs = res.read().decode('utf-8')
        rs = json.loads(rs)
        for r in rs:
            try:
                cost_indices = r['cost_indices']
                cost=0
                for cost_indice in cost_indices:
                    if cost_indice['activity']=='manufacturing':
                        cost = cost_indice['cost_index']
                self.costs[str(r['solar_system_id'])] = float(cost)

            except Exception as e:
                print('wronging at load_system_cost:',r)
                continue
        # print(self.costs)


    def fetch_price(self,region,type_ids):
        priceset = {}
        if self.dashboard.__contains__(region) is False:
            self.dashboard[region]={}
        for type_id in type_ids:
            if self.dashboard[region].__contains__(type_id):
                priceset[type_id] =  self.dashboard[region][type_id]
            else:
                return self.fetch_price_online(region,type_ids)
        # print('use local data.............')
        return priceset

            



    def fetch_price_online(self,region,type_ids):
        headers = {'user-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        # myurl = "https://market.fuzzwork.co.uk/aggregates/?region="+self.region[region]+"&types=" + ",".join(type_ids)

        myurl = "https://api.evemarketer.com/ec/marketstat?typeid="+ ",".join(type_ids)+"&&usesystem=" +self.region[region]
    
        req = urllib.request.Request(url = myurl,headers = headers)
        try:
            res = urllib.request.urlopen(req)
           
        except Exception as e:
            return '0'
        rs = res.read().decode('utf-8')
        rs = xmltodict.parse(rs)
        rs=rs['exec_api']['marketstat']['type']
        
        priceset = {}
        if isinstance(rs,dict):
            buy_price = float(rs['buy']['max'])
            buy_volume = int(rs['buy']['volume'])
            sell_price =  float(rs['sell']['min'])
            sell_volume = int(rs['sell']['volume'])
            if self.dashboard.__contains__(region) is False:
                self.dashboard[region]={}
            self.dashboard[region][rs['@id']]={'buy_price':buy_price,'buy_volume':buy_volume,'sell_price':sell_price,'sell_volume':sell_volume}
            priceset[rs['@id']]={'buy_price':buy_price,'buy_volume':buy_volume,'sell_price':sell_price,'sell_volume':sell_volume}
            return priceset

        for r in rs:
            buy_price = float(r['buy']['max'])
            buy_volume = int(r['buy']['volume'])
            sell_price =  float(r['sell']['min'])
            sell_volume = int(r['sell']['volume'])
            if self.dashboard.__contains__(region) is False:
                self.dashboard[region]={}
            self.dashboard[region][r['@id']]={'buy_price':buy_price,'buy_volume':buy_volume,'sell_price':sell_price,'sell_volume':sell_volume}
            priceset[r['@id']]={'buy_price':buy_price,'buy_volume':buy_volume,'sell_price':sell_price,'sell_volume':sell_volume}


        return priceset
    def load_itemlist(self):
        self.itemlist = pd.read_csv(self.itemlist_filepath, index_col=0)
    
    def load_buleprints(self):
        with open(self.blueprint_filepath,mode='r',encoding='utf-8') as file:
            self.buleprints = yaml.safe_load(file)
    
   
    def load_typeids(self):
        with open(self.typeids_filepath,mode='r',encoding='utf-8') as file:
            self.typeids = yaml.safe_load(file)

    def fetch_buleprint_by_product_ids(self,pids):
        self.check_init()
        s_buleprints = {}
        for id in self.buleprints.keys():
            if self.buleprints[id]['activities'].__contains__('manufacturing') is False:
                continue
            if self.buleprints[id]['activities']['manufacturing'].__contains__('products') is False:
                continue
            product = self.buleprints[id]['activities']['manufacturing']['products'][0]
            product_id = str(product['typeID'])
            for pid in pids:
                if pid==product_id:
                    s_buleprints[id] = self.buleprints[id]

                
        return s_buleprints

    def process_buleprints(self):
        for id in self.buleprints.keys():
           
            items_ids=[]
            try:
                if self.buleprints[id]['activities'].__contains__('manufacturing') is False:
                    continue
                if self.buleprints[id]['activities']['manufacturing'].__contains__('materials') is False:
                    continue
                product = self.buleprints[id]['activities']['manufacturing']['products'][0]
                product_id = str(product['typeID'])
                if self.typeids.__contains__(product_id) is False:
                    continue
                product_ids = self.typeids[product_id]
                product_name = product_ids['name']['zh']
                
                if product_ids.__contains__('metaGroupID'):
                    product_metaGroupID = product_ids['metaGroupID']
                    # if product_metaGroupID>2:
                    #     continue
                    if product_metaGroupID!=2:
                        if self.prices.__contains__(str(id)) is False:
                            print(product_name,' is out')
                            continue
                

                else:
                    if self.prices.__contains__(str(id)) is False:
                        print(product_name,' is out')
                        continue

                self.user_buleprints[id] = self.buleprints[id]
                if self.buleprints[id]['activities'].__contains__('invention'):
                    invention = self.buleprints[id]['activities']['invention']['products'][0]
                    self.inventions[invention['typeID']] = self.buleprints[id]

                

            except Exception as e:
                print(e,'process_buleprints')
                traceback.print_exc()
                continue
    
    def load_market(self,region):
        
        items_ids={}
        for id in self.user_buleprints.keys():
            
            product = self.buleprints[id]['activities']['manufacturing']['products'][0]
            product_id = str(product['typeID'])
            product_ids = self.typeids[product_id]
            product_name = product_ids['name']['zh']
            materials = self.buleprints[id]['activities']['manufacturing']['materials']
            items_ids[product_id]=1
            for material in materials:
                material_id = str(material['typeID'])
                items_ids[material_id]=1
            if self.buleprints[id]['activities'].__contains__('invention'):
                try:
                    inv_materials = self.buleprints[id]['activities']['invention']['materials']
                    for inv_material in inv_materials:
                        inv_material_id = str(inv_material['typeID'])
                        items_ids[inv_material_id]=1
                except Exception as e:
                    print(product_name,e,'invention')
                    traceback.print_exc()
                    continue
        
        s_ids = []
        
        for sid in items_ids.keys():
            s_ids.append(sid)
            if len(s_ids)>150:
                
                self.fetch_price(region,s_ids)
                s_ids = []
        self.fetch_price(region,s_ids)

    def flush_watchlist(self,type,sort_by):
        if self.watchlist.shape[0]>0:
            data_list = self.window.tab_setting.strategys_list
            data_list.DeleteAllItems()
            data_csv = self.watchlist
            data_csv = data_csv.sort_values(by=sort_by,ascending=False)
            for i, r in data_csv.iterrows():

                if str(r['product_metaGroupID'])==type or type=='ALL':
                    index = data_list.InsertItem(data_list.GetItemCount(), '') 
                    data_list.SetItem(index, 0, str(r['product_id']))
                    data_list.SetItem(index, 1, r['product_name'])
                    data_list.SetItem(index, 2, str(r['product_metaGroupID']))
                    data_list.SetItem(index, 3, str('{:20,}'.format(r['product_price'])))   
                    data_list.SetItem(index, 4, str(r['product_time']))
                    data_list.SetItem(index, 5, str('{:20,}'.format(r['material_total'])))
                    data_list.SetItem(index, 6, str(r['profit_rate']))
                    data_list.SetItem(index, 7, str('{:20,}'.format(r['profit_pre_day'])))  
                    data_list.SetItem(index, 8, str('{:20,}'.format(r['full_eff_material_total'])))
                    data_list.SetItem(index, 9, str(r['full_eff_profit_rate']))
                    data_list.SetItem(index, 10, str('{:20,}'.format(r['full_eff_profit_pre_day'])))  
                    data_list.SetItem(index, 11, str('{:20,}'.format(r['product_cost'])))
                    data_list.SetItem(index, 12, str('{:20,}'.format(r['invent_cost'])))

                    data_list.SetItem(index, 13, str(r['order_volumn']))
                    data_list.SetItem(index, 14, str('{:20,}'.format(r['orders_profit'])))
                    data_list.SetItem(index, 15, str(r['eff_full_order_volumn']))
                    data_list.SetItem(index, 16, str('{:20,}'.format(r['eff_full_orders_profit'])))
                    data_list.SetItem(index, 17, str(r['isRecount']))
                    data_list.SetItem(index, 18, str(r['update_time']))
            
    def flush_productlist(self,type,sort_by):
        data_list = self.window.tab_main.strategys_list
        data_list.DeleteAllItems()
        data_csv = self.productlist
        data_csv = data_csv.sort_values(by=sort_by,ascending=False)
        for i, r in data_csv.iterrows():

            if str(r['product_metaGroupID'])==type or type=='ALL':
                index = data_list.InsertItem(data_list.GetItemCount(), '') 
                data_list.SetItem(index, 0, str(r['product_id']))
                data_list.SetItem(index, 1, r['product_name'])
                data_list.SetItem(index, 2, str(r['product_metaGroupID']))
                data_list.SetItem(index, 3, str('{:20,}'.format(r['product_price'])))  
                data_list.SetItem(index, 4, str(r['product_time']))
                data_list.SetItem(index, 5, str('{:20,}'.format(r['material_total'])))
                data_list.SetItem(index, 6, str(r['profit_rate']))
                data_list.SetItem(index, 7, str('{:20,}'.format(r['profit_pre_day'])))  
                data_list.SetItem(index, 8, str('{:20,}'.format(r['full_eff_material_total'])))
                data_list.SetItem(index, 9, str(r['full_eff_profit_rate']))
                data_list.SetItem(index, 10, str('{:20,}'.format(r['full_eff_profit_pre_day'])))
                data_list.SetItem(index, 11, str('{:20,}'.format(r['product_cost'])))
                data_list.SetItem(index, 12, str('{:20,}'.format(r['invent_cost'])))
                data_list.SetItem(index, 13, str(r['isRecount']))
        
        

   

    def analysis_buleprints_new(self):
        
        if self.buleprints is None:
            self.data_init()
        
        data_csv =  self.analysis_buleprints(self.user_buleprints,False)
        self.productlist = data_csv
        self.flush_productlist('ALL','profit_pre_day')
        
        
        
        
    def check_init(self):
        if self.buleprints is None:
            self.data_init()
    
    def process_products(self):
        items_ids={}
        for id in self.buleprints.keys():
            try:
                if self.buleprints[id]['activities'].__contains__('manufacturing') is False:
                    continue
                if self.buleprints[id]['activities']['manufacturing'].__contains__('materials') is False:
                    continue
                if self.buleprints[id]['activities']['manufacturing'].__contains__('products') is False:
                    continue
                product = self.buleprints[id]['activities']['manufacturing']['products'][0]
                product_id = str(product['typeID'])
                items_ids[product_id] = self.buleprints[id]
            except Exception as e:
                print(e)
                traceback.print_exc()
        self.productitems = items_ids
        

    def account_materials_value_by_product(self,pid,prices):
       
        # product_name = self.typeids[pid]['name']['zh']
       
        material_total=0
        full_eff_material_total=0
        isRecount=False
        if  self.productitems[pid]['activities'].__contains__('manufacturing'):
            
            
            materials = self.productitems[pid]['activities']['manufacturing']['materials']
            
            for material in materials:
                material_id = str(material['typeID'])
                if prices.__contains__(material_id) is False:
                    items_ids=[]
                    items_ids.append(material_id)
                    m_prices = self.fetch_price(self.materials_region,items_ids)
                    prices[material_id] = m_prices[material_id]
                material_price = prices[material_id]['sell_price']
                material_quantity = int(material['quantity'])
                full_eff_material =  material_price
                
                
                if self.productitems.__contains__(material_id):
                    
                    r_material_price , r_full_eff_material,isRecount= self.account_materials_value_by_product(material_id,prices)
                    if r_material_price<material_price:
                        material_price = r_material_price
                        full_eff_material = r_full_eff_material
                        isRecount=True

                if  material_price==0:
                    
                    return prices[pid]['sell_price']*material_quantity,prices[pid]['sell_price']*material_quantity,isRecount
                
                material_value = material_price*material_quantity
                material_total=material_total+material_value
                full_eff_material_quantity = material_quantity%10+material_quantity//10*9
                full_eff_material_value = full_eff_material*full_eff_material_quantity
                full_eff_material_total=full_eff_material_total+full_eff_material_value
            return material_total,full_eff_material_total,isRecount
        else:
            return prices[pid]['sell_price']*material_quantity,prices[pid]['sell_price']*material_quantity,isRecount

    def analysis_buleprints(self,t_buleprints,is_order):
       
        self.check_init()
        records = pd.DataFrame()
        cost_rate = float(self.costs[self.region[self.manufacture_region]])
        process_total=len(t_buleprints)
        process_number=0
        for id in t_buleprints.keys():
            process_number+=1
            items_ids=[]
            try:
                # if self.buleprints[id]['activities'].__contains__('manufacturing') is False:
                #     continue
                product_time = int(self.buleprints[id]['activities']['manufacturing']['time'])
                
                product = self.buleprints[id]['activities']['manufacturing']['products'][0]
                product_id = str(product['typeID'])

                product_ave_price=9999999999999
                if self.prices.__contains__(product_id):
                    product_ave_price = float(self.prices[product_id])
                else:
                    continue
                    print('worng at product_id not in product_ave_price:',product_id)
                
                product_ids = self.typeids[product_id]
                product_name = product_ids['name']['zh']
                product_metaGroupID=0
                product_cost = cost_rate*product_ave_price

              
                product_quantity = int(product['quantity'])
                materials = self.buleprints[id]['activities']['manufacturing']['materials']
                items_ids.append(product_id)
                for material in materials:
                    material_id = str(material['typeID'])
                    items_ids.append(material_id)
                

                
                prices = self.fetch_price(self.materials_region,items_ids)
                product_price = prices[product_id]['buy_price']
                
                product_value = product_price*product_quantity
                if product_price==0:
                    continue
                
                
                material_total,full_eff_material_total,isRecount=self.account_materials_value_by_product(product_id,prices)
                # material_total=0
                # full_eff_material_total=0
                # for material in materials:
                #     material_id = str(material['typeID'])
                #     material_price = prices[material_id]['sell_price']
                #     material_quantity = int(material['quantity'])
                #     if material_price==0:
                #         continue

                #     material_value = material_price*material_quantity
                #     material_total=material_total+material_value
                #     full_eff_material_quantity = material_quantity%10+material_quantity//10*9
                #     full_eff_material_value = material_price*full_eff_material_quantity
                #     full_eff_material_total=full_eff_material_total+full_eff_material_value

                    # print('id:',material['typeID'],'  material_price:',material_price,'   material_quantity:',material_quantity,'   material_value:',material_value)
                product_metaGroupID=1
                if product_ids.__contains__('metaGroupID'):
                    product_metaGroupID = product_ids['metaGroupID']
                invent_cost=0    
                if product_metaGroupID==2:
                    if self.inventions.__contains__(id) is False:
                        continue
                    invent = self.inventions[id]
                    i_materials = invent['activities']['invention']['materials']
                    i_product_quantity = invent['activities']['invention']['products'][0]['quantity']
                    i_material_total=0
                    for i_material in i_materials:
                        i_material_id = str(i_material['typeID'])
                        
                        i_ids = []
                        i_ids.append(i_material_id)
                        i_prices = self.fetch_price(self.materials_region,i_ids)
                        i_material_price = i_prices[i_material_id]['sell_price']
                        i_material_quantity = int(i_material['quantity'])
                        if i_material_price==0:
                            material_price=999999999
                        i_material_value = i_material_price*i_material_quantity
                        i_material_total=i_material_total+i_material_value
                    invent_cost = i_material_total*3/i_product_quantity
                    

                   

                
                profit =  product_value*(1-self.tax)-material_total-product_cost*product_quantity-invent_cost
                full_eff_profit = (product_value*(1-self.tax)-full_eff_material_total-product_cost*product_quantity)*1.4-invent_cost
                
                # print('id:',id,'  product_value:',product_value,'  material_total:',material_total,'  profit:',profit)
                self.print_text('['+str(process_number)+'/'+str(process_total)+']正在处理：'+product_name,)
                if full_eff_profit>0 or True:
                    profit_rate = profit/material_total
                    profit_pre_time = profit/product_time

                    full_eff_profit_rate = full_eff_profit/full_eff_material_total
                    full_eff_profit_pre_time = full_eff_profit/product_time


                    is_full_working = False
                    full_working_time=60*60*24
                    working_time = 0

                    is_full_working_full_eff = False
                    working_time_full_eff = 0

                    orders_profit = 0
                    eff_full_orders_profit = 0

                    order_volumn = 0
                    eff_full_order_volumn = 0
                    full_working_days = 0
                    full_working_days_full_eff = 0
                    profit_pre_day = profit_pre_time*full_working_time
                    full_eff_profit_pre_day = full_eff_profit_pre_time*full_working_time
                    
                    if is_order:
                        obooks = self.fetch_orderbook(product_id,self.materials_region)
                        buy_books = pd.DataFrame(list(obooks['buy'].items()),columns=['price','volumn'])
                        buy_books = buy_books.sort_values(by='price',ascending=False)
                        

                        for index, book in buy_books.iterrows():
                            o_price = book['price']
                            o_volumn = book['volumn']
                            if o_price*(1-self.tax)-invent_cost>full_eff_material_total:
                                eff_full_order_volumn+=o_volumn
                                o_working_time = o_volumn*product_time
                                working_time_full_eff+=o_working_time
                                eff_full_orders_profit+=((o_price*(1-self.tax)-invent_cost)-full_eff_material_total)*o_volumn
                                if o_price*(1-self.tax)-invent_cost>material_total:
                                    order_volumn+=o_volumn
                                    working_time+=o_working_time
                                    orders_profit+=((o_price*(1-self.tax)-invent_cost)-material_total)*o_volumn

                            if full_working_time<working_time:
                                is_full_working=True

                            if is_full_working_full_eff<working_time_full_eff:
                                is_full_working_full_eff=True
                            
                            if product_metaGroupID==2:
                                full_eff_material_total = material_total
                                full_eff_profit = profit
                                full_eff_profit_rate = profit_rate
                                full_eff_profit_pre_time = profit_pre_time
                                full_eff_profit_pre_day =profit_pre_day

                        
                        full_working_days = working_time/full_working_time
                        full_working_days_full_eff = working_time_full_eff/full_working_time
                        profit_pre_day = profit_pre_time*60*60*24
                        full_eff_profit_pre_day = full_eff_profit_pre_time*60*60*24
                     

                    record = pd.DataFrame(
                                    {'buleprint_id': id, 'product_id': product_id, 'product_name': product_name, 'product_cost': int(product_cost), 'invent_cost': int(invent_cost), 'isRecount': isRecount, 
                                    'product_price': int(product_price),'product_quantity': product_quantity,'product_value': int(product_value), 'material_total': int(material_total),
                                    'profit': profit,'profit_rate': profit_rate//0.01/100,'product_time': product_time,'profit_pre_time': profit_pre_time,'profit_pre_day': int(profit_pre_day),
                                    'full_eff_material_total': int(full_eff_material_total),'full_eff_profit': int(full_eff_profit),'full_eff_profit_rate': full_eff_profit_rate//0.01/100,'full_eff_profit_pre_time': full_eff_profit_pre_time,'full_eff_profit_pre_day': int(full_eff_profit_pre_day),
                                    'is_full_working': is_full_working,'order_volumn': order_volumn,'orders_profit': int(orders_profit),'full_working_days': full_working_days,
                                    'is_full_working_full_eff': is_full_working_full_eff,'eff_full_order_volumn': int(eff_full_order_volumn),'eff_full_orders_profit': int(eff_full_orders_profit),'full_working_days_full_eff': full_working_days_full_eff,
                                    'product_metaGroupID': product_metaGroupID,'update_time': datetime.datetime.now().strftime('%Y-%m-%d')
                                    },index=[1])
                    # print(record)
                    records = pd.concat([records,record], ignore_index=True)
                
            except Exception as e:
                print(type(e),e.with_traceback,'analysis_buleprints')
                traceback.print_exc()
                continue
        
        records.to_csv('d:/eve_industry_'+self.materials_region+datetime.datetime.now().strftime('%Y-%m-%d')+'.csv')
        self.print_text('所有数据处理完成！',)
        return records
               





# eve.analysis_buleprints('Jita',0.05)



class CryptoFrame(wx.Frame):
    

    def __init__(self, *args, **kw):
        super(CryptoFrame, self).__init__(*args, **kw)
        self.eve = EVEonline(self)
        self.notebook = wx.Notebook(self)
        self.notebook.main = self
        # create a panel in the frameF
        self.tab_main = tabMain(self.notebook)
        self.notebook.AddPage(self.tab_main, '制造产品列表')

        self.tab_setting = tabSetting(self.notebook)
        self.notebook.AddPage(self.tab_setting, '制造关注列表')
        
        self.CreateStatusBar()
        self.SetStatusText("The System is Stop!")
        
class tabMain(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        
      
        
        
        
       
        
        
        self.strategys_box = wx.BoxSizer(wx.HORIZONTAL)

        self.strategys_list = wx.ListCtrl(self, -1, style = wx.LC_REPORT,size=(2200, 1000))
        self.strategys_box.Add(self.strategys_list, 0, flag=wx.EXPAND | wx.ALL, border=5)
        
        self.strategys_list.InsertColumn(0, 'ID', wx.LIST_FORMAT_RIGHT, width = 60)
        self.strategys_list.InsertColumn(1, '产品名称', wx.LIST_FORMAT_LEFT, width = 300)
        self.strategys_list.InsertColumn(2, '等级', wx.LIST_FORMAT_RIGHT, width = 50)
        self.strategys_list.InsertColumn(3, '销售价', wx.LIST_FORMAT_RIGHT, width = 200)
        self.strategys_list.InsertColumn(4, '生产时间(秒)', wx.LIST_FORMAT_LEFT, width = 100)
        self.strategys_list.InsertColumn(5, '材料成本', wx.LIST_FORMAT_RIGHT, width = 200)
        self.strategys_list.InsertColumn(6, '利润率', wx.LIST_FORMAT_RIGHT, width = 70)
        self.strategys_list.InsertColumn(7, '普通日收益', wx.LIST_FORMAT_RIGHT, width = 200)
        self.strategys_list.InsertColumn(8, 'FE材料成本', wx.LIST_FORMAT_RIGHT, width = 200)
        self.strategys_list.InsertColumn(9, 'FE利润率', wx.LIST_FORMAT_LEFT, width = 100)
        self.strategys_list.InsertColumn(10, 'FE日收益', wx.LIST_FORMAT_RIGHT, width = 200)
        self.strategys_list.InsertColumn(11, '生产费用', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(12, '研发成本', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(13, '分解', wx.LIST_FORMAT_LEFT, width = 100)
        
        
        
        for i in range(0,100):
            index = self.strategys_list.InsertItem(self.strategys_list.GetItemCount(), '')
            self.strategys_list.SetItem(index, 0, '')
            self.strategys_list.SetItem(index, 1, '')
            self.strategys_list.SetItem(index, 2, '')
            self.strategys_list.SetItem(index, 3, '')
            self.strategys_list.SetItem(index, 4, '')
            self.strategys_list.SetItem(index, 5, '')
            self.strategys_list.SetItem(index, 6, '')
            self.strategys_list.SetItem(index, 7, '')
            self.strategys_list.SetItem(index, 8, '')
        
       

            
            
       
        
       
        
        
        
        
        self.operate_box2 = wx.BoxSizer(wx.HORIZONTAL)

        self.realtrade_checkbox = wx.CheckBox(self, label='只显示1级', style=wx.ALIGN_CENTER)
        self.operate_box2.Add(self.realtrade_checkbox, 0, flag=wx.EXPAND | wx.ALL, border=5)
        
        self.enable_records_checkbox = wx.CheckBox(self, label='只显示2级', style=wx.ALIGN_CENTER)
        self.operate_box2.Add(self.enable_records_checkbox, 0, flag=wx.EXPAND | wx.ALL, border=5)

        self.name_input = wx.TextCtrl(self)
        self.operate_box2.Add(self.name_input, 0, flag=wx.EXPAND | wx.ALL, border=5)
        
      
        self.start_btn = wx.Button(self, label='刷新全部产品')
        self.operate_box2.Add(self.start_btn, 1, flag=wx.EXPAND | wx.ALL, border=5)

        self.stop_btn = wx.Button(self, label='加入关注')
        self.operate_box2.Add(self.stop_btn, 1, flag=wx.EXPAND | wx.ALL, border=5)
        
       
        
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.sizer.Add(self.strategys_box, 0, wx.ALL | wx.EXPAND, 5)
        # self.sizer.Add(self.record_box, 0, wx.ALL | wx.EXPAND, 5)
        self.sizer.Add(self.operate_box2, 0, wx.ALL | wx.EXPAND, 5)
        # self.sizer.Add(self.system_info_box, 0, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(self.sizer)
        self.Bind(wx.EVT_BUTTON, self.on_system_start, self.start_btn)
        self.Bind(wx.EVT_BUTTON, self.on_system_stop, self.stop_btn)
        self.Bind(wx.EVT_CHECKBOX, self.set_info, self.enable_records_checkbox)
        self.Bind(wx.EVT_CHECKBOX, self.set_realtrade, self.realtrade_checkbox)
        self.strategys_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.data_choose)
        
        
    def set_info(self, event):
        type='ALL'
        if self.enable_records_checkbox.Value:
            type='2'
            self.realtrade_checkbox.Value=False
        
       
        if self.parent.main.eve.productlist is None:
            self.parent.main.SetStatusText("无产品列表数据")
        else:
            self.parent.main.eve.flush_productlist(type,'profit_pre_day')
        
    def set_realtrade(self, event):
        type='ALL'
       
        if self.realtrade_checkbox.Value:
            type='1'
            self.enable_records_checkbox.Value=False
        
        if self.parent.main.eve.productlist is None:
            self.parent.main.SetStatusText("无产品列表数据")
        else:
            self.parent.main.eve.flush_productlist(type,'full_eff_profit_pre_day')
    
    def on_system_start(self, event):
        # data_csv = self.parent.main.eve.analysis_buleprints('Jita','',0.05)

       


        self.parent.main.SetStatusText("The System is Start!")
        # self.parent.main.regent.TRADE_FLAG = True 
        threading.Thread(target=self.parent.main.eve.analysis_buleprints_new).start()
        
    def on_system_stop(self, event):
        itemcount = self.strategys_list.GetItemCount()
        selected_index = 0
        for i in range(0, itemcount):
            if self.strategys_list.IsSelected(i):
                selected_index = i
                break
        if selected_index==0:
            self.parent.main.SetStatusText("请选中一个列表中的产品")
        else:
            id = self.strategys_list.GetItem(selected_index, 0).GetText()
            self.parent.main.eve.add_watchlist(id)

    def data_choose(self, event):
        itemcount = self.strategys_list.GetItemCount()
        selected_index = 0
        for i in range(0, itemcount):
            if self.strategys_list.IsSelected(i):
                selected_index = i
                break
        if selected_index==0:
            self.parent.main.SetStatusText("请选中一个列表中的产品")
        else:
            name = self.strategys_list.GetItem(selected_index, 1).GetText()
            self.name_input.Value = name  



    
  
        
      
class tabSetting(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.parent = parent
        self.strategys_box = wx.BoxSizer(wx.HORIZONTAL)

        self.strategys_list = wx.ListCtrl(self, -1, style = wx.LC_REPORT,size=(2200, 1000))
        self.strategys_list.InsertColumn(0, 'ID', wx.LIST_FORMAT_RIGHT, width = 60)
        self.strategys_list.InsertColumn(1, '产品名称', wx.LIST_FORMAT_LEFT, width = 220)
        self.strategys_list.InsertColumn(2, '等级', wx.LIST_FORMAT_RIGHT, width = 50)
        self.strategys_list.InsertColumn(3, '销售价', wx.LIST_FORMAT_RIGHT, width = 130)
        self.strategys_list.InsertColumn(4, '生产时间(秒)', wx.LIST_FORMAT_RIGHT, width = 100)
        self.strategys_list.InsertColumn(5, '材料成本', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(6, '利润率', wx.LIST_FORMAT_RIGHT, width = 70)
        self.strategys_list.InsertColumn(7, '普通日收益', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(8, 'FE材料成本', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(9, 'FE利润率', wx.LIST_FORMAT_RIGHT, width = 100)
        self.strategys_list.InsertColumn(10, 'FE日收益', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(11, '生产费用', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(12, '研发成本', wx.LIST_FORMAT_RIGHT, width = 130)
        self.strategys_list.InsertColumn(13, '订单数', wx.LIST_FORMAT_RIGHT, width = 100)
        self.strategys_list.InsertColumn(14, '订单利润', wx.LIST_FORMAT_RIGHT, width = 100)
        self.strategys_list.InsertColumn(15, 'FE订单数', wx.LIST_FORMAT_RIGHT, width = 100)
        self.strategys_list.InsertColumn(16, 'FE订单利润', wx.LIST_FORMAT_RIGHT, width = 150)
        self.strategys_list.InsertColumn(17, '分解', wx.LIST_FORMAT_LEFT, width = 50)
        self.strategys_list.InsertColumn(18, '更新时间', wx.LIST_FORMAT_RIGHT, width = 100)
       
        for i in range(0,5):
            index = self.strategys_list.InsertItem(self.strategys_list.GetItemCount(), '')
            self.strategys_list.SetItem(index, 1, '')
            self.strategys_list.SetItem(index, 2, '')
            self.strategys_list.SetItem(index, 3, '')
            self.strategys_list.SetItem(index, 4, '')
            self.strategys_list.SetItem(index, 5, '')
            self.strategys_list.SetItem(index, 6, '')
            self.strategys_list.SetItem(index, 7, '')
            self.strategys_list.SetItem(index, 8, '')
            self.strategys_list.SetItem(index, 9, '')
            self.strategys_list.SetItem(index, 10, '')
        self.flush_watchlist('ALL','profit_pre_day')
        

       
        self.operate_box2 = wx.BoxSizer(wx.HORIZONTAL)

        self.realtrade_checkbox = wx.CheckBox(self, label='只显示1级', style=wx.ALIGN_CENTER)
        self.operate_box2.Add(self.realtrade_checkbox, 0, flag=wx.EXPAND | wx.ALL, border=5)
        
        self.enable_records_checkbox = wx.CheckBox(self, label='只显示2级', style=wx.ALIGN_CENTER)
        self.operate_box2.Add(self.enable_records_checkbox, 0, flag=wx.EXPAND | wx.ALL, border=5)
        
        self.name_input = wx.TextCtrl(self)
        self.operate_box2.Add(self.name_input, 0, flag=wx.EXPAND | wx.ALL, border=5)

        self.start_btn = wx.Button(self, label='刷新关注列表')
        self.operate_box2.Add(self.start_btn, 1, flag=wx.EXPAND | wx.ALL, border=5)

        # self.stop_btn = wx.Button(self, label='添加蓝图')
        # self.operate_box2.Add(self.stop_btn, 1, flag=wx.EXPAND | wx.ALL, border=5)
            
        # self.flush_strategys_list()
        self.strategys_box.Add(self.strategys_list,1,wx.EXPAND)
        
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        # self.sizer.Add(self.operate_box, 0, wx.ALL | wx.EXPAND, 5)
        
        # self.sizer.Add(self.operate_box3, 0, wx.ALL | wx.EXPAND, 5)
        self.sizer.Add(self.strategys_box, 0, wx.ALL | wx.EXPAND, 5)
        self.sizer.Add(self.operate_box2, 0, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(self.sizer)
        self.Bind(wx.EVT_CHECKBOX, self.set_info, self.enable_records_checkbox)
        self.Bind(wx.EVT_CHECKBOX, self.set_realtrade, self.realtrade_checkbox)
        self.Bind(wx.EVT_BUTTON, self.on_save_strategy, self.start_btn)
        self.strategys_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.data_choose)
        # self.strategys_list.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.data_click)
        # self.strategys_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.data_choose)
   

    def data_choose(self, event):
        itemcount = self.strategys_list.GetItemCount()
        selected_index = 0
        for i in range(0, itemcount):
            if self.strategys_list.IsSelected(i):
                selected_index = i
                break
        if selected_index==0:
            self.parent.main.SetStatusText("请选中一个列表中的产品")
        else:
            name = self.strategys_list.GetItem(selected_index, 1).GetText()
            self.name_input.Value = name
           
        
    def set_info(self, event):
        type='ALL'
        if self.enable_records_checkbox.Value:
            type='2'
            self.realtrade_checkbox.Value=False
        
        
        if self.parent.main.eve.watchlist is None:
            self.parent.main.SetStatusText("无产品列表数据")
        else:
            self.flush_watchlist(type,'profit_pre_day')
        
    def set_realtrade(self, event):
        type='ALL'
       
        if self.realtrade_checkbox.Value:
            type='1'
            self.enable_records_checkbox.Value=False
        
        if self.parent.main.eve.watchlist is None:
            self.parent.main.SetStatusText("无产品列表数据")
        else:
            self.flush_watchlist(type,'full_eff_profit_pre_day')
        
        
    def on_save_strategy(self, event):
        threading.Thread(target=self.parent.main.eve.reflush_watchlist).start()
        


    def flush_watchlist(self,type,sort_by):
        watchlist = self.parent.main.eve.watchlist
        if watchlist.shape[0]>0:
            data_list = self.strategys_list
            data_list.DeleteAllItems()
            data_csv = watchlist
            data_csv = data_csv.sort_values(by=sort_by,ascending=False)
            for i, r in data_csv.iterrows():

                if str(r['product_metaGroupID'])==type or type=='ALL':
                    index = data_list.InsertItem(data_list.GetItemCount(), '') 
                    data_list.SetItem(index, 0, str(r['product_id']))
                    data_list.SetItem(index, 1, r['product_name'])
                    data_list.SetItem(index, 2, str(r['product_metaGroupID']))
                    data_list.SetItem(index, 3, str('{:20,}'.format(r['product_price'])))  
                    data_list.SetItem(index, 4, str(r['product_time']))
                    data_list.SetItem(index, 5, str('{:20,}'.format(r['material_total'])))  
                    data_list.SetItem(index, 6, str(r['profit_rate']))
                    data_list.SetItem(index, 7, str('{:20,}'.format(r['full_eff_profit_pre_day'])))  
                    data_list.SetItem(index, 8, str('{:20,}'.format(r['full_eff_material_total'])))   
                    data_list.SetItem(index, 9, str(r['full_eff_profit_rate']))
                    data_list.SetItem(index, 10, str('{:20,}'.format(r['full_eff_profit_pre_day'])))  
                    data_list.SetItem(index, 11, str('{:20,}'.format(r['product_cost'])))  
                    data_list.SetItem(index, 12, str('{:20,}'.format(r['invent_cost'])))

                    data_list.SetItem(index, 13, str(r['order_volumn']))
                    data_list.SetItem(index, 14, str('{:20,}'.format(r['orders_profit'])))  
                    data_list.SetItem(index, 15, str(r['eff_full_order_volumn']))
                    data_list.SetItem(index, 16, str('{:20,}'.format(r['eff_full_orders_profit'])))  
                    data_list.SetItem(index, 17, str(r['isRecount'])) 
                    data_list.SetItem(index, 18, str(r['update_time']))    
    
   
        
        
if __name__ == '__main__':
   
    
    app = wx.App()
    frm = CryptoFrame(None, title='EVE-制造速查工具混沌军团内部', size=(2220, 1200))
    frm.Show()
    app.MainLoop()