from datetime import datetime, timezone, timedelta
from tls_client import Session
from requests import get
from time import sleep
from uuid import uuid4

from modules.retry import retry, have_json
from modules.config import OPENSEA_QUERIES
from modules.database import DataBase
from modules.utils import logger
import settings


class Browser:
    def __init__(self, db: DataBase, encoded_pk: str, address: str, proxy: str):
        self.max_retries = 5
        self.db = db
        self.encoded_pk = encoded_pk
        self.address = address

        if proxy == "mobile":
            if settings.PROXY not in ['https://log:pass@ip:port', 'http://log:pass@ip:port', 'log:pass@ip:port', '', None]:
                self.proxy = settings.PROXY
            else:
                self.proxy = None
        else:
            if proxy not in ['https://log:pass@ip:port', 'http://log:pass@ip:port', 'log:pass@ip:port', '', None]:
                self.proxy = "http://" + proxy.removeprefix("https://").removeprefix("http://")
                logger.debug(f'[•] Soft | Got proxy {self.proxy}')
            else:
                self.proxy = None

        if self.proxy:
            if proxy == "mobile": self.change_ip()
        else:
            logger.warning(f'[-] Soft | You dont use proxies!')

        self.session = self.get_new_session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            "Origin": "https://opensea.io",
            "Referer": "https://opensea.io/",
            "X-App-Id": "os2-web",
            "X-Auth-Address": self.address.lower()
        })


    def get_new_session(self):
        session = Session(
            client_identifier="safari_16_0",
            random_tls_extension_order=True
        )

        if self.proxy:
            session.proxies.update({'http': self.proxy, 'https': self.proxy})

        return session


    @have_json
    def send_request(self, **kwargs):
        if kwargs.get("session"):
            session = kwargs["session"]
            del kwargs["session"]
        else:
            session = self.session

        if kwargs.get("method"): kwargs["method"] = kwargs["method"].upper()
        return session.execute_request(**kwargs)


    def change_ip(self):
        if settings.CHANGE_IP_LINK not in ['https://changeip.mobileproxy.space/?proxy_key=...&format=json', '']:
            print('')
            while True:
                try:
                    r = get(settings.CHANGE_IP_LINK)
                    if 'mobileproxy' in settings.CHANGE_IP_LINK and r.json().get('status') == 'OK':
                        logger.debug(f'[+] Proxy | Successfully changed ip: {r.json()["new_ip"]}')
                        return True
                    elif not 'mobileproxy' in settings.CHANGE_IP_LINK and r.status_code == 200:
                        logger.debug(f'[+] Proxy | Successfully changed ip: {r.text}')
                        return True
                    logger.error(f'[-] Proxy | Change IP error: {r.text} | {r.status_code}')
                    sleep(10)

                except Exception as err:
                    logger.error(f'[-] Browser | Cannot get proxy: {err}')


    @retry(source="Browser", module_str="Get account NFTs", exceptions=Exception)
    def search_for_nft(self, nft_address: str, nft_id: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "ProfileItemsListQuery",
                "query": OPENSEA_QUERIES["get_nfts"],
                "variables": {
                    "address": self.address,
                    "limit": 100,
                    "sort": {
                        "by": "RECEIVED_DATE",
                        "direction": "DESC"
                    }
                }
            },
            headers={"X-Query-Signature": "167992aeec2f66e69ca600b1a462817233f231769590d45037fb71ec85a2485e"}
        )
        if r.json().get("data", {}).get("profileItems", {}).get("items") is None:
            raise Exception(f'Unexpected response: {r.json()}')
        return [
            nft
            for nft in r.json()["data"]["profileItems"]["items"]
            if (
                    nft["contractAddress"].lower() == nft_address.lower() and
                    (nft_id is None or nft["id"] == nft_id)
            )
        ]

    @retry(source="Browser", module_str="Get NFT market data", exceptions=Exception)
    def get_nft_market_data(self, nft_address: str, nft_token_id: str, chain: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "ListingFlowQuery",
                "query": OPENSEA_QUERIES["get_market_data"],
                "variables": {
                    "address": self.address,
                    "identifiers": [{
                        "chain": chain,
                        "contractAddress": nft_address,
                        "tokenId": nft_token_id
                    }]
                }
            },
        )

        if r.json().get("data") is None or not r.json()["data"].get("itemsByIdentifiers"):
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["data"]["itemsByIdentifiers"][0]

    @retry(source="Browser", module_str="Get floor sell transaction", exceptions=Exception)
    def get_price_sell_transaction(self, chain: str, nft_address: str, nft_token_id: str, price: str):
        time_now = datetime.now(tz=timezone.utc)

        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "ListingFlowTimelineQuery",
                "query": OPENSEA_QUERIES["get_sell_steps"],
                "variables": {
                    "address": self.address,
                    "listings": [
                        {
                            "endTime": (time_now + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z",
                            "item": {
                                "chain": chain,
                                "contractAddress": nft_address,
                                "tokenId": nft_token_id
                            },
                            "pricePerItem": {
                                "contractAddress": "0x0000000000000000000000000000000000000000",
                                "unit": price
                            },
                            "quantity": 1,
                            "startTime": time_now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
                        }
                    ],
                    "useCreatorFee": True
                }
            }
        )

        if r.json().get("data") is None or not r.json()["data"].get("createListings", {}).get("actions"):
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["data"]["createListings"]["actions"]

    @retry(source="Browser", module_str="Get floor sell transaction", exceptions=Exception)
    def list_nft_for_sell(self, chain: str, orders: list, signature: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "ListingsFlowTimelineMutation",
                "query": OPENSEA_QUERIES["list_for_sale"],
                "variables": {
                    "chain": chain,
                    "orders": orders,
                    "signature": signature,
                }
            }
        )

        if (
                r.json().get("data") and
                r.json()["data"].get("createListingsV2", {}).get("__typename") == "OrderCreationSuccessResponse"
        ):
            return True

        else:
            raise Exception(f'Unexpected response: {r.json()}')

    @retry(source="Browser", module_str="Get cancel listing tx", exceptions=Exception)
    def get_cancel_listing_tx(self, chain: str, nft_address: str, nft_token_id: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "CancelListingsForItemsFlowQuery",
                "query": OPENSEA_QUERIES["cancel_listing"],
                "variables": {
                    "address": self.address,
                    "items": [
                        {
                            "chain": chain,
                            "contractAddress": nft_address,
                            "tokenId": nft_token_id
                        }
                    ]
                }
            },
        )

        if r.json().get("data") is None or not r.json().get("data", {}).get("cancelItemsListings", {}).get("actions"):
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["data"]["cancelItemsListings"]["actions"]

    @retry(source="Browser", module_str="Is terms accepted", exceptions=Exception)
    def os_is_terms_accepted(self):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "TermsAcceptance",
                "query": OPENSEA_QUERIES["terms_acceptance"],
                "variables": {
                    "address": self.address
                }
            },
        )

        if r.json().get("data") is None or r.json().get("data", {}).get("profileByAddress", {}).get("hasAcceptedTerms") is None:
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["data"]["profileByAddress"]["hasAcceptedTerms"]

    @retry(source="Browser", module_str="Get nonce", exceptions=Exception)
    def os_get_nonce(self):
        r = self.send_request(
            method="POST",
            url='https://opensea.io/__api/auth/siwe/nonce',
        )

        if r.json().get("nonce") is None:
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["nonce"]

    @retry(source="Browser", module_str="Authorization", exceptions=Exception)
    def os_auth(self, typed_data: dict, signature: str):
        r = self.send_request(
            method="POST",
            url='https://opensea.io/__api/auth/siwe/verify',
            json={
                "message": typed_data,
                "signature": signature
            },
        )

        if r.json().get("user") is None:
            raise Exception(f'Unexpected response: {r.json()}')
        return True

    @retry(source="Browser", module_str="Accept Terms", exceptions=Exception)
    def os_accept_terms(self):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "AcceptTermsMutation",
                "query": "mutation AcceptTermsMutation($address: Address!) {\n  acceptTerms(address: $address)\n}",
                "variables": {"address": self.address}
            },
        )

        if r.json().get("data") is None or r.json().get("data", {}).get("acceptTerms") is not True:
            raise Exception(f'Unexpected response: {r.json()}')

    @retry(source="Browser", module_str="Get Unopened Cases", exceptions=Exception)
    def os_get_unopened_cases(self):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "unopenedShipmentsQuery",
                "query": OPENSEA_QUERIES["unopened_cases"],
                "variables": {
                    "address": self.address,
                    "filter": {
                        "isOpen": False,
                        "leaderboardKey": "LEADERBOARD_600"
                    }
                }
            },
            headers={"X-Query-Signature": "b1634ebc56534f084bccf2e285870ef7d5da593a79a333172e40fd3ec3a25904"}
        )

        if r.json().get("data") is None or r.json().get("data", {}).get("profileShipments") is None:
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["data"]["profileShipments"]

    @retry(source="Browser", module_str="Open Case", exceptions=Exception)
    def os_open_case(self, case_id: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "openShipment",
                "query": OPENSEA_QUERIES["open_case"],
                "variables": {"id": case_id}
            },
            headers={"X-Query-Signature": "c3fad7a660e83a17a7430274b035f1b7c9ac5b1f7bc79e30980c6fb704e4e0a4"}
        )

        if r.json().get("data") is None or r.json().get("data", {}).get("openShipmentV2") is None:
            raise Exception(f'Unexpected response: {r.json()}')

        result = r.json()["data"]["openShipmentV2"]
        if result["error"]:
            raise Exception(f'Couldnt open case: {result["error"]}')

        case_from = result["shipmentOwnership"]["distribution"]["collection"]["name"]
        case_reward_amount = result["shipmentOwnership"]["rewards"][0]["points"]
        case_reward_name = result["shipmentOwnership"]["rewards"][0]["type"]

        if int(case_reward_amount) == case_reward_amount: case_reward_amount = int(case_reward_amount)

        self.db.append_report(
            privatekey=self.encoded_pk,
            text=f'opened case from "{case_from}" +{case_reward_amount} {case_reward_name}',
            success=True
        )
        logger.success(f'[+] OpenSea | Opened case from "{case_from}" +{case_reward_amount} {case_reward_name}')

        return True

    @retry(source="Browser", module_str="Get XP", exceptions=Exception)
    def os_get_xp(self):
        r = self.send_request(
             method="POST",
             url="https://gql.opensea.io/graphql",
             json={
                 "operationName": "useLeaderboardEntryQuery",
                 "query": OPENSEA_QUERIES["get_xp"],
                 "variables": {
                     "algorithmGroup": "ALGORITHM_GROUPING_600",
                     "identifier": self.address,
                     "leaderboardKey": "LEADERBOARD_600"
                 }
             }
         )

        if r.json().get("data") is None or r.json().get("data", {}).get("leaderboardEntryV2", {}).get('score') is None:
            raise Exception(f'Unexpected response: {r.json()}')

        return int(r.json()["data"]["leaderboardEntryV2"]["score"])


    @retry(source="Browser", module_str="Get listed nfts", exceptions=Exception)
    def get_listed_nfts(self, collection_slug: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "CollectionItemsListQuery",
                "query": OPENSEA_QUERIES["get_listed_nfts"],
                "variables": {
                    "collectionSlug": collection_slug,
                    "limit": 100,
                    "sort": {"by": "PRICE", "direction": "ASC"}
                }
            },
            headers={"X-Query-Signature": "512682514d2c8d6ac112bc50c8baa72b884b644fd139c9c0188b43f57e102d8b"}
        )

        if r.json().get("data") is None or r.json().get("data", {}).get("collectionItems", {}).get("items") is None:
            raise Exception(f'Unexpected response: {r.json()}')

        return r.json()["data"]["collectionItems"]["items"]


    @retry(source="Browser", module_str="Get Buy NFT tx", exceptions=Exception)
    def get_buy_nft_tx(self, from_chain: str, price: str, nft_address: str, nft_token_id: str):
        r = self.send_request(
            method="POST",
            url='https://gql.opensea.io/graphql',
            json={
                "operationName": "BuyItemQuery",
                "query": OPENSEA_QUERIES["get_buy_nft_tx"],
                "variables": {
                    "address": self.address,
                    "blurAuthToken": None,
                    "itemQuantities": [{
                            "item": {
                                "chain": from_chain,
                                "contractAddress": nft_address,
                                "tokenId": nft_token_id
                            },
                            "orderId": None,
                            "pricePerItem": {
                                "contractAddress": "0x0000000000000000000000000000000000000000",
                                "unit": price
                            },
                            "quantity": 1
                    }],
                    "substituteItems": False
                }
            },
        )

        if r.json().get("data") is None:
            return False, f"Unexpected response: {r.json()}"

        elif r.json()["data"].get("buyItems", {}).get("errors"):
            error_reason = r.json()['data']['buyItems']['errors'][0]['__typename']
            if error_reason in ["OrderNotFound", "EstimateGasFailureError"]:
                return False, error_reason
            else:
                return False, f"Unexpected response: {r.json()['data']['buyItems']['errors'][0]['__typename']}"

        elif not r.json()["data"].get("buyItems", {}).get("actions"):
            return False, f"Unexpected response: {r.json()}"

        return True, r.json()["data"]["buyItems"]["actions"][0]["transactionSubmissionData"]
