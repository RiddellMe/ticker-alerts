import logging
import os
import shutil
import sys
import time
from datetime import datetime
from enum import Enum
from typing import List

import gtts
import playsound
from pydantic import BaseModel
from requests import Session

_YAHOO_FINANCE_URL = "https://au.finance.yahoo.com/quote/"
_DAILY_MKT_HTML_PREFIX = '<span class="Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)" data-reactid="32">'
_EXTENDED_MKT_HTML_PREFIX = '<span class="C($primaryColor) Fz(24px) Fw(b)" data-reactid="37">'
_HTML_SUFFIX = '</span>'
_TMP_DIR = "temp"
_ALERT_PATH = "alert.mp3"
_ARG_FORMATTING_DESCRIPTOR = "Incorrect script args. Format: '<TICKER>,<ALERT_PRICE>,<PRICE_DIRECTION>', where PRICE_DIRECTION is '+' or '-'."

log = logging.getLogger(__name__)


class PriceDirection(str, Enum):
    POSITIVE = "+"
    NEGATIVE = "-"


class TickerData(BaseModel):
    ticker: str
    alert_price: float
    price_direction: PriceDirection


def scrape_for_ticker_prices(repeat_alerts: bool = True):
    num_args = len(sys.argv)
    if num_args > 1:
        ticker_data_args = sys.argv[1:num_args]
        ticker_data_list = []
        for arg in ticker_data_args:
            ticker_values = arg.split(",")
            validate_arg_values(ticker_values)
            ticker_data_list.append(
                TickerData(ticker=ticker_values[0].strip(), alert_price=float(ticker_values[1].strip()),
                           price_direction=PriceDirection(ticker_values[2].strip())))
        log.info(f"Scraping price for {len(ticker_data_list)} tickers.")
        with Session() as session:
            while ticker_data_list:
                reset_temp_dir()
                for ticker_data in ticker_data_list:
                    req = session.request("GET", os.path.join(_YAHOO_FINANCE_URL, ticker_data.ticker))
                    lines = req.text.splitlines()
                    price = determine_current_ticker_price(lines)
                    log.info(f"Price of [{ticker_data.ticker}] is [{price}]")
                    is_price_breached = play_alert_if_price_breached(ticker_data, price)
                    if is_price_breached and not repeat_alerts:
                        ticker_data_list.remove(ticker_data)
                        log.info(f"Removed {ticker_data} from list")
                    time.sleep(5)
    else:
        log.info(
            f"{_ARG_FORMATTING_DESCRIPTOR}\n"
            f"Separate ticker related csv with a space (they are args, after all)\n"
            f"Example terminal command: python {sys.argv[0]} GME,140.52,+ PLTR,39.50,-"
        )
        time.sleep(10)


def reset_temp_dir():
    if os.path.exists(_TMP_DIR):
        shutil.rmtree(_TMP_DIR)
    os.mkdir(_TMP_DIR)


def determine_current_ticker_price(lines: List[str]) -> float:
    price = 0
    for line in lines:
        if _EXTENDED_MKT_HTML_PREFIX in line:
            price = get_price_from_html(line, _EXTENDED_MKT_HTML_PREFIX)
            break
        elif _DAILY_MKT_HTML_PREFIX in line:
            price = get_price_from_html(line, _DAILY_MKT_HTML_PREFIX)
    return float(price)


def play_alert_if_price_breached(ticker_data: TickerData, price: float) -> bool:
    if (ticker_data.price_direction == PriceDirection.POSITIVE and price >= ticker_data.alert_price) or \
            (ticker_data.price_direction == PriceDirection.NEGATIVE and price <= ticker_data.alert_price):
        text_to_speech_path = os.path.join(_TMP_DIR, f"{ticker_data.ticker}_alert.mp3")
        gtts.gTTS(f"{ticker_data.ticker} is now ${price}").save(text_to_speech_path)
        playsound.playsound(_ALERT_PATH)
        time.sleep(1)
        playsound.playsound(text_to_speech_path)
        return True
    else:
        return False


def validate_arg_values(data_list):
    if len(data_list) != 3:
        raise RuntimeError(f"{_ARG_FORMATTING_DESCRIPTOR}")
    for arg in data_list:
        if not arg:
            raise RuntimeError(f"{_ARG_FORMATTING_DESCRIPTOR}")


def get_price_from_html(line: str, starting_string: str) -> str:
    beginning_index = line.index(starting_string) + len(starting_string)
    extra_chars = line[beginning_index:].index(_HTML_SUFFIX)
    return line[beginning_index:beginning_index + extra_chars]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | ln:%(lineno)d - %(message)s")
    scrape_for_ticker_prices()
