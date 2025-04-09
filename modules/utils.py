from inspect import getsourcefile
from datetime import datetime
from random import randint
from requests import post
from loguru import logger
from time import sleep
from web3 import Web3
from tqdm import tqdm
import ctypes
import sys
import os
sys.__stdout__ = sys.stdout # error with `import inquirer` without this string in some system
from inquirer import prompt, List

import settings


logger.remove()
logger.add(sys.stderr, format="<white>{time:HH:mm:ss}</white> | <level>{message}</level>")
windll = ctypes.windll if os.name == 'nt' else None # for Mac users


class WindowName:
    def __init__(self, accs_amount):
        try: self.path = os.path.abspath(getsourcefile(lambda: 0)).split("\\")[-3]
        except: self.path = os.path.abspath(getsourcefile(lambda: 0)).split("/")[-3]

        self.accs_amount = accs_amount
        self.accs_done = 0
        self.modules_amount = 0
        self.modules_done = 0

        self.update_name()

    def update_name(self):
        if os.name == 'nt':
            windll.kernel32.SetConsoleTitleW(f'OpenSea Manager [{self.accs_done}/{self.accs_amount}] | {self.path}')

    def add_acc(self):
        self.accs_done += 1
        self.update_name()

    def add_module(self, modules_done=1):
        self.modules_done += modules_done
        self.update_name()

    def new_acc(self):
        self.accs_done += 1
        self.modules_amount = 0
        self.modules_done = 0
        self.update_name()			# aG

    def set_modules(self, modules_amount: int):
        self.modules_done = 0
        self.modules_amount = modules_amount
        self.update_name()


class TgReport:
    def __init__(self, logs=""):
        self.logs = logs


    def update_logs(self, text: str):
        self.logs += f'{text}\n'


    def send_log(self, logs: str = None):
        notification_text = logs or self.logs

        texts = []
        while len(notification_text) > 0:
            texts.append(notification_text[:1900])
            notification_text = notification_text[1900:]

        if settings.TG_BOT_TOKEN:
            for tg_id in settings.TG_USER_ID:
                for text in texts:
                    # text = text.replace('+', '%2B')
                    try:
                        r = post(
                            url=f'https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage',
                            json={
                                'parse_mode': 'html',
                                'disable_web_page_preview': True,
                                'chat_id': tg_id,
                                'text': text,
                            }
                        )
                        if r.json().get("ok") != True: raise Exception(r.json())
                    except Exception as err: logger.error(f'[-] TG | Send Telegram message error to {tg_id}: {err}\n{text}')


def sleeping(*timing):
    if type(timing[0]) == list: timing = timing[0]
    if len(timing) == 2: x = randint(timing[0], timing[1])
    else: x = timing[0]
    desc = datetime.now().strftime('%H:%M:%S')
    for _ in tqdm(range(x), desc=desc, bar_format='{desc} | [•] Sleeping {n_fmt}/{total_fmt}'):
        sleep(1)


def make_border(table_elements: dict):
    left_margin = 22
    space = 2
    horiz = '━'
    vert = '║'
    conn = 'o'

    if not table_elements: return "No text"

    key_len = max([len(key) for key in table_elements.keys()])
    val_len = max([len(str(value)) for value in table_elements.values()])
    text = f'{" " * left_margin}{conn}{horiz * space}'

    text += horiz * (key_len + space) + conn
    text += horiz * space
    text += horiz * (val_len + space) + conn

    text += '\n'

    for table_index, element in enumerate(table_elements):
        text += f'{" " * left_margin}{vert}{" " * space}'

        text += f'{element}{" " * (key_len - len(element) + space)}{vert}{" " * space}'
        text += f'{table_elements[element]}{" " * (val_len - len(str(table_elements[element])) + space)}{vert}'
        text += "\n" + " " * left_margin + conn + horiz * space
        text += horiz * (key_len + space) + conn
        text += horiz * (space * 2 + val_len) + conn + '\n'
    return text


def choose_mode():
    questions = [
        List('prefered_path', message="Choose action",
             choices=[
                '(Re)Create Database',
                '1. AutoMode',
                '2. Buy NFT',
                f'3. Sell NFT ({settings.SELL_SETTINGS["sell_type"].title()})',
                '4. Cancel NFT listings',
                '5. Case Opener',
                '6. Transfer to Exchange',
             ])]
    answer = prompt(questions, raise_keyboard_interrupt=True)
    if answer is None: return None
    answer = answer['prefered_path']

    if answer == '(Re)Create Database':
        questions = [
            List('db_type', message="You want to delete current Database and create new?",
                 choices=[
                     'No',
                     'Delete and create new',
                     'Hard Delete (with bought nft history) and create new',
                 ])]
        answer = prompt(questions, raise_keyboard_interrupt=True)
        if answer is None: return None
        answer = answer['db_type']
        return answer

    else:
        mode_num = str(answer).split(' ')[0].removesuffix('.')
        if mode_num.isdigit():
            return int(mode_num)
        return answer


def get_address(pk: str):
    return Web3().eth.account.from_key(pk).address
