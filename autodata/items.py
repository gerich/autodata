# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy import Item, Field


class MarkItem(Item):
    name = Field()
    link = Field()

class ModelItem(Item):
    name = Field()
    model_family_id = Field() # id
    start_year = Field()
    end_year = Field()
    mark_link = Field()
    chassi_code = Field()
    last = Field()

class EngineItem(Item):
    engine_name = Field() # id кодов двигателя
    model_family_id = Field() # parent

class EngineCodeItem(EngineItem):
    code = Field()
    start_year = Field()
    end_year = Field()
    power_kw = Field()
    power = Field()
    param = Field()
    mecnid = Field() # id

class CarFeatureItem(Item):
    name = Field()
    mecnid = Field() # parent
    model_family_id = Field() # parent
    item_id = Field() # id

# то что ниже для конкретной страницы с работами и нормочасами
class CarComponentItem(Item):
    feature = Field() # parent item_id
    name = Field()

class WorkGroupItem(Item):
    name = Field()

class WorkItem(Item):
    name = Field() # id
    hours = Field()
    type = Field()

class SubWorkItem(Item):
    name = Field()
    type = Field()

