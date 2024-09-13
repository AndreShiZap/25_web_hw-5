import aiohttp
import asyncio
import logging
import websockets
from websockets import WebSocketServerProtocol, WebSocketProtocolError
import names
import aiofile
from aiopath import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)


async def get_exchange(current_date):
    shift = current_date.strftime("%d.%m.%Y")
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.privatbank.ua/p24api/exchange_rates?date={shift}') as resp:
            if resp.status == 200:
                r = await resp.json()
                result = {}
                if 'exchangeRate' in r:
                    currencies = {}
                    for rate in r['exchangeRate']:
                        if rate['currency'] in ['EUR', 'USD']:
                            currency = rate['currency']
                            currencies[currency] = {'sale': rate['saleRate'], 'purchase': rate['purchaseRate']}
                    result[shift] = currencies
                    return result


class Server:
    clients = set()
    log_file_path = Path("log.txt")

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except WebSocketProtocolError as err:
            logging.error(err)
        finally:
            await self.unregister(ws)

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message.startswith('exchange'):
                if message == 'exchange':
                    index_day = 0
                else:
                    index_day = int(message.split()[1])
                    if index_day > 10:
                        index_day = 10

                start_date = datetime.now()
                end_date = start_date - timedelta(days=index_day)
                tasks = []
                current_date = start_date
                while current_date >= end_date:
                    tasks.append(get_exchange(current_date))
                    current_date -= timedelta(days=1)
                m = await asyncio.gather(*tasks)
                result_lines = []
                for entry in m:
                    for date, currencies in entry.items():
                        result_lines.append(f"{date}: ")
                        for currency, rates in currencies.items():
                            line = f" {currency}: sale: {rates['sale']}, purchase: {rates['purchase']}"
                            result_lines.append(line)
                        result_lines.append('\n')
                result_string = ''.join(result_lines)

                await self.send_to_clients(result_string)

                async with aiofile.AIOFile(self.log_file_path, 'a') as afp:
                    await afp.write(f"{datetime.now()}: Exchange command executed from {ws.name}\n "
                                    f"_Response from server:\n{result_string}\n")
            else:
                await self.send_to_clients(f"{ws.name}: {message}")


async def main_serv():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8080):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    asyncio.run(main_serv())