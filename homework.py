import logging
import os, requests, sys, time

from dotenv import load_dotenv
from logging import StreamHandler
from telegram import Bot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
DAYS = 30
PERIOD_OF_TIME = DAYS * 86400
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(f'Бот отправил сообщение "{message}"')
    except Exception as error:
        logger.error(f'При отправке сообщения "{message}" возникла ошибка "{error}".')


def get_api_answer(timestamp):
    from_date = timestamp or int(time.time())
    params = {'from_date': from_date}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        logger.error(f'При запросе к эндпоинту вернулся код ответа {response.status_code}')
        raise requests.ConnectionError(f'При запросе к эндпоинту вернулся код ответа {response.status_code}')
    return response.json()


def check_response(response):
    if not type(response) is dict:
        logger.error('Ответ не в формате dict')
        raise TypeError('Ответ не в формате dict')
    if not type(response.get('homeworks')) is list:
        logger.error('Список работ не в формате list')
        raise TypeError('Список работ не в формате list')
    return response.get('homeworks')


def parse_status(homework):
    if not homework.get('status'):
        logger.error('Отсутствует данные "status"')
        raise KeyError('Отсутствуют данные "status"')
    if homework.get('status') not in HOMEWORK_STATUSES:
        logger.error('Неизвестный статус проверки работы')
        raise KeyError('Неизвестный статус проверки работы')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    TOKENS = [
        [PRACTICUM_TOKEN, 'practicum token'],
        [TELEGRAM_TOKEN, 'telegram token'],
        [TELEGRAM_CHAT_ID, 'telegram chat id'],
    ]
    tokens_ok = True
    for token, token_name in TOKENS:
        if not token:
            logger.critical(
                f'Отсутствует переменная окружения {token_name}'
            )
            tokens_ok = False
    return tokens_ok


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return None

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    from_date = current_timestamp - PERIOD_OF_TIME
    message = ''
    prev_message = ''

    while True:
        try:
            response = get_api_answer(from_date)
            homeworks = check_response(response)
            if not homeworks:
                logger.error('Отсутствуют данные о домашних работах')
                raise ValueError('Отсутствуют данные о домашних работах')
            message = parse_status(homeworks[0])
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != prev_message:
                prev_message = message
                send_message(bot, message)

        else:
            if message != prev_message:
                prev_message = message
                send_message(bot, message)
                


if __name__ == '__main__':
    main()
