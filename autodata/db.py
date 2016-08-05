# -*- coding: utf-8 -*-

import pymongo
from bson.dbref import DBRef
import json 
import pdb
from scrapy.conf import settings
from scrapy.exceptions import CloseSpider

from autodata.items import EngineItem, EngineCodeItem, CarOptionItem

class Db(object):

    ALL_MARKER = 'all'
    
    def __init__(self):
        connection = pymongo.MongoClient(settings['MONGODB_SERVER'], settings['MONGODB_PORT'])
        db = connection[settings['MONGODB_DB']]
        self.collection = db[settings['MONGODB_COLLECTION']]
        self.works = db[settings['MONGODB_WORKS_COLLECTION']]

    def save_mark(self, item):
        result = self.collection.insert_one(dict(item))
        if result and result.inserted_id:
            return result.inserted_id
        return None

    def __update_result(self, result):
        if result and result.matched_count:
            return result.matched_count
        return None

    def save_model(self, item):
        item = dict(item)
        mark = item['mark_link']
        if 'model_family_id' in item:
            id = item['model_family_id']
            del item['model_family_id']
        else:
            id = self.ALL_MARKER
            item = {}

        result = self.collection.update_one(
            {'link': mark},
            {'$set': {'models.' + id: item}}
        )
        return self.__update_result(result)

    def save_engine_series(self, item):
        model_id = item['model_family_id']
        if 'engine_name' in item:
            engine_id = item['engine_name']
        else:
            engine_id = self.ALL_MARKER
        selector = "models.{0}".format(model_id)
        update =  "{0}.engines.{1}".format(selector, engine_id)
        result = self.collection.update_one(
            {selector: {'$exists': True}},
            {'$set' : {update: {}}}
        )

        return self.__update_result(result)

    def save_engine_code(self, item):
        """
        engine_name: { dict(EngineCodeItem) }
        """
        item = dict(item)
        engine_id = item['engine_name']
        model_id = item['model_family_id']
        if 'mecnid' in item:
            engine_code_id = item['mecnid']
            del item['engine_name']
            del item['model_family_id']
            del item['mecnid']
        else:
            engine_code_id = self.ALL_MARKER
            item = {}
        selector = "models.{0}.engines.{1}".format(model_id, engine_id)
        update = "{0}.{1}".format(selector, engine_code_id)
        result = self.collection.update_one(
            {selector: {'$exists': True}},
            {'$set' : {update: item}}
        )
        return self.__update_result(result)

    def save_option(self, item):
        item = dict(item)

        engine_id = item['engine_name']
        model_id = item['model_family_id']
        engine_code_id = item['mecnid']
        if 'item_id' in item:
            option_id = item['item_id']
            del item['engine_name']
            del item['model_family_id']
            del item['mecnid']
            del item['item_id']
        else:
            option_id = self.ALL_MARKER
            item = {}

        selector = "models.{0}.engines.{1}.{2}".format(model_id, engine_id, engine_code_id)
        update = "{0}.options.{1}".format(selector, option_id)
        result = self.collection.update_one(
            {selector: {'$exists': True}},
            {'$set' : {update: item}}
        )
        return self.__update_result(result)

    def save_repair_times(self, item, times):
        if type(item) is CarOptionItem:
            selector = "models.{0}.engines.{1}.{2}.options.{3}".format(
                item['model_family_id'],
                item['engine_name'],
                item['mecnid'],
                item['item_id']
            )

            works_document = {
                "model_family_id": item['model_family_id'],
                "engine_name": item['engine_name'],
                "mecnid": item['mecnid'],
                "item_id": item['item_id']
            }
        elif type(item) is EngineCodeItem: 
            selector = "models.{0}.engines.{1}.{2}".format(
                item['model_family_id'],
                item['engine_name'],
                item['mecnid'],
            )

            works_document = {
                "model_family_id": item['model_family_id'],
                "engine_name": item['engine_name'],
                "mecnid": item['mecnid'],
            }
        else:
            raise RuntimeError('Не ясно куда прикрепить нормо часы')

        works_document['repair_times'] = json.dumps(times)
        result = self.works.insert_one(works_document)
        
        if not result or not result.inserted_id:
            return None

        ref = DBRef(
            collection = settings['MONGODB_WORKS_COLLECTION'],
            id = result.inserted_id
        )
        result = self.collection.update_one(
            {selector: {'$exists': True}},
            {'$set': {selector + '.works': ref}}
        )

        return self.__update_result(result)

    def coursor(self):
        return self.collection.find()
    
    def mark_exists(self, id):
        coursor = self.collection.find({'link': id})
        return coursor.count() > 0
    
    def __exists_by_selector(self, selector):
        coursor = self.collection.find({selector: {'$exists': True}})
        return coursor.count() > 0

    def model_exists(self, id):
        return self.__exists_by_selector('models.' + id)

    def engine_series_exists(self, model, id):
        selector = 'models.{}.engines.{}'.format(model, id)
        return self.__exists_by_selector(selector)

    def engine_code_exists(self, model, series, id):
        selector = 'models.{}.engines.{}.{}'.format(model, series, id)
        return self.__exists_by_selector(selector)

    def option_exists(self, model, series, code, option):
        selector = 'models.{}.engines.{}.{}.options.{}'.format(
            model, series, code, option
        )
        return self.__exists_by_selector(selector)

    def is_all(self, model = None, series = None, code = None):
        if model == None:
            selector = 'models.' + self.ALL_MARKER
        elif series == None:
            selector = ('models.' + model
                + '.engines.' + self.ALL_MARKER)
        elif code == None:
            selector = ('models.' + model
                + '.engines.' + series
                + '.' + self.ALL_MARKER)
        else:
            selector = ('models.' + model
                + '.engines.' + series
                + '.' + code)
            if self.__exists_by_selector(selector + '.options'):
                selector += '.options.' + self.ALL_MARKER
            else:
                selector += '.works'

        return self.__exists_by_selector(selector)

    def is_all_mark(self, link):
        coursor = self.collection.find({'link': link, 'models.' + self.ALL_MARKER: {'$exists': True}})
        return coursor.count() > 0

