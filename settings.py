
SHUFFLE_WALLETS     = True                      # True | False - перемешивать ли кошельки
RETRY               = 3                         # кол-во попыток при ошибках / фейлах

ETH_MAX_GWEI        = 20
GWEI_MULTIPLIER     = 1.05                      # умножать текущий гвей при отправке транз на 5%
TO_WAIT_TX          = 1                         # сколько минут ожидать транзакцию. если транза будет находится в пендинге после указанного времени то будет считатся зафейленной

RPCS                = {
    'ethereum'  : 'https://eth.drpc.org',
    'arbitrum'  : 'https://arbitrum.meowrpc.com',
    'optimism'  : 'https://optimism.drpc.org',
    'base'      : 'https://mainnet.base.org',
    'ronin'     : 'https://api.roninchain.com/rpc',
}


OPENSEA_CHAIN       = "ronin"                   # в какой сети выполнять действия

WITHDRAW_PARAMS     = {                         # настройки вывода с биржи (для Automde и Buy NFT)
    "min_balance"           : 0.001,            # если баланс в сети `OPENSEA_CHAIN` будет ниже указанного - выводит с биржи
    "exchange"              : ["Binance", "OKX"], # с каких биржи выводить ETH (Bybit | OKX | Bitget | Binance)
    "withdraw_range"        : [0.01, 0.02],     # выводить от 0.01 ETH до 0.02 ETH
}

DEPOSIT_PARAMS      = {                         # настройки отправки нативного токена на биржу в конце работы аккаунта (для Automode)
    "enabled"               : False,            # нужно ли после всех действий отправлять нативный токен на биржу
    "keep_balance"          : [0.001, 0.0002],  # сколько нативного токена оставлять в сети
}

# --- AUTOMODE SETTINGS ---
AUTOMODE_SETTINGS = {
    "trades_amount"     : [2, 4],               # делать от 2 до 4 кругов (1 круг - купить+продать)
    "sell_chance"       : 35,                   # при запуске автомода - каждый раз шанс 35% на продажу уже купленных нфт
}

# --- BUY SETTINGS ---
BUY_SETTINGS        = {
    "collection_name"   : "axie-ronin",         # название коллекции для покупки (берется в конце ссылки https://opensea.io/collection/axie-ronin)
    "max_price"         : 5.9,                  # максимальная цена NFT в нативном токене (ETH/RON)
    "floor_additional"  : 0.1,                  # цена floor + 0.1 = минимальная цена по которой софт будет покупать NFT...
                                                # ... сделано для тех коллекций где большой актив, и не дают выкупать...
                                                # ...самые дешевые NFT, поэтому фейлятся транзы
}

# --- SELL SETTINGS ---
SELL_SETTINGS       = {
    "nft_address"       : "0x32950db2a7164ae833121501c797d79e7b79d74c", # адрес NFT контракта который продавать

    "sell_type"         : "floor",              # тип продажи NFT:
                                                # "offer" - сливать по офферу
                                                # "floor" - сливать по флору, используя настройку floor_difference
                                                # "price" - выставлять NFT в ценовом диапазоне используя настройку price_range

    "offer_min_price"   : 0.01,                 # для "offer": если цена лучшего оффера будет ниже - софт будет ожидать повышения
    "floor_difference"  : -0.001,               # для "floor": на сколько ETH ниже флора продавать NFT
                                                # (для выставления выше флора используйте положительные числа)
    "price_range"       : [0.013, 0.016]        # для "price": выставлять NFT в диапазоне от 0.013 до 0.016
}

SLEEP_AFTER_TX      = [10, 20]                  # задержка после каждой транзы 10-20 секунд
SLEEP_AFTER_ACC     = [20, 40]                  # задержка после каждого аккаунта 20-40 секунд


# --- PERSONAL SETTINGS ---

OKX_API_KEY         = ''
OKX_API_SECRET      = ''
OKX_API_PASSWORD    = ''

BYBIT_KEY           = ''
BYBIT_SECRET        = ''

BITGET_KEY          = ''
BITGET_SECRET       = ''
BITGET_PASSWORD     = ''

BINANCE_KEY         = ''
BINANCE_SECRET      = ''

PROXY_TYPE          = "mobile"              # "mobile" - для мобильных/резидентских прокси, указанных ниже | "file" - для статичных прокси из файла `proxies.txt`
PROXY               = 'http://log:pass@ip:port' # что бы не использовать прокси - оставьте как есть
CHANGE_IP_LINK      = 'https://changeip.mobileproxy.space/?proxy_key=...&format=json'

TG_BOT_TOKEN        = ''                    # токен от тг бота (`12345:Abcde`) для уведомлений. если не нужно - оставляй пустым
TG_USER_ID          = []                    # тг айди куда должны приходить уведомления.