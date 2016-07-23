# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html
from scrapy.exceptions import DropItem
from scrapy import log

from autodata import items
import pdb


class AutodataPipeline(object):
    def process_item(self, item, spider):
        for data in item:
            if not data:
                raise DropItem("Missing {0}!".format(data))

        db = spider.db
        if type(item) is items.MarkItem:
            inserted_id = db.save_mark(item)
            if inserted_id:
                log.msg("Mark {0} added with _id {1}"
                    .format(item['name'], inserted_id), level=log.DEBUG, spider=spider)
        elif type(item) is items.ModelItem:
            count = db.save_model(item)
            if count:
                log.msg("Model {0} added with {1}"
                    .format(item['name'], item['model_family_id']), level=log.DEBUG, spider=spider)
        elif type(item) is items.EngineCodeItem:
            if db.save_engine_code(item):
                log.msg("Engine code added to engine {0} with model {1}"
                    .format(item['engine_name'], item['model_family_id'])
                    , level=log.DEBUG, spider=spider)
        return item

