import json, telebot, os, time
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from brownie import accounts, chain, Wei, Contract, ZERO_ADDRESS, web3

load_dotenv(find_dotenv())
telegram_bot_key = os.environ.get('WAVEY_ALERTS_BOT_KEY')
bot = telebot.TeleBot(telegram_bot_key)
WALLET = '0x114Fe577BC999D7B854959859BfeA5CA0e0269D4'
DEBT_REPAYER = '0x9eb6BF2E582279cfC1988d3F2043Ff4DF18fa6A0'
SLEEP_SECONDS = 7
LOG_ITERATIONS = 100

TOKENS = {
    '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599': {
        'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
        'antoken': '0x17786f3813E6bA35343211bd8Fe18EC4de14F28b',
        'symbol': 'WBTC',
        'threshold': 1e6,
        'decimals': 8,
    },
    '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e': {
        'address': '0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e',
        'antoken': '0xde2af899040536884e062D3a334F2dD36F34b4a4',
        'symbol': 'YFI',
        'threshold': 1e16,
        'decimals': 18,
    },
}

tx_params = {}
is_dev = web3.provider.endpoint_uri == 'http://127.0.0.1:8545'
if is_dev:
    wallet = accounts.at(WALLET, force=True)
else:
    wallet = accounts.load('inverse', os.getenv('PASSWORD'))
    tx_params = {}
    tx_params['max_fee'] = 70e9
    tx_params['priority_fee'] = 3e9
    tx_params['gas_limit'] = 300_000
    # tx_params['nonce'] = 445

def main():
    if is_dev:
        setup()
    repayer = Contract(DEBT_REPAYER, owner=wallet)
    count = 0
    while True:
        count += 1
        if count % LOG_ITERATIONS == 0:
            print_stuff = True
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            print(f'--- {dt_string} ---')
            print(f'Logging every {SLEEP_SECONDS * LOG_ITERATIONS / 60} minutes')
        else:
            print_stuff = False
        for address in TOKENS:
            balance = Contract(address).balanceOf(repayer)
            antoken = Contract(TOKENS[address]['antoken'])
            decimals = TOKENS[address]["decimals"]
            symbol = TOKENS[address]["symbol"]
            should_claim = balance > TOKENS[address]["threshold"]
            if print_stuff:
                print(f'Current contract {symbol} balance: {balance/10**decimals}',flush=True)
                print(f'{"✅" if should_claim else "🟥"} {symbol} threshold: {TOKENS[address]["threshold"]/10**decimals}',flush=True)
            if should_claim:
                an_balance = antoken.balanceOf(WALLET)
                min = repayer.amountOut(antoken.address, address, an_balance)[0] * .99
                try:
                    tx = repayer.sellDebt(antoken.address, an_balance, min, tx_params)
                    repayment = tx.events['debtRepayment']
                    m = f'Received: {repayment["receiveAmount"]/10**decimals} {TOKENS[repayment["underlying"]]["symbol"]}\nPaid: {repayment["paidAmount"]/1e8} {antoken.symbol()}'
                    m += f'\n\n🔗 [View on Etherscan](https://etherscan.io/tx/{tx.txid})'
                    print(m,flush=True)
                    send_alert(m)
                except Exception as e:
                    print(e,flush=True)
                    m = f'Unable to send transaction for {symbol}.\n\nCurrent balance available: {balance/10**decimals}'
                    send_alert(m)
        time.sleep(SLEEP_SECONDS)

def send_alert(m):
    bot.send_message('-789090497', m, parse_mode="markdown", disable_web_page_preview = True)

def setup():
    whale = accounts.at('0x218B95BE3ed99141b0144Dba6cE88807c4AD7C09', force=True)
    wbtc = Contract('0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',owner=whale)
    wbtc.transfer(DEBT_REPAYER, 1e8)