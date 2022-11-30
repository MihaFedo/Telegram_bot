import requests
import logging
from logging import StreamHandler
import sys
import time
import telegram
import os
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

LAST_MESSAGE_TEXT_DICT = {
    'last_text': ''
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def send_message(bot, message):
    """Отправка сообщения пользователю, если сообщение не повторяется.
    Проверка, что новое сообщение отличается от предыдущего.
    """
    try:
        #if LAST_MESSAGE_TEXT_DICT['last_text'] != message:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        LAST_MESSAGE_TEXT_DICT['last_text'] = message
        logger.debug(f'ОК - Сообщение отправлено с текстом: {message}')
    except telegram.error.TelegramError as error:
        logger.error(f'Сообщение не отправлено: {error}')


def get_api_answer(current_timestamp):
    """Запрос к основному URL и преобразование ответа из json."""
    payload = {'from_date': current_timestamp}
    request_param = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': payload,
        'timeout': 3,
    }
    logger.info('Попытка запроса к API')
    try:
        response = requests.get(**request_param)
        if response.status_code != HTTPStatus.OK:
            raise Exception(
                f'Статус HTTP запроса не OK: {response.status_code}'
            )
    except requests.RequestException as error:
        raise Exception(f'Проблема с доступом к API: {error}')
    logger.info('Статус запроса к API: OK')
    response = response.json()
    return response


def check_response(response):
    """Проверка соответствия документации ответа API."""
    if isinstance(response, dict) is False:
        raise TypeError('ошибка - ответ API не dict')
    if (
        'homeworks' not in response.keys()
        or 'current_date' not in response.keys()
    ):
        raise AttributeError(
            'ошибка - в ответе API нет нужных ключей - HW/date'
        )
    if isinstance(response.get('homeworks'), list) is False:
        raise TypeError('ошибка - в ответе API по ключу homeworks не список')
    logger.info('ОК - структура ответа API соотв. документации')
    return True


def count_homeworks(response):
    """Определение кол-ва ДЗ в списке, полученном от API."""
    count_homeworks = len(response.get('homeworks'))
    return count_homeworks


def get_last_homework(response):
    """Получение инфо о последней домашней работе."""
    if len(response.get('homeworks')) == 0:
        logger.info('Ответ API - статус домашки пока не обновился')
    else:
        homework = response.get('homeworks')[0]
        return homework


def get_last_current_date(response):
    """Получение текущего времени из последнего запроса."""
    current_date = response.get('current_date')
    return current_date


def parse_status(homework):
    """Получение статуса ДЗ."""
    if (
        'homework_name' not in homework.keys()
        or 'status' not in homework.keys()
    ):
        raise AttributeError(
            'ошибка - в ответе API о ДЗ нет ключей - name/status'
        )
    logger.info('ОК - структура словаря ДЗ соотв. документации')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS.keys():
        raise AttributeError(
            'ошибка - в ответе API есть неизвестный статус ДЗ'
        )
    logger.info('ОК - Статус ДЗ от API соотв. документации')
    logger.debug(f'От API получен статус ДЗ - {homework_status}')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """1. Проверка доступности переменных окружения.
    2. Вывод в лог отсутствующих переменных.
    """
    return all((TELEGRAM_CHAT_ID, TELEGRAM_TOKEN, PRACTICUM_TOKEN))


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        logger.critical('Отсутствуют переменные окружения')
        sys.exit('Отсутсвуют токены')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    while True:
        try:
            response = get_api_answer(current_timestamp)
            check_response(response)
            if count_homeworks(response) > 0:
                current_timestamp = get_last_current_date(response)
                homework = get_last_homework(response)
                message = parse_status(homework)
                if LAST_MESSAGE_TEXT_DICT['last_text'] != message:
                    send_message(bot, message)
            else:
                logger.info('Ответ API - статус домашки пока не обновился')

        except Exception as error:
            message_err = f'Сбой в работе программы: {error}'
            logger.error(message_err)
            if LAST_MESSAGE_TEXT_DICT['last_text'] != message_err:
                send_message(bot, message_err)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    handler = StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    main()
