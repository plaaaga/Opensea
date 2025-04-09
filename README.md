## OpenSea Manager

### описание
софт для взаимодействия с OpenSea 

имеет 6 режимов:
1. *AutoMode* - круговой режим для покупки + продажи указанной NFT коллекции
2. *Buy NFT* - покупка указанной NFT по флору
3. *Sell NFT* - продажа указанной NFT по самому дорогому офферу либо по флору 
   (можно выставлять дешевле либо дороже флора)
4. *Cancel NFT listings* - отмена выставленных NFT на продажу
5. *Case Opener* - открытие кейсов для получения XP
6. *Transfer to Exchange* - вывод нативного баланса из сети на биржу

при запуске *AutoMode* - используются все настройки из `BUY_SETTINGS` и `SELL_SETTINGS`, за исключением `nft_address` 
в `SELL_SETTINGS`

---

### настройка

1. указать свои приватники в `privatekeys.txt`
2. в `settings.py` настройте софт под себя, указав прокси и тд

---

### запуск

1. установить необходимые либы `pip install -r requirements.txt`
2. запустить софт `py main.py`
3. создать базу данных (*Create Database -> New Database*)
4. стартуем неободимый режим

---

[🍭 kAramelniy 🍭](https://t.me/kAramelniy)

---
