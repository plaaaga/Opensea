from random import random

from modules.utils import sleeping, logger, sleep, choose_mode
from modules.retry import DataBaseError
from modules import *

from settings import (
    AUTOMODE_SETTINGS,
    SLEEP_AFTER_ACC,
    WITHDRAW_PARAMS,
    SLEEP_AFTER_TX,
    DEPOSIT_PARAMS,
    OPENSEA_CHAIN,
)


def run_modules(mode: int):
    while True:
        module_data = None
        print('')
        try:
            if (
                    mode == 1 and
                    (
                        random() * 100 < AUTOMODE_SETTINGS["sell_chance"] or
                        db.get_accounts_count() == 0
                    )
            ):
                module_data = db.get_random_bought_nft()

            if not module_data:
                module_data = db.get_random_module(mode=mode)
                if module_data == 'No more accounts left':
                    logger.success(f'All accounts done.')
                    return 'Ended'

            browser = Browser(
                db=db,
                encoded_pk=module_data["encoded_privatekey"],
                address=module_data["address"],
                proxy=module_data["proxy"],
            )
            wallet = Wallet(
                privatekey=module_data["privatekey"],
                encoded_pk=module_data["encoded_privatekey"],
                recipient=module_data["recipient"],
                browser=browser,
                db=db,
            )
            logger.info(f'[•] Web3 | {wallet.address}')

            if mode != 6:
                if (
                        mode in [1, 2] and
                        wallet.get_balance(chain_name=OPENSEA_CHAIN, human=True) < WITHDRAW_PARAMS["min_balance"]
                ):
                    wallet.withdraw_funds(chain=OPENSEA_CHAIN)
                    sleeping(SLEEP_AFTER_TX)

                module_data["module_info"]["status"] = OpenSea(wallet=wallet).run(
                    mode=mode,
                    force_nft_to_sell=module_data.get("sell_nft_data")
                )

            if mode == 6 or (mode == 1 and DEPOSIT_PARAMS["enabled"] and module_data['last']):
                if not wallet.recipient:
                    raise Exception(f'Couldnt send native tokens: no `recipient` provided')

                if mode == 1:
                    sleeping(SLEEP_AFTER_ACC)

                wallet.send_native(chain_name=OPENSEA_CHAIN)

                if mode == 6:
                    module_data["module_info"]["status"] = True

        except Exception as err:
            logger.error(f'[-] Web3 | Account error: {err}')
            db.append_report(privatekey=wallet.encoded_pk, text=str(err), success=False)

        finally:
            if type(module_data) == dict:
                if module_data.get("sell_nft_data"):
                    db.remove_bought_nft(
                        encoded_pk=module_data["encoded_privatekey"],
                        sell_nft_data=module_data["sell_nft_data"],
                        status=module_data["module_info"]["status"]
                    )
                elif mode == 1:
                    db.remove_module(module_data=module_data)
                else:
                    db.remove_account(module_data=module_data)

                if module_data['last']:
                    reports = db.get_account_reports(privatekey=wallet.encoded_pk)
                    TgReport().send_log(logs=reports)

                if module_data["module_info"]["status"] is True: sleeping(SLEEP_AFTER_ACC)
                else: sleeping(10)


if __name__ == '__main__':
    try:
        db = DataBase()

        while True:
            mode = choose_mode()

            match mode:
                case None: break

                case 'Delete and create new':
                    db.create_modules()

                case 'Hard Delete (with bought nft history) and create new':
                    db.create_modules(hard=True)

                case 1 | 2 | 3 | 4 | 5 | 6:
                    if run_modules(mode) == 'Ended': break
                    print('')


        sleep(0.1)
        input('\n > Exit\n')

    except DataBaseError as e:
        logger.error(f'[-] Database | {e}')

    except KeyboardInterrupt:
        pass

    finally:
        logger.info('[•] Soft | Closed')
