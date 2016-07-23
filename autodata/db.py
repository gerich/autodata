# -*- coding: utf-8 -*-

import pymongo
import pdb
from scrapy.conf import settings

from autodata.items import EngineItem

class Db(object):
    
    def __init__(self):
        connection = pymongo.MongoClient(settings['MONGODB_SERVER'], settings['MONGODB_PORT'])
        db = connection[settings['MONGODB_DB']]
        self.collection = db[settings['MONGODB_COLLECTION']]

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
        id = item['model_family_id']
        del item['model_family_id']
        result = self.collection.update_one(
            {'link': item['mark_link']},
            {'$set': {'models.' + id: item}}
        )
        return self.__update_result(result)

    def save_engine_code(self, item):
        """
        engine_name: { dict(EngineCodeItem) }
        """
        item = dict(item)
        engine_id = item['engine_name']
        model_id = item['model_family_id']
        engine_code_id = item['mecnid']
        del item['engine_name']
        del item['model_family_id']
        del item['mecnid']
        selector = "models.{0}".format(model_id)
        update = "{0}.engines.{1}.{2}".format(selector, engine_id, engine_code_id)
        result = self.collection.update_one(
            {selector: {'$exists': True}},
            {'$set' : {update: item}}
        )
        return self.__update_result(result)

    def coursor(self):
        return self.collection.find()
    
    def log(self, msg):
        if hasattr(self, 'spider'):
           self.spider.log(msg)
