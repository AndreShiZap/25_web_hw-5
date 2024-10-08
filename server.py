import aiohttp
import asyncio
import logging
import websockets
from websockets import WebSocketServerProtocol, WebSocketProtocolError
import names
import aiofile
from aiopath import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)


async def get_exchange():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5') as resp:
            if resp.status == 200:
                r = await resp.json()
                result_lines = []
                for entry in r:
                    line = f"{entry['ccy']}: sale: {entry['buy']}, purchase: {entry['sale']}"
                    result_lines.append(line)
                result_string = '\n'.join(result_lines)
            return result_string


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
            if message == 'exchange':
                m = await get_exchange()
                await self.send_to_clients(m)

                async with aiofile.AIOFile(self.log_file_path, 'a') as afp:
                    await afp.write(f"{datetime.now()}: Exchange command executed from {ws.name}\n")
            else:
                await self.send_to_clients(f"{ws.name}: {message}")


async def main_serv():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8080):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    asyncio.run(main_serv())