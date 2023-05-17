import uuid
import requests
import scrapy
from scrapy import Selector
from scrapy.responsetypes import Response

from datetime import datetime
from bs4 import BeautifulSoup

class AptekaSpiderSpider(scrapy.Spider):
    name = "apteka_spider"
    allowed_domains = ["apteka-ot-sklada.ru"]
    start_urls = [
        "https://apteka-ot-sklada.ru/catalog/kosmetika/sredstva-dlya-tela/depilyatsiya-zhenskoe", 
        "https://apteka-ot-sklada.ru/catalog/letnie-serii/dlya-zagara",
        "https://apteka-ot-sklada.ru/catalog/izdeliya-meditsinskogo-naznacheniya/aptechki",
    ]

    def parse(self, response: Response):
        items = response.css(
            '.ui-card.ui-card_size_default' \
            '.ui-card_outlined.goods-card' \
            '.goods-grid__cell.goods-grid__cell_size_3'
        )
        sections = response.css('.ui-breadcrumbs__list span::text').extract()
        for item in items:
            timestamp = datetime.timestamp(datetime.now())
            rpc = int(uuid.uuid4()) # rpc сгенерировал сам
            title = item.css('.goods-card__link span::text').get()
            item_path = item.css('.goods-card__link::attr(href)').get()
            url = 'https://' + self.allowed_domains[-1] + item_path
            marketing_tags = item.css(
                '.goods-tags.goods-card__tags.text.text_size_caption span::text'
            ).extract()
            brand = title # не нашел способа как корректно определить бренд
            price_data = self.__get_item_price_data(item)
            stock = {'in_stock': bool(price_data['original']), 'count': 0}
            assets = self.__get_assets_data(item)
            metadata = self.__get_metadata(url)
            variants = 1 # не нашел на странице по этому дефолтное значение
            yield {
                "timestamp": timestamp,
                "RPC": rpc,
                "title": title,
                "url": url,
                "marketing_tags": [tag.strip() for tag in marketing_tags],
                "brand": brand,
                "section": [section.strip() for section in sections if section.strip()],
                "price_data": price_data,
                "stock": stock,
                "assets": assets,
                "metadata": metadata,
                "variants": variants
            }

        href = response.css(
            '.ui-pagination__item.ui-pagination__item_next a::attr(href)'
        ).get()
        if href:
            next_page_url = 'https://' + self.allowed_domains[-1] + href
            yield scrapy.Request(
                url=next_page_url,
                callback=self.parse
            )
    
    def __get_item_price_data(self, item: Selector) -> dict:
        sale_tag = 'Скидка 0%'
        original_price_str = item.css(
            '.goods-card__cost-old' \
            '.text.text_size_default' \
            '.text_weight_medium::text'
        ).get()
        current_price_str = item.css(
            '.goods-card__cost.text.' \
            'text_size_title.text_weight_bold.' \
            'goods-card__cost_new::text'
        ).get()

        if original_price_str and current_price_str:
            current_price = float(current_price_str.strip().split()[0])
            original_price = float(original_price_str.strip().split()[0])
            sale_tag = f'Скидка {(1 - current_price/original_price) * 100:.2f} %'
        else:
            original_price_str = item.css('.goods-card__price span::text').get()
            original_price = float(original_price_str.strip().split()[0]) \
                                if original_price_str else 0
            current_price = original_price

        return {
            "current": current_price,
            "original": original_price,
            "sale_tag": sale_tag
        }

    def __get_assets_data(self, item: Selector) -> dict:
        image_url = item.css('.goods-photo.goods-card__image::attr(src)').get()
        # Дополнительные параметры не совсем понял как выгрузить поэтому пустые
        set_images = list()
        view360 = list()
        video = list()

        return {
            "main_image": image_url,
            "set_images": set_images,
            "view360": view360,
            "video": video
        }

    def __get_metadata(self, url: str) -> dict:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        description_tag = soup.find(class_='custom-html content-text')
        description = ' '.join(description_tag.stripped_strings) \
                        if description_tag else ''
        location = soup.find('span', attrs={'itemtype': 'location'})

        return {
            "__description": description,
            "СТРАНА ПРОИЗВОДИТЕЛЬ": location.text if location else None
        }