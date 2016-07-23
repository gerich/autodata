# -*- coding: utf-8 -*-

import pdb
import json
import time

from scrapy import Request, FormRequest
from scrapy.spiders import Spider, Rule
# from scrapy.spiders import CrawlSpider as Spider, Rule
from scrapy.selector import Selector
from twisted.internet import reactor, defer

from autodata.items import (MarkItem, ModelItem, EngineItem, EngineCodeItem,
    CarComponentItem, CarFeatureItem, WorkGroupItem, WorkItem)
from autodata.db import Db

from autodata.spiders import helper


class StepByStepSpider(Spider):
    name = "step_by_step"
    allowed_domains = ["workshop.autodata-group.com"]
    start_urls = (
        'https://workshop.autodata-group.com/vehicle/model-selection/',
    )
    
    def __init__(self):
        self.db = Db()
        self.db.collection.delete_many({})
        self.marks = []
        self.models = []
        self.engine_codes = []
        super(StepByStepSpider, self).__init__()

    def __prepare_request(self, request):
        request.cookies['ad_web_g_333238303433'] = '0'
        request.cookies['ad_web_u_6C69686F6C65746F762D763530'] = '0'
        request.cookies['ad_web_i_36322E37362E31332E313331'] = '0'
        request.cookies['has_js'] = '1'
        # request.cookies['__qca'] = 'P0-1677323104-1468405118825'
        request.cookies['SESSd965b47fdd2684807fd560c91c3e21b6'] = 'NBL7XwCsyAijyrUOtcd9pZVFiCxBYh48xOcI0pOiwnY'
        # request.dont_filter = True

    def make_requests_from_url(self, url):
        request = super(StepByStepSpider, self).make_requests_from_url(url)
        self.__prepare_request(request)       
        return request

    def parse(self, response):
        marks = Selector(response).xpath('//ul[@id="all-manufacturers-list"]/li')
        marks = [marks[2]] + [marks[5]] + [marks[18]] # @todo

        for mark in marks:
            item = MarkItem()
            item['link'] = mark.xpath('@manufacturer_id').extract()[0]
            a = mark.xpath('a')
            item['name'] = a.xpath('text()').extract()[0].strip()
            self.db.save_mark(item)
            yield item
            self.marks.append(item)
            
        self.going_to_root()

    def __model_request(self, mark):
        url = self.start_urls[0] + 'ajax/' + mark['link']
        request = self.make_requests_from_url(url)
        request.callback = self.parse_models
        request.meta['mark'] = dict(mark)

        return request

    def going_to_root(self, response = None):
        request = self.make_requests_from_url('https://' + self.allowed_domains[0])
        request.callback = self.going_to_mark

        yield request

    def going_to_mark(self, response):
        if not self.marks: 
            return

        mark = self.marks.pop()
        request = self.__mark_request(mark)

        yield request
        
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
        models = models[:10] # @todo
        
        for model in models:
            model_family_id = model.xpath('@model_family_id').extract()[0]
            name = model.xpath('a/text()').extract()[0].strip()
            start_year, end_year, chassi_code = helper.extract_years_and_chassi_code(model)
            item = ModelItem(name=name, start_year=start_year,
                    end_year=end_year, model_family_id=model_family_id,
                    mark_link=mark_link, chassi_code=chassi_code)

            self.db.save_model(item)
        
            yield item
            self.models.append(item)
    
        # yield self.__prepare_model_menu_request(mark)

    def __prepare_model_menu_request(self, mark):
        if not self.models:
            return

        item = self.models.pop()
        request = FormRequest(
            url = self.start_urls[0],
            formdata = {
                'action': 'modelSelectionSaveVehicle',
                'manufacturer_id': mark['link'],
                'model_family_id': dict(item)['model_family_id'],
                'manufacturer_name': mark['name'],
                'model_name': '',
                'engine_code': '',
                'model_mid': '',
                'back': ''
            },
            callback = self.going_to_engine_select,
            meta = {
                'mark': mark,
                'model': dict(item),
            }
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
        request.priority = 20
        request.callback = self.parse_engines
        yield request

    def parse_engines(self, response):
        mark = response.meta['mark']
        model = response.meta['model']
        selector = Selector(response)
        engines = selector.xpath('//ul[@id="engine-model-list "]/li/a')
        if not engines:
            yield

        for engine in engines:
            engine_item = EngineItem(
                engine_name = engine.xpath('text()').extract()[0].strip(),
                model_family_id = engine.xpath('@body').extract()[0].strip()
            )
             
            engine_codes = selector.xpath('//table[@id="engine-code-filtered"]/tbody/tr')
            if not engine_codes:
                continue
            
            for code in engine_codes:
                item = helper.make_engine_code_item(code, engine_item)
        
                if item:
                    self.db.save_engine_code(item)
                    yield item
                
                request = self.__make_request_for_engine_code(dict(item), response.url)
                if request:
                    yield request

        request = self.__prepare_model_menu_request(mark)
        if request:
            yield request

    def __make_request_for_engine_code(self, code_item, url):
        pass 
