import logging
import os
import requests
import telegram
import time


from dotenv import load_dotenv
from http import HTTPStatus
from typing import Union


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

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    filename='main.log',
    level=logging.DEBUG
)

logger = logging.getLogger(__name__)


def check_tokens() -> bool:
    """Проверка токенов."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as e:
        logger.error(f'Сообщение не отправлено. Ошибка {e}.')
    else:
        logger.debug('Сообщение отправлено.')


def get_api_answer(timestamp: int) -> dict:
    """Получение ответа от Api."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except Exception as e:
        message = f'При подключении к серверу произошла ошибка: {e}.'
        logger.error(message)
        raise ConnectionError(message)
    if response.status_code == HTTPStatus.OK:
        return response.json()
    else:
        message = 'Получен неожиданный ответ от'
        f' сервера: {response.status_code}.'
        logger.error(message)
        raise Exception(message)


def check_response(response: Union[list, dict]) -> list:
    """Проверка ответа."""
    if type(response) is not dict:
        message = 'Ответ API вернул не словарь.'
        logger.error(message)
        raise TypeError(message)
    try:
        homeworks = response['homeworks']
    except KeyError:
        message = 'В ответе отсутствует ключ "homeworks".'
        logger.error(message)
        raise KeyError(message)
    if type(homeworks) is not list:
        message = 'Ключ "homeworks" вернул не список.'
        logger.error(message)
        raise TypeError(message)
    return homeworks


def parse_status(homework: dict) -> str:
    """Парсинг статуса работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        message = 'Отсутствует имя работы.'
        logger.error(message)
        raise KeyError(message)
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS.keys():
        message = f'Не удалось получить статус работы {homework_name}.'
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    print('Проверка токенов...')
    if not check_tokens():
        message = 'Отсутствуют токены для работы бота.'
        logger.critical(message)
        raise Exception(message)
    print('Запуск бота...')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            print('Обращаемся к серверу...')
            response = get_api_answer(timestamp)
            if response:
                print('Успешно подклились к серверу...')
                timestamp = response.get('current_date', timestamp)
                homeworks = check_response(response)
                if homeworks:
                    print('Есть новые работы...')
                    for homework in homeworks:
                        print('Сообщение о статусе работы '
                              f'{homework["homework_name"]} отправлено...')
                        message = parse_status(homework)
                        send_message(bot, message)
                else:
                    message = 'Статус работ не изменился.'
                    print(message)
                    logger.debug(message)
        except Exception as e:
            message = f'Сбой в работе программы: {e}'
            send_message(bot, message)
            logger.error(message)
        finally:
            print('Перезапуск бота через 10 минут...')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
