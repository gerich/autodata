import pdb

from autodata.items import (MarkItem, ModelItem, EngineItem, EngineCodeItem,
    CarComponentItem, CarOptionItem, WorkGroupItem, WorkItem)

def extract_years_and_chassi_code(model):
    years = model.xpath('a/span/text()').extract()
    start_year = end_year = chassi_code = None
    if len(years) == 0:
        return start_year, end_year, chassi_code

    years = years[0].strip()
    years = years.replace(')', '').replace('(', '')
    start_year = years
    without_space = (start_year.find(' ') == -1)
    without_dash = (start_year.find('-') == -1)
    # Только год
    if without_space and not without_dash:
        start_year, end_year = start_year.split('-')
        end_year = int(end_year) if end_year else 0
        return int(start_year), int(end_year), chassi_code
    # Для FROD
    elif without_space and start_year.find("'") >= 0:
        start_year = start_year.replace("'", '').split('/')[-1]
        return None, int(start_year), ''
    # Только серия
    elif without_space:
        return None, None, start_year
    
    chassi_code, start_year = years.split(' ')
    if not without_dash:
        start_year, end_year = start_year.split('-')

    start_year = int(start_year) if start_year else None
    end_year = int(end_year) if end_year else None

    return start_year, end_year, chassi_code
            
def make_engine_code_item(code, engine_item):
    if not code:
        return

    disabled = code.xpath(
        'contains(concat(" ", normalize-space(@class), " "), " disabled ")'
    )
    disabled = False if disabled else True
    
    item = EngineCodeItem(engine_item)
    item['code'] = code.xpath('td[1]/text()').extract()[0].strip()
    item['power_kw'] = int(code.xpath('td[2]/text()')
        .extract()[0].strip().split(' ')[0])
    item['power'] = code.xpath('td[3]/text()').extract()[0].strip()
    param = code.xpath('td[4]/text()').extract()[0].strip()
    if param:
        item['param'] = param
    years = code.xpath('td[5]/text()').extract()[0].strip().split('-')
    if len(years) == 2:
        item['start_year'] = years[0]
        item['end_year'] = years[1]
    item['mecnid'] = code.xpath('@mecnid').extract()[0].strip()
    
    return item, disabled

def make_repair_times(selector):
    group_dict = {}
    for group in selector:
        header = group.xpath('div[1]/h2/text()').extract()[0].strip()
        subgroups = {}
        for subgroup_selector in group.xpath('div[2]/div/div'):
            subheader = subgroup_selector.xpath('a/text()').extract()[0].strip()
            works = []
            for repair_time_selector in subgroup_selector.xpath('div/table/tbody/tr'):
                name = repair_time_selector.xpath('@rt_name').extract()[0].strip()
                work_type = repair_time_selector.xpath('td[1]/text()').extract()[0].strip()
                time = repair_time_selector.xpath('td[3]/text()').extract()[0].strip()
                works.append({
                    'type': work_type,
                    'time': time,
                    'name': name
                })
            subgroups[subheader] = works
        group_dict[header] = subgroups
    return group_dict

def change_engine_link(selector):
    link = selector.xpath(
        '//ul[@id="jobfolderheader"]/li/div/a[contains(@class, "ctaSmall")]/@href'
    ).extract()[0]
    return link

def make_engine_series(engine):
    return EngineItem(
        engine_name = engine.xpath('text()').extract()[0].strip(),
        model_family_id = engine.xpath('@body').extract()[0].strip(),
        text = engine.xpath('@freetext').extract()[0].strip(),
        vehicletype = engine.xpath('@vehicletype').extract()[0].strip(),
        fuel = engine.xpath('@fuel').extract()[0],
        link = engine.xpath('@manufacturer').extract()[0],
        litres = engine.xpath('@litres').extract()[0]
    )

def make_car_option_item(engine, id = None, name = None):
    item = CarOptionItem(
        model_family_id  = engine['model_family_id'],
        engine_name = engine['engine_name'],
        mecnid = engine['mecnid'],
        link = engine['link']
    )

    if id:
        item['item_id'] = id

    if name:
        item['name'] = name

    return item
