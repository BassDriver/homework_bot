import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from logging import FileHandler, StreamHandler
from requests.exceptions import RequestException
from telegram import Bot, TelegramError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKENS_NAMES = [
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID'
]

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

API_NOT_AVL = 'Сервис недоступен {error}'
HTTP_ERROR = (
    'При запросе к ресурсу {endpoint} c параметрами {headers} и {params}'
    ' вернулся код ответа {code}'
)
RESP_NOT_DICT = 'Ответ не в ожидаемом формате {type}'
KEY = 'homeworks'
KEY_NOT_IN_RESP = 'В ответе отсутствует ключ {key}'
HOMEWORKS_ERROR = 'Список работ не в формате {type}'
VERDICT_ERROR = 'Получен неизвестный статус работы'
TOKEN_ERROR = 'Отсутствует переменная окружения {name}'
NO_HOMEWORKS = 'Отсутствуют данные о домашних работах'
MESSAGE_ERROR = 'Сбой в работе программы: {error}'
MESSAGE_ERROR_SENT = 'Сообщение об ошибке "{message}" успешно отправлено'
MESSAGE_SENT = 'Сообщение "{message}" успешно отправлено'
TELEGRAM_ERROR = (
    'При отправке сообщения "{message}"'
    ' возникла ошибка "{error}".'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = StreamHandler(sys.stdout)
file_handler = FileHandler(__file__ + '.log')

formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(MESSAGE_SENT.format(message=message))
    except Exception as error:
        logger.exception(
            TELEGRAM_ERROR.format(message=message, error=error)
        )
        raise TelegramError(
            TELEGRAM_ERROR.format(message=message, error=error)
        )


def get_api_answer(timestamp):
    """Обработка ответа от API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        raise RequestException(API_NOT_AVL.format(error=error))
    else:
        if response.status_code != 200:
            raise requests.HTTPError(
                HTTP_ERROR.format(
                    endpoint=ENDPOINT, headers=HEADERS,
                    params=params, code=response.status_code
                )
            )
        return response.json()


def check_response(response):
    """Проверка ответа на запрос."""
    if not isinstance(response, dict):
        raise TypeError(RESP_NOT_DICT.format(type=dict))
    if KEY not in response:
        raise KeyError(KEY_NOT_IN_RESP.format(key=KEY))
    homeworks = response.get('homeworks')
    if not type(homeworks) is list:
        raise TypeError(HOMEWORKS_ERROR.format(type=list))
    return homeworks


def parse_status(homework):
    """Обработка ответа и получение информации."""
    name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        raise KeyError(VERDICT_ERROR)

    return f'Изменился статус проверки работы "{name}". {verdict}'


def check_tokens():
    """Проверка токенов."""
    tokens_ok = True
    for name in TOKENS_NAMES:
        if not globals()[name]:
            logger.critical(TOKEN_ERROR.format(name=name))
            tokens_ok = False
    return tokens_ok


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return None

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message = ''
    prev_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                raise ValueError(NO_HOMEWORKS)
            message = parse_status(homeworks[0])
            current_timestamp = response.get('current_date', current_timestamp)

        except Exception as error:
            message = MESSAGE_ERROR.format(error=error)
            logger.error(message)
            if message != prev_message:
                send_message(bot, message)
                prev_message = message
                time.sleep(RETRY_TIME)
            else:
                time.sleep(RETRY_TIME)

        else:
            if message != prev_message:
                send_message(bot, message)
                prev_message = message
                time.sleep(RETRY_TIME)
            else:
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
