# -*- coding: utf-8 -*-

import pdb
import json
import time

from scrapy import Request, FormRequest
from scrapy.spiders import Spider, Rule
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
        # self.db.collection.delete_many({})
        # self.db.works.delete_many({})
        super(WorkingSpider, self).__init__()

    def __prepare_request(self, request):
        request.cookies['ad_web_g_333336303139'] = '0'
        request.cookies['ad_web_u_67656E6572616C6F762E616C6578616E64722E612D707666'] = '0'
        request.cookies['ad_web_i_36322E37362E31332E313331'] = '0'
        request.cookies['has_js'] = '1'
        # request.cookies['__qca'] = 'P0-1677323104-1468405118825'
        request.cookies['SESSd965b47fdd2684807fd560c91c3e21b6'] = 'QSbftB9UPveR3c9x69k3iLn9SDHmLzKfSPrZ73lYDlc'
        request.dont_filter = True

    def make_requests_from_url(self, url):
        request = super(WorkingSpider, self).make_requests_from_url(url)
        self.__prepare_request(request)       
        return request

    def parse(self, response):
        marks = Selector(response).xpath('//ul[@id="all-manufacturers-list"]/li')
        if not marks:
            raise CloseSpider('Сессионная кука не верна')
        
        exists = True
        for mark in marks:
            item = helper.make_mark_item(mark)
            exists = self.db.mark_exists(item['link'])
            if not exists:
                self.db.save_mark(item)
                yield item

            is_all = self.db.is_all_mark(item['link'])
            if (not is_all or not exists) and item['link'] != 'POR0':
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
        mark_link = response.request.url.split('/')[-1]
        for model in models:
            model_family_id = model.xpath('@model_family_id').extract()[0]
            name = model.xpath('a/text()').extract()[0].strip()
            start_year, end_year, chassi_code = helper.extract_years_and_chassi_code(model)
            item = ModelItem(name=name, start_year=start_year,
                    end_year=end_year, model_family_id=model_family_id,
                    mark_link=mark_link, chassi_code=chassi_code)
            exists = self.db.model_exists(model_family_id)
            if not exists:
                self.db.save_model(item)
                yield item
            
            is_all = self.db.is_all(model_family_id)
            if not exists or not is_all:
                request = self.__model_menu_request(mark, item)
                exists = False
                yield request
                break

        if exists:
            self.db.save_model(ModelItem(mark_link=mark_link))
            self.log('Переход к новой марке')
            request = self.make_requests_from_url(self.start_urls[0])
            request.callback = self.parse
            yield request

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
    
    def __engines_path(self, mark, model):
        return ('/v2/engine/select/'
            + model + '/'
            + mark + '/'
            + '?back=/vehicle/component/rt&module=RT')
