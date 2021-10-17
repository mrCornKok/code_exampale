import asyncio
import json
import logging
import uuid
import random
import telebot
import atexit
import aiohttp
from time import sleep


logging.basicConfig(
    filename='cian_robot.log',
    level=logging.INFO,
    format='%(asctime)s %(name)s[%(levelname)s]: %(message)s',
)


class CianApi:
    PREFIX = "https://api.cian.ru/"
    SEARCH = "search-offers/v2/search-offers-desktop/"
    GET_TOKEN = "sopr-experiments/listing-user-activity-time/"
    ADMINS = {
        2434894834389: 'Mr mouse',
        3479032387647: 'Mrs tiger',
    }
    DELAY = 5
    HEADERS = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4600.0 Iron Safari/537.36",
        "accept": "*/*",
        "origin": "https://www.cian.ru",
        "accept-encoding": "gzip, deflate, br",
        "content-type": "text/plain;charset=UTF-8"
    }
    NEEDED_KEYS = (
        'roomsCount',
        'fullUrl',
        'totalArea',
        'creationDate',
        'isNew',
        'id',
        'floorNumber',
        'building',
        'phones',
        'bargainTerms',
        'title',
        'description'
    )

    def __init__(self):
        self.cookies = None
        self.log = logging.getLogger('RuslanLogger')
        self.log.setLevel('INFO')
        self.bot = telebot.TeleBot(
            '1445460911:AAGZrjBrz7WvdVspA58z_nWhSAlTH8zwzmo',
            parse_mode=None,
        )
        self.max_retries = 7
        self.known_offers = []
        with open('cian_robot_known_offers.json', 'w+') as json_file:
            self.known_offers = json.load(json_file)

        asyncio.get_event_loop().run_until_complete(self.refresh_cookies())

    async def refresh_cookies(self):
        for _ in range(self.max_retries):
            try:
                self.log.info('Trying to set new session')
                async with aiohttp.ClientSession() as session:
                    response = await session.post(
                        f'{CianApi.PREFIX}{CianApi.GET_TOKEN}',
                        json={
                            "user_id": None,
                            "t": round(random.uniform(2000.0000000000000, 16999.9999999999999), 13),
                            "ml_search_session_guid": uuid.uuid4().hex,
                        },
                        headers=CianApi.HEADERS,
                    )
                    self.cookies = response.cookies
                    return
            except Exception:
                await asyncio.sleep(self.DELAY)
                self.log.error(f'Error occurred while trying to get new cookies: {response}')

    async def get_offers(self):
        responses_list = []
        result = []
        page_counter = 1

        while True:
            for _ in range(self.max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        response = await session.post(
                            CianApi.PREFIX + CianApi.SEARCH,
                            headers=CianApi.HEADERS,
                            cookies=self.cookies,
                            json={
                                "jsonQuery": {
                                    "foot_min": {
                                        "type": "range",
                                        "value": {"lte": 20}},
                                    "_type": "flatrent",
                                    "room": {
                                        "type": "terms",
                                        "value": [1, 2]},
                                    "for_day": {
                                        "type": "term",
                                        "value": "!1"},
                                    "price": {
                                        "type": "range",
                                        "value": {"lte": 110000}},
                                    "only_foot": {
                                        "type": "term",
                                        "value": "2"},
                                    "engine_version": {
                                        "type": "term",
                                        "value": 2},
                                    "currency": {
                                        "type": "term",
                                        "value": 2},
                                    "geo": {
                                        "type": "geo",
                                        "value": [{"type": "underground","id": 338}]},
                                    "page": {
                                        "type": "term",
                                        "value": page_counter}}
                            },
                        )
                        responses_list.append(await response.json())
                        page_counter += 1
                        break
                except Exception as ex:
                    self.log.error(
                        f'Error occurred while trying to get json from CIAN offers response: {ex}'
                    )

                    await asyncio.sleep(self.DELAY)
                    await self.refresh_cookies()

            if responses_list and len(responses_list[-1]['data']['offersSerialized']) < 1:
                break

        if not responses_list:
            raise ValueError('there is no valid responses')

        for offer in [responses['data']['offersSerialized'] for responses in responses_list]:
            result.append({
                key: offer[key] for key in self.NEEDED_KEYS
            })
        return result

    def send_notifications(self, offers: list, admins: dict):
        try:
            for offer in offers:
                [self.bot.send_message(admin, self.compile_offer(offer)) for admin in admins]
                self.known_offers.append(offer)
            with open('cian_robot_known_offers.json', 'w+') as json_file:
                json.dump(self.known_offers, json_file)
        except Exception as ex:
            self.log.error(f'Error occurred while trying to send message to admins: {ex}')

    def compile_offer(self, offer):
        return f"{offer['description'][:80]}...\n" \
                 f"{offer['fullUrl']}\n\n" \
                 f"{str('{:,}'.format(offer['bargainTerms']['price']))} {offer['bargainTerms']['paymentPeriod']}\n" \
                 f"{(str('{:,}'.format(offer['bargainTerms']['deposit'])) if offer['bargainTerms']['deposit'] else '')} deposit\n" \
                 f"{str(offer['floorNumber']) + '/' + str(offer['building']['floorsCount'])} floor\n" \
                 f"{str(offer['roomsCount'])} rooms; {offer['totalArea']}  m²\n\n" \
                 f"Creation date: {offer['creationDate']}"


@atexit.register
def goodbye():
    print(f"Shutting down application")


if __name__ == '__main__':
    work_machine = CianApi()
    true = True

    while True and true:
        offers = asyncio.get_event_loop().run_until_complete(work_machine.get_offers())
        new_offers = []

        for offer in offers:
            new_offers.append(offer) if offer not in work_machine.known_offers else None

        if len(new_offers) > 0:
            work_machine.send_notifications(new_offers, CianApi.ADMINS)
            new_offers.clear()

        sleep(work_machine.DELAY)
