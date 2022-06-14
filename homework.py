import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from logging import FileHandler, StreamHandler
from telegram import Bot

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

API_NOT_AVAILABLE = (
    'При запросе к ресурсу {endpoint} c параметрами {headers} и {params}'
    ' сервис недоступен {code}'
)
CONNECTION_ERROR = (
    'При запросе к ресурсу {endpoint} c параметрами {headers} и {params}'
    ' вернулся код ответа {code}'
)
API_REJECTION = (
    'Ресурс вернул отказ в обслуживании, в ответе есть ключ "{key}"'
)
RESPONSE_NOT_DICT = 'Ответ не в ожидаемом формате {type}'
KEY_NOT_IN_RESPONSE = 'В ответе отсутствует ключ {key}'
HOMEWORKS_ERROR = 'Список работ не в формате {type}'
VERDICT_ERROR = 'Получен неизвестный статус работы {status}'
TOKEN_ERROR = 'Отсутствует переменная окружения {name}'
NO_HOMEWORKS = 'Отсутствуют данные о домашних работах'
HOMEWORK_STATUS_CHANGE = 'Изменился статус проверки работы "{name}". {verdict}'
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
    sent_message = False
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
    else:
        sent_message = True

    return sent_message


def get_api_answer(timestamp):
    """Обработка ответа от API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.ConnectionError as error:
        raise ConnectionError(
            API_NOT_AVAILABLE.format(
                endpoint=ENDPOINT, headers=HEADERS,
                params=params, code=error)
        )

    if response.status_code != 200:
        raise ConnectionError(
            CONNECTION_ERROR.format(
                endpoint=ENDPOINT, headers=HEADERS,
                params=params, code=response.status_code
            )
        )
    if 'code' in response.json():
        raise requests.HTTPError(API_REJECTION.format(key='code'))
    elif 'error' in response.json():
        raise requests.HTTPError(API_REJECTION.format(key='error'))

    return response.json()


def check_response(response):
    """Проверка ответа на запрос."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_NOT_DICT.format(type=dict))
    if 'homeworks' not in response:
        raise KeyError(KEY_NOT_IN_RESPONSE.format(key='homeworks'))
    homeworks = response.get('homeworks')
    if not type(homeworks) is list:
        raise TypeError(HOMEWORKS_ERROR.format(type=list))
    return homeworks


def parse_status(homework):
    """Обработка ответа и получение информации."""
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(VERDICT_ERROR.format(status=status))
    verdict = HOMEWORK_VERDICTS.get(status)

    return HOMEWORK_STATUS_CHANGE.format(name=name, verdict=verdict)


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
            current_timestamp = response.get(
                'current_date', current_timestamp
            )

        except Exception as error:
            message = MESSAGE_ERROR.format(error=error)
            logger.error(message)
            if message != prev_message:
                sent_message = send_message(bot, message)
                if sent_message is True:
                    prev_message = message

        else:
            if message != prev_message:
                sent_message = send_message(bot, message)
                if sent_message is True:
                    prev_message = message

        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
