from datetime import datetime, timezone
from random import randint, uniform
from decimal import Decimal
from loguru import logger
from time import sleep
from json import loads

from .utils import sleeping
from .wallet import Wallet
from .config import OPENSEA_CHAINS, CHAIN_TOKENS
from settings import SELL_SETTINGS, SLEEP_AFTER_TX, OPENSEA_CHAIN, BUY_SETTINGS, RETRY


class OpenSea(Wallet):
    def __init__(self, wallet: Wallet):
        super().__init__(
            privatekey=wallet.privatekey,
            encoded_pk=wallet.encoded_pk,
            db=wallet.db,
            browser=wallet.browser,
            recipient=wallet.recipient
        )

        self.from_chain = OPENSEA_CHAIN
        self.os_chain = OPENSEA_CHAINS[OPENSEA_CHAIN]
        self.native_token = CHAIN_TOKENS[OPENSEA_CHAIN]

        self.web3 = self.get_web3(self.from_chain)

        self.old_xp = 0
        self.mode = None


    def run(self, mode: int, force_nft_to_sell: dict | None):
        if force_nft_to_sell:
            mode = 3
        self.mode = mode
        self.auth_v2()

        if mode in [1, 2]:
            status = self.buy_nft_collection()

        elif mode in [3, 4]:
            status = self.process_my_nfts(force_nft_to_sell=force_nft_to_sell)

        elif mode == 5:
            self.old_xp = self.browser.os_get_xp()

            status = self.open_cases()

            self.parse_xp()

        return status


    def process_my_nfts(self, force_nft_to_sell: dict | None):
        if force_nft_to_sell:
            sell_nft_address = force_nft_to_sell["address"]
            sell_nft_id = force_nft_to_sell["id"]
        else:
            sell_nft_address = SELL_SETTINGS["nft_address"]
            sell_nft_id = None

        collections_to_sell = self.browser.search_for_nft(nft_address=sell_nft_address, nft_id=sell_nft_id)
        if not collections_to_sell:
            logger.warning(f'[-] OpenSea | Not found NFTs with address {sell_nft_address}')
            self.db.append_report(
                privatekey=self.encoded_pk,
                text='not found nfts',
                success=False,
            )
            return True

        elif force_nft_to_sell:
            collections_to_sell = collections_to_sell[:1]

        if self.mode == 3:
            if SELL_SETTINGS["sell_type"] not in ["offer", "floor", "price"]:
                raise Exception(f'Unsupported sell type "{SELL_SETTINGS["sell_type"]}"')
            return self.sell_collections(collections_to_sell)

        elif self.mode == 4:
            collections_to_cancel = [
                collection
                for collection in collections_to_sell
                if collection["lowestListingForOwner"]
            ]
            if not collections_to_cancel:
                logger.warning(f'[-] OpenSea | No NFT listings to cancel')
                self.db.append_report(
                    privatekey=self.encoded_pk,
                    text='no nft listings to cancel',
                    success=True,
                )
                return True
            return self.cancel_collection_sell(collections_to_cancel)


    def auth_v2(self):
        nonce = self.browser.os_get_nonce()
        issued_at = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
        sign_text = f"""opensea.io wants you to sign in with your Ethereum account:
{self.address}

Click to sign in and accept the OpenSea Terms of Service (https://opensea.io/tos) and Privacy Policy (https://opensea.io/privacy).

URI: https://opensea.io/
Version: 1
Chain ID: 8453
Nonce: {nonce}
Issued At: {issued_at}"""
        typed_data = {
            "domain": "opensea.io",
            "address": self.address,
            "statement": "Click to sign in and accept the OpenSea Terms of Service (https://opensea.io/tos) and Privacy Policy (https://opensea.io/privacy).",
            "uri": "https://opensea.io/",
            "version": "1",
            "chainId": 8453,
            "nonce": nonce,
            "issuedAt": issued_at
        }
        signature = self.sign_message(text=sign_text)
        self.browser.os_auth(typed_data=typed_data, signature=signature)
        if not self.browser.os_is_terms_accepted():
            self.browser.os_accept_terms()


    def sell_collections(self, collections: list):
        all_nft_sold = True
        for collection in collections:
            collection_name = collection["collection"]["slug"]
            nft_name = collection["name"] or collection["tokenId"]
            if collection["lowestListingForOwner"]:
                current_price = collection["lowestListingForOwner"]["pricePerItem"]["token"]["unit"]
                logger.error(f'[-] OpenSea | NFT "{nft_name}": already listed on sell for {current_price} {self.native_token}')
                self.db.append_report(
                    privatekey=self.encoded_pk,
                    text=f'"{nft_name}" already listed on sell for {current_price} {self.native_token}',
                    success=False,
                )
                continue

            min_price_notified = False
            on_offers_notified = False
            try:
                while True:
                    nft_market_data = self.browser.get_nft_market_data(
                        nft_address=collection["contractAddress"],
                        nft_token_id=collection["tokenId"],
                        chain=self.from_chain
                    )
                    if SELL_SETTINGS["sell_type"] != "offer":
                        break

                    # todo: "offer" must sold instantly
                    if not nft_market_data["bestOffer"]:
                        if not on_offers_notified:
                            min_price_notified = False
                            on_offers_notified = True
                            logger.warning(f'[-] OpenSea | Collection "{collection_name}" has no offers, waiting for it...')
                        sleep(10)
                        continue

                    offer_price = nft_market_data["bestOffer"]["pricePerItem"]["token"]["unit"]
                    if offer_price < SELL_SETTINGS["offer_min_price"]:
                        if not min_price_notified:
                            on_offers_notified = False
                            min_price_notified = True
                            logger.warning(
                                f'[-] OpenSea | Current top offer price is {offer_price} {self.native_token}, '
                                f'waiting for {SELL_SETTINGS["offer_min_price"]} {self.native_token}'
                            )
                        sleep(10)
                        continue

                    list_price = offer_price
                    break

                if SELL_SETTINGS["sell_type"] == "floor":
                    floor_price = float(nft_market_data["collection"]["floorPrice"]["pricePerItem"]["token"]["unit"])

                    max_rounder = max([
                        len(str(digit)[str(digit).find('.') + 1:])
                        for digit in [floor_price, SELL_SETTINGS["floor_difference"]]
                    ])
                    list_price = round(floor_price + SELL_SETTINGS["floor_difference"], max_rounder)

                elif SELL_SETTINGS["sell_type"] == "price":
                    list_price = round(uniform(*SELL_SETTINGS["price_range"]), randint(4, 5))

                if SELL_SETTINGS["sell_type"] == "offer":
                    tx_label = f'Sell "{nft_name}" for {list_price} {self.native_token}'
                    logger_message = f'Sell "{nft_name}" for {list_price} {self.native_token}'
                else:
                    tx_label = f'list "{nft_name}" for sell for {list_price} {self.native_token}'
                    logger_message = f'List "{nft_name}" for sell for {list_price} {self.native_token}'

                self.list_nft_for_sale(
                    collection=collection,
                    list_price=list_price,
                    sell_tx_label=tx_label,
                    logger_message=logger_message,
                )

                if collection != collections[-1]:
                    sleeping(SLEEP_AFTER_TX)

            except Exception as err:
                all_nft_sold = False
                logger.error(f'[-] OpenSea | Failed to list for sale "{nft_name}": {err}')
                self.db.append_report(
                    privatekey=self.encoded_pk,
                    text=f'failed to list for sell "{nft_name}"',
                    success=False,
                )

        return all_nft_sold


    def list_nft_for_sale(self, collection: dict, list_price: float, sell_tx_label: str, logger_message: str):
        collection_name = collection["collection"]["slug"]

        sell_tx_steps = self.browser.get_price_sell_transaction(
            chain=self.from_chain,
            nft_address=collection["contractAddress"],
            nft_token_id=collection["tokenId"],
            price=str(list_price),
        )
        for sell_tx_step in sell_tx_steps:
            if sell_tx_step["__typename"] in ["ItemApprovalAction", "AssetApprovalActionType"]:
                tx_label = f'approve "{collection_name}" for OpenSea'

            elif sell_tx_step["__typename"] in ["CreateListingsAction", "CreateOrderActionType"]:
                sell_tx_data = sell_tx_step
                break

            else:
                tx_label = f'{sell_tx_step["__typename"]} "{collection_name}"'

            completed_tx = {
                'from': self.address,
                'to': self.web3.to_checksum_address(sell_tx_step["transactionSubmissionData"]["to"]),
                'data': sell_tx_step["transactionSubmissionData"]["data"],
                'chainId': self.web3.eth.chain_id,
                'nonce': self.web3.eth.get_transaction_count(self.address),
                'value': int(sell_tx_step["transactionSubmissionData"]["value"]),
                **self.get_gas(chain_name=self.from_chain)
            }
            self.sent_tx(
                chain_name=self.from_chain,
                tx=completed_tx,
                tx_label=tx_label,
                tx_raw=True
            )
            sleeping(SLEEP_AFTER_TX)

        typed_data = loads(sell_tx_data["signatureRequest"]["message"])
        signature = self.sign_message(typed_data=typed_data)

        for order in sell_tx_data["orders"]:
            if order.get("__typename"):
                del order["__typename"]

            for offer in order["offer"]:
                if offer.get("__typename"):
                    del offer["__typename"]

            for consideration in order["consideration"]:
                if consideration.get("__typename"):
                    del consideration["__typename"]

        self.browser.list_nft_for_sell(
            chain=self.from_chain,
            orders=sell_tx_data["orders"],
            signature=signature,
        )

        self.db.append_report(
            privatekey=self.encoded_pk,
            text=sell_tx_label,
            success=True,
        )
        logger.info(f'[+] OpenSea | {logger_message}')


    def cancel_collection_sell(self, collections: list):
        all_nft_canceled = True
        for collection in collections:
            nft_name = collection["name"] or collection["tokenId"]
            current_price = collection["lowestListingForOwner"]["pricePerItem"]["token"]["unit"]
            try:
                cancel_actions = self.browser.get_cancel_listing_tx(
                    chain=self.from_chain,
                    nft_address=collection["contractAddress"],
                    nft_token_id=collection["tokenId"],
                )

                for cancel_action in cancel_actions:
                    if cancel_action["__typename"] == "CancelOrdersAction":
                        break
                    else:
                        logger.error(f'[-] OpenSea | Unexpected action "{cancel_action["__typename"]}" on canceling "{nft_name}"')

                sell_tx = {
                    'from': self.address,
                    'to': self.web3.to_checksum_address(cancel_action["transactionSubmissionData"]["to"]),
                    'data': cancel_action["transactionSubmissionData"]["data"],
                    'chainId': self.web3.eth.chain_id,
                    'nonce': self.web3.eth.get_transaction_count(self.address),
                    'value': 0,
                    **self.get_gas(chain_name=self.from_chain)
                }
                tx_label = f'cancel listing "{nft_name}" for {current_price} {self.native_token}'

                self.sent_tx(
                    chain_name=self.from_chain,
                    tx=sell_tx,
                    tx_label=tx_label,
                    tx_raw=True
                )

                if collection != collections[-1]:
                    sleeping(SLEEP_AFTER_TX)

            except Exception as err:
                all_nft_canceled = False
                logger.error(f'[-] OpenSea | Failed to cancel listing "{nft_name}": {err}')
                self.db.append_report(
                    privatekey=self.encoded_pk,
                    text=f'failed to cancel listing "{nft_name}"',
                    success=False,
                )

        return all_nft_canceled


    def open_cases(self):
        all_case_opened = True
        unopened_cases = self.browser.os_get_unopened_cases()
        if not unopened_cases:
            self.old_xp = -1
            self.db.append_report(
                privatekey=self.encoded_pk,
                text=f"no unopened cases found",
                success=True,
            )
            logger.info(f'[•] OpenSea | No unopened cases found')

        else:
            for case in unopened_cases:
                try:
                    self.browser.os_open_case(case_id=case["id"])
                except Exception as err:
                    all_case_opened = False
                    logger.error(f'[-] OpenSea | Open from "{case["distribution"]["collection"]["name"]}" case error: {err}')
                    self.db.append_report(
                        privatekey=self.encoded_pk,
                        text=f'open case from "{case["distribution"]["collection"]["name"]}"',
                        success=False,
                    )

                if case != unopened_cases[-1]:
                    sleep(randint(3, 7))

        return all_case_opened


    def parse_xp(self):
        for _ in range(3):
            acc_xp = self.browser.os_get_xp()
            if acc_xp > self.old_xp:
                break
            sleep(5)

        self.db.append_report(
            privatekey=self.encoded_pk,
            text=f"\n⭐️ {acc_xp} XP",
        )
        logger.info(f'[•] OpenSea | Account XP: {acc_xp}')


    def buy_nft_collection(
            self,
            max_floor_notified: bool = False,
            skip_nfts: list | None = None,
            retry: int = 0,
    ):
        if skip_nfts is None:
            skip_nfts = self.db.get_blacklisted_opensea_nfts()

        try:
            cheapest_nft = None
            collection_nfts = self.browser.get_listed_nfts(collection_slug=BUY_SETTINGS["collection_name"])
            min_price = float(collection_nfts[0]["bestListing"]["pricePerItem"]["token"]["unit"]) + BUY_SETTINGS["floor_additional"]
            for nft in collection_nfts:
                floor_price = float(nft["bestListing"]["pricePerItem"]["token"]["unit"])
                if (
                        nft["id"] not in skip_nfts and
                        floor_price >= min_price
                ):
                    cheapest_nft = nft
                    break

            if cheapest_nft is None:
                raise Exception(
                    f'Not found any NFTs on "{BUY_SETTINGS["collection_name"]}" '
                    f'with min price {min_price} {self.native_token}'
                )

            nft_name = cheapest_nft["name"] or cheapest_nft["tokenId"]
            if float(floor_price) > BUY_SETTINGS["max_price"]:
                if max_floor_notified is False:
                    max_floor_notified = True
                    logger.warning(
                        f'[-] OpenSea | Current "{BUY_SETTINGS["collection_name"]}" floor price is {floor_price} {self.native_token}, '
                        f'waiting for {BUY_SETTINGS["max_price"]} {self.native_token}'
                    )
                    sleep(10)
                return self.buy_nft_collection(max_floor_notified=max_floor_notified, skip_nfts=skip_nfts, retry=retry)

            status, buy_tx = self.browser.get_buy_nft_tx(
                from_chain=self.from_chain,
                price=floor_price,
                nft_address=cheapest_nft["contractAddress"],
                nft_token_id=cheapest_nft["tokenId"],
            )
            if status is False:
                logger.warning(f'[-] OpenSea | Failed to buy "{nft_name}": {buy_tx}')
                if "OrderNotFound" in str(buy_tx):
                    self.db.blacklist_opensea_nft(nft_id=cheapest_nft["id"])
                skip_nfts.append(cheapest_nft["id"])
                return self.buy_nft_collection(skip_nfts=skip_nfts, retry=retry)

            elif int(buy_tx["value"]) != int(Decimal(str(floor_price)) * Decimal(1e18)):
                logger.warning(
                    f'[-] OpenSea | Failed to buy "{nft_name}": price changed from {floor_price} {self.native_token} '
                    f'to {int(buy_tx["value"]) / 1e18} {self.native_token}')
                return self.buy_nft_collection(skip_nfts=skip_nfts, retry=retry)

            buy_tx = {
                'from': self.address,
                'to': self.web3.to_checksum_address(buy_tx["to"]),
                'data': buy_tx["data"],
                'chainId': self.web3.eth.chain_id,
                'nonce': self.web3.eth.get_transaction_count(self.address),
                'value': int(buy_tx["value"]),
                **self.get_gas(chain_name=self.from_chain)
            }
            tx_label = f'buy "{nft_name}" for {floor_price} {self.native_token}'

            self.sent_tx(
                chain_name=self.from_chain,
                tx=buy_tx,
                tx_label=tx_label,
                tx_raw=True
            )
            if self.mode == 1:
                self.db.save_bought_nft({
                    "encoded_pk": self.encoded_pk,
                    "address": self.address,
                    "proxy": self.browser.proxy,
                    'recipient': self.recipient,
                    "nft_address": cheapest_nft["contractAddress"],
                    "nft_id": cheapest_nft["id"],
                })
            return True

        except Exception as err:
            logger.warning(f'[-] OpenSea | Failed to buy "{BUY_SETTINGS["collection_name"]}": {err}')
            if ("tx is failed" in str(err) or "tx failed" in str(err)) and retry < RETRY:
                sleeping(SLEEP_AFTER_TX)
                return self.buy_nft_collection(skip_nfts=skip_nfts, retry=retry+1)

            self.db.append_report(
                privatekey=self.encoded_pk,
                text=f'failed to buy "{BUY_SETTINGS["collection_name"]}"',
                success=False,
            )
            return False
