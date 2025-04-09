from random import choice, shuffle, randint
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from time import sleep, time
from os import path, mkdir
from hashlib import md5
import json

from .retry import DataBaseError
from modules.utils import logger, get_address, WindowName, sleeping
from settings import SHUFFLE_WALLETS, PROXY_TYPE, AUTOMODE_SETTINGS, DEPOSIT_PARAMS

from cryptography.fernet import InvalidToken


class DataBase:
    def __init__(self):

        self.modules_db_name = 'databases/modules.json'
        self.report_db_name = 'databases/report.json'
        self.opensea_db_name = 'databases/opensea.json'
        self.personal_key = None
        self.window_name = None

        # create db's if not exists
        if not path.isdir(self.modules_db_name.split('/')[0]):
            mkdir(self.modules_db_name.split('/')[0])

        for db_params in [
            {"name": self.modules_db_name, "value": "[]"},
            {"name": self.report_db_name, "value": "{}"},
            {"name": self.opensea_db_name, "value": "{}"},
        ]:
            if not path.isfile(db_params["name"]):
                with open(db_params["name"], 'w') as f: f.write(db_params["value"])

        amounts = self.get_amounts()
        logger.info(f'Loaded {amounts["modules_amount"]} modules for {amounts["accs_amount"]} accounts\n')
        if amounts["to_sell_amount"]:
            logger.opt(colors=True).warning(f'[!] Database | Run <white>1. Automode</white> to sell {amounts["to_sell_amount"]} NFTs\n')


    def set_password(self):
        if self.personal_key is not None: return

        logger.debug(f'Enter password to encrypt privatekeys (empty for default):')
        raw_password = input("")

        if not raw_password:
            raw_password = "@karamelniy dumb shit encrypting"
            logger.success(f'[+] Soft | You set empty password for Database\n')
        else:
            print(f'')
        sleep(0.2)

        password = md5(raw_password.encode()).hexdigest().encode()
        self.personal_key = Fernet(urlsafe_b64encode(password))


    def get_password(self):
        if self.personal_key is not None: return

        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)
        if not modules_db and not opensea_db.get("nfts_to_sell"): return

        try:
            if modules_db:
                first_pk = list(modules_db.keys())[0]
            else:
                if opensea_db.get("nfts_to_sell"):
                    first_pk = opensea_db["nfts_to_sell"][0]["encoded_pk"]

            temp_key = Fernet(urlsafe_b64encode(md5("@karamelniy dumb shit encrypting".encode()).hexdigest().encode()))
            self.decode_pk(pk=first_pk, key=temp_key)
            self.personal_key = temp_key
            return
        except InvalidToken: pass

        while True:
            try:
                logger.debug(f'Enter password to decrypt your privatekeys (empty for default):')
                raw_password = input("")
                password = md5(raw_password.encode()).hexdigest().encode()

                temp_key = Fernet(urlsafe_b64encode(password))
                self.decode_pk(pk=list(modules_db.keys())[0], key=temp_key)
                self.personal_key = temp_key
                logger.success(f'[+] Soft | Access granted!\n')
                return

            except InvalidToken:
                logger.error(f'[-] Soft | Invalid password\n')


    def encode_pk(self, pk: str, key: None | Fernet = None):
        if key is None:
            return self.personal_key.encrypt(pk.encode()).decode()
        return key.encrypt(pk.encode()).decode()


    def decode_pk(self, pk: str, key: None | Fernet = None):
        if key is None:
            return self.personal_key.decrypt(pk).decode()
        return key.decrypt(pk).decode()


    def create_modules(self, hard: bool = False):
        self.set_password()

        with open('input_data/privatekeys.txt') as f: private_keys = f.read().splitlines()

        if not DEPOSIT_PARAMS["enabled"]:
            recipients = [None for _ in range(len(private_keys))]
        else:
            with open('input_data/recipients.txt') as f: recipients = f.read().splitlines()
            if len(recipients) != len(private_keys):
                raise DataBaseError(f'Amount of privatekeys ({len(private_keys)}) must be same as amount of recipients ({len(recipients)})')

        if PROXY_TYPE == "file":
            with open('input_data/proxies.txt') as f:
                proxies = f.read().splitlines()
            if len(proxies) == 0 or proxies == [""] or proxies == ["http://login:password@ip:port"]:
                logger.error('You will not use proxy')
                proxies = [None for _ in range(len(private_keys))]
            else:
                proxies = list(proxies * (len(private_keys) // len(proxies) + 1))[:len(private_keys)]
        elif PROXY_TYPE == "mobile":
            proxies = ["mobile" for _ in range(len(private_keys))]

        with open(self.report_db_name, 'w') as f: f.write('{}')  # clear report db

        new_modules = {
            self.encode_pk(pk): {
                "address": get_address(pk),
                "modules": [
                    {"module_name": "manage", "status": "to_run"}
                    for _ in range(randint(*AUTOMODE_SETTINGS["trades_amount"]))
                ],
                "proxy": proxy,
                "recipient": recipient,
            }
            for pk, proxy, recipient in zip(private_keys, proxies, recipients)
        }

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(new_modules, f)
        if hard:
            with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)
            if opensea_db.get("blacklisted_nft"):
                opensea_db = {"blacklisted_nft": opensea_db["blacklisted_nft"]}
            else:
                opensea_db = {}

            with open(self.opensea_db_name, 'w', encoding="utf-8") as f: json.dump(opensea_db, f)

        amounts = self.get_amounts()
        logger.opt(colors=True).critical(f'Dont Forget To Remove Private Keys from <white>privatekeys.txt</white>!')
        logger.info(f'Created Database for {amounts["accs_amount"]} accounts with {amounts["modules_amount"]} modules!\n')


    def get_amounts(self):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        modules_len = sum([len(modules_db[acc]["modules"]) for acc in modules_db])

        for acc in modules_db:
            for index, module in enumerate(modules_db[acc]["modules"]):
                if module["status"] in ["failed", "cloudflare"]: modules_db[acc]["modules"][index]["status"] = "to_run"

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

        if self.window_name == None: self.window_name = WindowName(accs_amount=len(modules_db))
        else: self.window_name.accs_amount = len(modules_db)
        self.window_name.set_modules(modules_amount=modules_len)
        with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)

        return {
            'accs_amount': len(modules_db),
            'modules_amount': modules_len,
            "to_sell_amount": len(opensea_db.get("nfts_to_sell", []))
        }

    def get_accounts_count(self):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        return len(set([
            pk
            for pk in modules_db
            for module in modules_db[pk]["modules"]
            if module["status"] == "to_run"
        ]))

    def get_random_module(self, mode: int):
        self.get_password()

        last = False
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        if (
                not modules_db or
                (
                        [module["status"] for acc in modules_db for module in modules_db[acc]["modules"]].count('to_run') == 0 and
                        [module["status"] for acc in modules_db for module in modules_db[acc]["modules"]].count('cloudflare') == 0
                )
        ):
                return 'No more accounts left'

        index = 0
        while True:
            if index == len(modules_db.keys()) - 1: index = 0
            if SHUFFLE_WALLETS: privatekey = choice(list(modules_db.keys()))
            else: privatekey = list(modules_db.keys())[index]
            module_info = choice(modules_db[privatekey]["modules"])
            if module_info["status"] not in ["to_run", "cloudflare"]:
                index += 1
                continue

            if mode != 1 and [module["status"] for module in modules_db[privatekey]["modules"]].count('to_run') == 1:  # if no modules left for this account
                last = True

            return {
                'privatekey': self.decode_pk(pk=privatekey),
                'encoded_privatekey': privatekey,
                'proxy': modules_db[privatekey].get("proxy"),
                'address': modules_db[privatekey]["address"],
                'recipient': modules_db[privatekey].get("recipient"),
                'module_info': module_info,
                'last': last
            }

    def remove_module(self, module_data: dict):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        for index, module in enumerate(modules_db[module_data["encoded_privatekey"]]["modules"]):
            if module["module_name"] == module_data["module_info"]["module_name"] and module["status"] in ["to_run", "cloudflare"]:
                self.window_name.add_module()

                if module_data["module_info"]["status"] in [True, "completed"]:
                    modules_db[module_data["encoded_privatekey"]]["modules"].remove(module)
                elif module_data["module_info"]["status"] == "cloudflare":
                    modules_db[module_data["encoded_privatekey"]]["modules"][index]["status"] = "cloudflare"
                else:
                    modules_db[module_data["encoded_privatekey"]]["modules"][index]["status"] = "failed"
                break

        if [module["status"] for module in modules_db[module_data["encoded_privatekey"]]["modules"]].count('to_run') == 0 and \
                [module["status"] for module in modules_db[module_data["encoded_privatekey"]]["modules"]].count('cloudflare') == 0:
            self.window_name.add_acc()
        if not modules_db[module_data["encoded_privatekey"]]["modules"]:
            del modules_db[module_data["encoded_privatekey"]]

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

    def remove_account(self, module_data: dict):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        self.window_name.add_acc()
        if module_data["module_info"]["status"] in [True, "completed"]:
            del modules_db[module_data["encoded_privatekey"]]
        else:
            modules_db[module_data["encoded_privatekey"]]["modules"] = [{
                "module_name": modules_db[module_data["encoded_privatekey"]]["modules"][0]["module_name"],
                "status": "failed"
            }]

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

    def get_blacklisted_opensea_nfts(self):
        with open(self.opensea_db_name, encoding="utf-8") as f: return json.load(f).get("blacklisted_nft", [])

    def blacklist_opensea_nft(self, nft_id: str):
        with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)

        if opensea_db.get("blacklisted_nft") is None:
            opensea_db["blacklisted_nft"] = []
        opensea_db["blacklisted_nft"].append(nft_id)

        with open(self.opensea_db_name, 'w', encoding="utf-8") as f: json.dump(opensea_db, f)

    def save_bought_nft(self, wallet_data: dict):
        with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)

        if opensea_db.get("nfts_to_sell") is None:
            opensea_db["nfts_to_sell"] = []
        opensea_db["nfts_to_sell"].append(wallet_data)

        with open(self.opensea_db_name, 'w', encoding="utf-8") as f: json.dump(opensea_db, f)

    def get_random_bought_nft(self):
        self.get_password()

        with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)

        if not opensea_db.get("nfts_to_sell"):
            return None
        
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        random_module = choice(opensea_db["nfts_to_sell"])
        modules_list = modules_db[random_module["encoded_pk"]]["modules"] if modules_db.get(random_module["encoded_pk"]) else []
        last = (
                [
                    module["status"] 
                    for module in modules_list
                ].count('to_run') == 0 and
                [
                    nft_to_sell["encoded_pk"]
                    for nft_to_sell in opensea_db["nfts_to_sell"]
                ].count(random_module["encoded_pk"]) == 1
        )
        return {
            'privatekey': self.decode_pk(pk=random_module["encoded_pk"]),
            'encoded_privatekey': random_module["encoded_pk"],
            'proxy': random_module["proxy"],
            'address': random_module["address"],
            'recipient': random_module.get("recipient"),
            'module_info': {"module_name": "sell", "status": "to_run"},
            "sell_nft_data": {"address": random_module["nft_address"], "id": random_module["nft_id"]},
            'last': last,
        }

    def remove_bought_nft(self, encoded_pk: str, sell_nft_data: dict, status: bool):
        if status is not True: return

        with open(self.opensea_db_name, encoding="utf-8") as f: opensea_db = json.load(f)

        for nft_to_sell in opensea_db["nfts_to_sell"]:
            if (
                nft_to_sell["encoded_pk"] == encoded_pk and
                nft_to_sell["nft_address"] == sell_nft_data["address"] and
                nft_to_sell["nft_id"] == sell_nft_data["id"]
            ):
                opensea_db["nfts_to_sell"].remove(nft_to_sell)
                with open(self.opensea_db_name, 'w', encoding="utf-8") as f: json.dump(opensea_db, f)

                return True


    def get_wallets_amount(self):
        self.get_password()
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        return len(modules_db)


    def append_report(self, privatekey: str, text: str, success: bool = None):
        status_smiles = {True: '✅ ', False: "❌ ", None: ""}

        with open(self.report_db_name, encoding="utf-8") as f: report_db = json.load(f)

        if not report_db.get(privatekey): report_db[privatekey] = {'texts': [], 'success_rate': [0, 0]}

        report_db[privatekey]["texts"].append(status_smiles[success] + text)
        if success != None:
            report_db[privatekey]["success_rate"][1] += 1
            if success == True: report_db[privatekey]["success_rate"][0] += 1

        with open(self.report_db_name, 'w') as f: json.dump(report_db, f)


    def get_account_reports(self, privatekey: str, get_rate: bool = False):
        with open(self.report_db_name, encoding="utf-8") as f: report_db = json.load(f)

        decoded_privatekey = self.decode_pk(pk=privatekey)
        account_index = f"[{self.window_name.accs_done}/{self.window_name.accs_amount}]"
        if report_db.get(privatekey):
            account_reports = report_db[privatekey]
            if get_rate: return f'{account_reports["success_rate"][0]}/{account_reports["success_rate"][1]}'
            del report_db[privatekey]

            with open(self.report_db_name, 'w', encoding="utf-8") as f: json.dump(report_db, f)

            logs_text = '\n'.join(account_reports['texts'])
            tg_text = f'{account_index} <b>{get_address(pk=decoded_privatekey)}</b>\n\n{logs_text}'
            if account_reports["success_rate"][1]:
                tg_text += f'\n\nSuccess rate {account_reports["success_rate"][0]}/{account_reports["success_rate"][1]}'

            return tg_text

        else:
            return f'{account_index} <b>{get_address(pk=decoded_privatekey)}</b>\n\nNo actions'
