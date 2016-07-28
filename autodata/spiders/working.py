# -*- coding: utf-8 -*-

import pdb
import json
import time

from scrapy import Request, FormRequest
from scrapy.spiders import Spider, Rule
# from scrapy.spiders import CrawlSpider as Spider, Rule
from scrapy.selector import Selector
from scrapy.exceptions import CloseSpider
from twisted.internet import reactor, defer

from autodata.items import (MarkItem, ModelItem, EngineItem, EngineCodeItem,
    CarComponentItem, CarOptionItem, WorkGroupItem, WorkItem)
from autodata.db import Db
from autodata.spiders import helper


class WorkingSpider(Spider):
    name = "working"
    allowed_domains = ["workshop.autodata-group.com"]
    start_urls = (
        'https://workshop.autodata-group.com/vehicle/model-selection/',
    )

    def __init__(self):
        self.db = Db()
        self.db.collection.delete_many({})
        self.db.works.delete_many({})
        super(WorkingSpider, self).__init__()

    def __prepare_request(self, request):
        request.cookies['ad_web_g_333336303139'] = '0'
        request.cookies['ad_web_u_67656E6572616C6F762E616C6578616E64722E612D707666'] = '0'
        request.cookies['ad_web_i_36322E37362E31332E313331'] = '0'
        request.cookies['has_js'] = '1'
        # request.cookies['__qca'] = 'P0-1677323104-1468405118825'
        request.cookies['SESSd965b47fdd2684807fd560c91c3e21b6'] = 'T5eR4BjfEfcjkOMEwV2zFOk1qaimbkA9vRsvUtg3SEc'
        request.dont_filter = True

    def make_requests_from_url(self, url):
        request = super(WorkingSpider, self).make_requests_from_url(url)
        self.__prepare_request(request)       
        return request

    def parse(self, response):
        marks = Selector(response).xpath('//ul[@id="all-manufacturers-list"]/li')
        if not marks:
            raise CloseSpider('Сессионная кука не верна')
        # marks = [marks[2]] + [marks[5]] + [marks[18]] # @TODO
        marks = [marks[18]] # @TODO

        exists = True
        for mark in marks:
            item = helper.make_mark_item(mark)
            exists = self.db.mark_exists(item['link'])
            if not exists:
                self.db.save_mark(item)
                yield item
                
                request = self.__model_request(item)
                yield request
                break
                
    def __model_request(self, item):
        url = self.start_urls[0] + 'ajax/' + item['link']
        request = self.make_requests_from_url(url)
        request.callback = self.parse_models
        request.method = 'POST'
        request.meta['mark'] = item

        return request

    def parse_models(self, response):
        json_response = json.loads(response.body_as_unicode())
        mark = response.meta['mark']
        html = ''
        for data in json_response:
            if (type(data) is not dict
                or 'command' not in data
                or 'method' not in data
                or data['command'] != 'insert'
                or data['method'] != 'replaceWith'):
                continue               
            html = data['data']
            
        if not html:
            yield
        
        models = Selector(text=html).xpath('//ul[@id="all-model-ranges-list"]/li')
        mark_link = response.url.split('/')[-1]
        # models = models[:10] # @TODO
        models = models[1:2] # @TODO
        for model in models:
            model_family_id = model.xpath('@model_family_id').extract()[0]
            exists = self.db.model_exists(model_family_id)
            if not exists:
                name = model.xpath('a/text()').extract()[0].strip()
                start_year, end_year, chassi_code = helper.extract_years_and_chassi_code(model)
                item = ModelItem(name=name, start_year=start_year,
                        end_year=end_year, model_family_id=model_family_id,
                        mark_link=mark_link, chassi_code=chassi_code)

                self.db.save_model(item)
                yield item

                request = self.__model_menu_request(mark, item)
                yield request
                break
    
    def __model_menu_request(self, mark, model):
        request = FormRequest(
            url = self.start_urls[0],
            formdata = {
                'action': 'modelSelectionSaveVehicle',
                'manufacturer_id': mark['link'],
                'model_family_id': dict(model)['model_family_id'],
                'manufacturer_name': mark['name'],
                'model_name': '',
                'engine_code': '',
                'model_mid': '',
                'back': ''
            },
            callback = self.going_to_engine_select,
            meta = {
                'mark': mark,
                'model': model,
            },
            dont_filter = True
        )
        self.__prepare_request(request)
        return request

    def going_to_engine_select(self, response):
        mark = response.meta['mark']
        model = response.meta['model']
        path = ('/v2/engine/select/'
            + model['model_family_id'] + '/'
            + mark['link'] + '/'
            + '?back=/vehicle/component/rt&module=RT')
        url = 'https://' + self.allowed_domains[0] + path
        time_works_link = Selector(response).xpath('//a[@href="' + path + '"]')
        
        # Если нет данных по этой модели
        if not time_works_link:
            yield
        
        request = self.make_requests_from_url(url)
        request.meta['mark'] = mark
        request.meta['model'] = model
        request.callback = self.parse_engine_series
        yield request

    def parse_engine_series(self, response):
        selector = Selector(response)
        engines = selector.xpath('//ul[@id="engine-model-list "]/li/a')
        engines = engines[0:1] # TODO
        item = None
        for engine in engines:
            engine_item = helper.make_engine_series(engine)
            exists = self.db.engine_series_exists(
                engine_item['model_family_id'],
                engine_item['engine_name']
            )
            if not exists:
                self.db.save_engine_series(engine_item)
                yield engine_item
                item = engine_item
                break
            is_all = self.db.is_all(
                engine_item['model_family_id'],
                engine_item['engine_name']
            )
            if not is_all:
                item = engine_item
                break

        if item:
            engine_item = helper.make_engine_series(
                selector.xpath('//a[text()="{}"]'.format(item['engine_name']))
            )
            request = self.__engine_codes_request(engine_item)
            yield request
        
    def __engine_codes_request(self, series):
        url = 'https://' + self.allowed_domains[0] + '/v2/engine_code/selection'
        request = FormRequest(
            url = url,
            formdata = {
                'manufacturer': series['link'],
                'body': series['model_family_id'],
                'litres': series['litres'],
                'fuel': series['fuel'],
                'freetext': series['text'],
                'vehicletype': series['vehicletype'],
                'module': 'RT'
            },
            callback = self.parse_engine_codes,
            meta = {
                'series': series,
            },
            dont_filter = True
        )
        self.__prepare_request(request)
        request.method = 'POST'
        return request
             
    def parse_engine_codes(self, response):
        json_response = json.loads(response.body_as_unicode())
        series = response.meta['series']
        engine_codes = Selector(text=json_response).xpath('//table[@id="engine-code-filtered"]/tbody/tr')
        exists = True
        for code in engine_codes[0:1]: # TODO
            item, disabled = helper.make_engine_code_item(code, series)
            exists = self.db.engine_code_exists(
                item['model_family_id'],
                item['engine_name'],
                item['mecnid']
            )
            if not exists:
                self.db.save_engine_code(item)
                yield item

            is_all = self.db.is_all(
                item['model_family_id'], 
                item['engine_name'],
                item['mecnid']
            )
            if not disabled and not is_all:
                yield self.__options_request(item)
                exists = False
                break

        if exists:
            request = self.make_requests_from_url(self.start_urls[0])
            yield request
                
    def __options_request(self, code):
        url = 'https://workshop.autodata-group.com/engine-code-form-api'

        request = FormRequest(
            url = url,
            callback = self.going_to_options_or_repair_times,
            formdata = {
                'vehicle_id': code['mecnid'],
                'engine_id': code['code'],
                'engine_name': code['code'],
                'back': ',/vehicle/component/rt&module=RT',
            },
            meta = {
                'series': code,
            },
            dont_filter = True
        )
        self.__prepare_request(request)
        request.method = 'POST'
        request.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        request.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
        request.headers['X-Requested-With'] = 'XMLHttpRequest'
        request.meta['code'] = code
        return request
        
    def going_to_options_or_repair_times(self, response):
        url = '/v2/vehicle/select/variant?back=rt&module=RT'
        url = 'https://' + self.allowed_domains[0] + url
        request = self.make_requests_from_url(url)
        request.callback = self.parse_options_or_repair_times
        request.meta['code'] = response.meta['code']

        yield request

    def parse_options_or_repair_times(self, response):
        selector = Selector(response)
        exists = True
        if response.url.find('repair-times') == -1:
            # страница опций  
            engine = response.meta['code']
            for option_selector in selector.xpath('//ul/li[@item-id]'): 
                id = option_selector.xpath('@item-id').extract()[0]
                name = option_selector.xpath('a/text()').extract()[0] 
                item = helper.make_car_option_item(engine, id, name)
                exists = self.db.option_exists(
                    item['model_family_id'],
                    item['engine_name'],
                    item['mecnid'],
                    item['item_id']
                )
                if not exists:
                    self.db.save_option(item)
                    yield item
                    url = '/vehicle/component/repair-times/variant'
                    url = 'https://' + self.allowed_domains[0] + url
                    request = FormRequest(
                        url = url, formdata = {'item_id': item['item_id']}
                    )
                    request.headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    request.headers['Accept'] = '*/*'
                    request.headers['X-Requested-With'] = 'XMLHttpRequest'
                    request.method = 'POST'
                    request.dont_filter = True
                    request.meta['option'] = item
                    request.callback = self.going_to_repair_times
                    self.__prepare_request(request)
                    yield request
                    break

            if exists: # STOP
                item = CarOptionItem(code)
                self.save_option(item)
        else:
            # страница нормочасов
            group_selectors = selector.xpath('//div[contains(@id,"accordian-section")]')
            repair_times = helper.make_repair_times(group_selectors)
            item = None
            if 'option' in response.meta:
                item = response.meta['option']
            elif 'code' in response.meta:
                item = response.meta['code']
            self.log('repair times scraped to ' + str(item))
            self.db.save_repair_times(item, repair_times)
            # TODO!!!!

        if exists:
            url = self.__make_url(helper.change_engine_link(selector))
            request = self.make_requests_from_url(url)
            request.callback = self.parse_engine_series
            yield request

    def going_to_repair_times(self, response):
        json_response = json.loads(response.body_as_unicode())
        url = 'https://' + self.allowed_domains[0] + json_response['action']
        request = self.make_requests_from_url(url)
        request.meta['option'] = response.meta['option']
        request.callback = self.parse_options_or_repair_times
        yield request

    def __make_url(self, url):
        return 'https://' + self.allowed_domains[0] + url
