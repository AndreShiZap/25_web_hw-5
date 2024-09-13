# Консольна утиліта, яка повертає курс EUR та USD ПриватБанку протягом останніх кількох днів.
# Не більше, ніж за останні 10 днів. Кількість днів вказується у командної строчці.
# Має можливість додатково отримати курс інших валют, вказав їх у якості аргументів командної строки.

import json
import argparse

import aiohttp
import asyncio
import platform

from datetime import datetime, timedelta


class HttpError(Exception):
    pass


async def request(url: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HttpError(f"Error status: {resp.status} for {url}")
        except (aiohttp.ClientConnectorError, aiohttp.InvalidURL) as err:
            raise HttpError(f'Connection error: {url}', str(err))


async def get_exchange(date, currency_list: list):
    shift = date.strftime("%d.%m.%Y")
    try:
        response = await request(f'https://api.privatbank.ua/p24api/exchange_rates?date={shift}')
        result = {}
        if 'exchangeRate' in response:
            currencies = {}
            for rate in response['exchangeRate']:
                if rate['currency'] in currency_list:
                    currency = rate['currency']
                    currencies[currency] = {'sale': rate['saleRate'], 'purchase': rate['purchaseRate']}
            result[shift] = currencies
            return result
    except HttpError as err:
        print(err)
        return None


async def main():
    parser = argparse.ArgumentParser(description='Exchange rate PB')
    parser.add_argument(dest='day', type=int, default=0, choices=range(0, 11), help="Number of days from today's date")
    parser.add_argument(dest='currency', nargs='*', type=str, help='list list of currencies in addition to EUR and USD')
    args = parser.parse_args()

    index_day = args.day
    start_date = datetime.now()
    end_date = start_date - timedelta(days=index_day)

    currency_add = args.currency
    currency_add.append('EUR')
    currency_add.append('USD')

    tasks = []
    current_date = start_date
    while current_date >= end_date:
        tasks.append(get_exchange(current_date, currency_add))
        current_date -= timedelta(days=1)
    results = await asyncio.gather(*tasks)
    return [result for result in results if result]


if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    r = asyncio.run(main())
    print(json.dumps(r, indent=4, ensure_ascii=False))
