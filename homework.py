import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from logging import FileHandler, StreamHandler
from telegram import Bot

load_dotenv()


class NoSuccessfulResponse(Exception):
    pass

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
    'При запросе к ресурсу {url} c параметрами {headers} и {params}'
    ' сервис недоступен {code}'
)
CONNECTION_ERROR = (
    'При запросе к ресурсу {url} c параметрами {headers} и {params}'
    ' вернулся код ответа {code}'
)
API_REJECTION_KEYS = ['code', 'error']
API_REJECTION_MESSAGE = (
    'Получен отказ в обслуживании при запросе к ресурсу {url}'
    ' c параметрами {headers} и {params},'
    ' ответ API с ключом "{key}" - "{error}"'
)
RESPONSE_NOT_DICT = 'Ответ не в ожидаемом формате {type}'
KEY_NOT_IN_RESPONSE = 'В ответе отсутствует ключ {key}'
HOMEWORKS_ERROR = 'Список работ не в формате {type}'
VERDICT_ERROR = 'Получен неизвестный статус работы {status}'
TOKEN_ERROR = 'Отсутствуют переменные окружения: {name}'
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
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(MESSAGE_SENT.format(message=message))
        return True
    except Exception as error:
        logger.exception(
            TELEGRAM_ERROR.format(message=message, error=error)
        )
        return False


def get_api_answer(timestamp):
    """Обработка ответа от API."""
    params = {'from_date': timestamp}
    api = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**api)
    except requests.RequestException as error:
        raise ConnectionError(API_NOT_AVAILABLE.format(code=error, **api))

    if response.status_code != 200:
        raise NoSuccessfulResponse(
            CONNECTION_ERROR.format(code=response.status_code, **api)
        )
    response_json = response.json()

    for key in API_REJECTION_KEYS:
        if key in response_json:
            raise requests.exceptions.InvalidJSONError(
                API_REJECTION_MESSAGE.format(
                    key=key, error=response_json.get(key), **api)
            )

    return response_json


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
    return HOMEWORK_STATUS_CHANGE.format(
        name=name, verdict=HOMEWORK_VERDICTS[status]
    )


def check_tokens():
    """Проверка токенов."""
    missing_tokens = [name for name in TOKENS_NAMES if not globals()[name]]
    if missing_tokens:
        logger.critical(TOKEN_ERROR.format(name=missing_tokens))
        return False
    
    return True


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
            if homeworks:
                message = parse_status(homeworks[0])
                if message != prev_message and send_message(bot, message):
                    prev_message = message
                    current_timestamp = response.get(
                        'current_date', current_timestamp
                    )

        except Exception as error:
            message = MESSAGE_ERROR.format(error=error)
            logger.error(message)
            if message != prev_message and send_message(bot, message):
                prev_message = message

        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
