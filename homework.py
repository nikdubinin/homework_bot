import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Union

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import Unauthorized

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
    try:
        logging.debug('Начинаем отправку сообщения.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Unauthorized:  # Добавил конкретный из ошибок телеграм
        logging.critical('Ошибка авторизации, проверьте токены.')
        sys.exit(1)
    except Exception as err:  # Прочитал Built-in Exceptions,общий тут подходит
        logging.error(f'Сообщение не отправлено. Ошибка {err}.', exc_info=True)
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
        raise ConnectionError(message)
    if not response.status_code == HTTPStatus.OK:
        message = (f'Получен неверный ответ от сервера: {response.status_code}'
                   f'. Параметры запроса: {ENDPOINT} - {HEADERS} - {payload}.')
        raise EndpointStatusError(message)
    return response.json()


def check_response(response: Union[list, dict]) -> list:
    """Проверка ответа."""
    if not isinstance(response, dict):
        message = 'Ответ API вернул не словарь.'
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'В ответе отсутствует ключ "homeworks".'
        raise KeyError(message)
    if 'current_date' not in response:
        message = 'В ответе отсутствует ключ "current_date".'
        raise KeyError(message)
    if not isinstance(response['homeworks'], list):
        message = 'Ключ "homeworks" вернул не список.'
        raise TypeError(message)
    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Парсинг статуса работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        message = 'В ответе отсутствует имя работы.'
        raise KeyError(message)
    elif not homework_status:
        message = 'В ответе отсутствует статус работы.'
        raise KeyError(message)
    if homework_status not in HOMEWORK_VERDICTS:
        message = f'Статус работы {homework_name} отличается от заданного.'
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствуют токены для работы бота. Работа остановлена.'
        logging.critical(message)
        sys.exit(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                message = 'За запрошенный период домашних работ нет.'
                logging.debug(message)
        except Exception as err:
            message = f'Сбой в работе программы: {err.message}'
            send_message(bot, message)
            logging.error(message, exc_info=True)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        level=logging.DEBUG
    )
    main()
