from settings import RETRY
from time import sleep

from loguru import logger

from requests.exceptions import JSONDecodeError as json_error1
from json.decoder import JSONDecodeError as json_error2


class CustomError(Exception): pass

class DataBaseError(Exception): pass


def have_json(func):
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        try:
            response.json()
        except (json_error1, json_error2):
            error_msg = response.text[:350].replace("\n", " ")
            raise Exception(f'bad json response: {error_msg}')

        return response
    return wrapper


def retry(
        source: str,
        module_str: str,
        exceptions,
        retries: int = RETRY,
        not_except=CustomError,
        to_raise: bool = True
):
    def decorator(f):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < retries:
                try:
                    return f(*args, **kwargs)

                except not_except as e:
                    if to_raise: raise CustomError(f'{module_str}: {e}')
                    else: return False

                except exceptions as e:
                    logger.error(f'[-] {source} | {module_str} | {e} [{attempt+1}/{retries}]')
                    attempt += 1
                    if attempt == retries:
                        if to_raise: raise ValueError(f'{module_str}: {e}')
                        else: return False
                    else:
                        sleep(2)
        return newfn
    return decorator
