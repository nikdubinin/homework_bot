import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Union

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

from exceptions import ConnectionError, EndpointStatusError

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


def check_tokens() -> bool:
    """Проверка токенов."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщения."""
    logging.debug('Начинаем отправку сообщения.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as err:
        logging.error(f'Ошибка работы с Telegram: {err}', exc_info=True)
    else:
        logging.debug('Сообщение отправлено.')


def get_api_answer(timestamp: int) -> dict:
    """Получение ответа от Api."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except Exception as err:
        message = (f'При подключении к серверу произошла ошибка: {err}.'
                   f' Параметры запроса: {ENDPOINT} - {HEADERS} - {payload}')
        raise ConnectionError(message) from err
    if not response.status_code == HTTPStatus.OK:
        message = (f'Получен неверный ответ от сервера: {response.status_code}'
                   f'. Параметры запроса: {ENDPOINT} - {HEADERS} - {payload}.'
                   f' Текст ответа: {response.text}')
        raise EndpointStatusError(message)
    return response.json()


def check_response(response: Union[list, dict]) -> list:
    """Проверка ответа."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API вернул не словарь.')
    if 'homeworks' not in response:
        raise KeyError('В ответе отсутствует ключ "homeworks".')
    if 'current_date' not in response:
        raise KeyError('В ответе отсутствует ключ "current_date".')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ "homeworks" вернул не список.')
    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Парсинг статуса работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError('В ответе отсутствует имя работы.')
    elif not homework_status:
        raise KeyError('В ответе отсутствует статус работы.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус работы {homework_name}'
                       ' отличается от заданного.')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_unique_message(bot: telegram.Bot,
                        message: str,
                        sent_messages: list,
                        debug: str) -> str:
    """Проверка сообщения на уникальность перед отправкой в телеграмм."""
    if message not in sent_messages:
        send_message(bot, message)
        sent_messages.append(message)
        logging.debug(message)
    else:
        logging.debug(debug)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствуют токены для работы бота. Работа остановлена.'
        logging.critical(message)
        sys.exit(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    sent_messages = []
    prev_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                debug = 'Изменений в статусах проверки работы нет.'
                send_unique_message(bot, message, sent_messages, debug)
            else:
                message = 'Нет новых домашних работ.'
                send_unique_message(bot, message, sent_messages, message)
        except Exception as err:
            message = f'Сбой в работе программы: {err}'
            logging.error(message, exc_info=True)
            if message != prev_error:
                send_message(bot, message)
                prev_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        level=logging.DEBUG
    )
    main()
