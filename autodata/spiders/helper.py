from autodata.items import (MarkItem, ModelItem, EngineItem, EngineCodeItem,
    CarComponentItem, CarFeatureItem, WorkGroupItem, WorkItem)

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
    if not disabled:
        return None
    
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
    
    return item
