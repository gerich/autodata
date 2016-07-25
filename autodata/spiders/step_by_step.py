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
        self.options = []
        super(StepByStepSpider, self).__init__()

    def __prepare_request(self, request):
        request.cookies['ad_web_g_333238303433'] = '0'
        request.cookies['ad_web_u_6C69686F6C65746F762D763530'] = '0'
        request.cookies['ad_web_i_36322E37362E31332E313331'] = '0'
        request.cookies['has_js'] = '1'
        # request.cookies['__qca'] = 'P0-1677323104-1468405118825'
        request.cookies['SESSd965b47fdd2684807fd560c91c3e21b6'] = 'R_T9syP2jfAX2TovffXKKrrky63sBJxWE7dSJnKwnCc'
        # request.dont_filter = True

    def make_requests_from_url(self, url):
        request = super(StepByStepSpider, self).make_requests_from_url(url)
        self.__prepare_request(request)       
        return request

    def parse(self, response):
        marks = Selector(response).xpath('//ul[@id="all-manufacturers-list"]/li')
        if not marks:
            raise EOFError('Сессионная кука не верна')

        marks = [marks[2]] + [marks[5]] + [marks[18]] # @todo

        for mark in marks:
            item = MarkItem()
            item['link'] = mark.xpath('@manufacturer_id').extract()[0]
            a = mark.xpath('a')
            item['name'] = a.xpath('text()').extract()[0].strip()
            self.db.save_mark(item)
            yield item
            self.marks.append(item)
            
        yield self.__root_request()

    def __model_request(self, mark = None):
        """
        Если нет текущей марки то берем из списка марок
        Если список марок пуст то останов
        """
        if not self.marks: 
            raise CloseSpider('Завершено')

        if not mark:
            mark = self.marks.pop()
        url = self.start_urls[0] + 'ajax/' + mark['link']
        request = self.make_requests_from_url(url)
        request.callback = self.parse_models
        request.meta['mark'] = dict(mark)

        return request
    
    def __root_request(self):
        request = self.make_requests_from_url('https://' + self.allowed_domains[0])
        request.callback = self.going_to_mark
        
        return request

    def going_to_root(self, response):
        yield self.__root_request()

    def __mark_select_request(self):
        request = self.make_requests_from_url(self.start_urls[0])
        request.callback = self.going_to_model_select

        return request

    def going_to_mark(self, response):
        yield self.__mark_select_request()

    def going_to_model_select(self, response):
        # если есть марка значит пришли парсин моделей текуще марки не закончен
        mark = None
        if 'mark' in response.meta:
            mark = response.meta['mark']

        yield self.__model_request(mark)
        
    def parse_models(self, response):
        mark = response.meta['mark']
        if not self.models:
            json_response = json.loads(response.body_as_unicode())
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
    
        yield self.__prepare_model_menu_request(mark)

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
        
        if not time_works_link:
            # Если нет данных по этой модели
            request = self.__mark_select_request()
        else:
            # Если есть то идем дальше
            request = self.make_requests_from_url(url)
            request.callback = self.parse_engines

        request.meta['mark'] = mark
        request.meta['model'] = model

        yield request

    def parse_engines(self, response):
        mark = response.meta['mark']
        model = response.meta['model']
        selector = Selector(response)
        engines = selector.xpath('//ul[@id="engine-model-list "]/li/a')
        if not engines:
            yield

        pdb.set_trace()   
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
                    self.engine_codes.append(item)
                    yield item
                
        request = self.__make_request_for_engine_code(dict(item), response.url)
        if request:
            return request

        request = self.__mark_select_request()
        if request:
            request.meta['mark'] = mark
            return request

    def __make_request_for_engine_code(self, code_item, url):
        pass 
