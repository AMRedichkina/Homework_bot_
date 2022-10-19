import os
import sys
import logging
import requests
import time
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 60 * 10  # 60 сек * 10 мин = 600 сек
url = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN }'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def send_message(bot, message):
    """Отправка сообщений в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID,
                         text=message)
        logger.info('Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception:
        logger.error('Ошибка отправки сообщения в телеграм')


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту."""
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        r = requests.get(
            url, headers=headers, params=params)
    except Exception as error:
        logger.error(f'Ошибка запроса к эндпоинту {error}')
        raise Exception(f'Ошибка запроса к эндпоинту {error}')
    else:
        if r.status_code != HTTPStatus.OK:
            logger.error(f'Недоступность эндпоинта {r.statuse.code}')
            raise Exception(f'Недоступность эндпоинта {r.statuse.code}')
        response = r.json()
        return(response)


def check_response(response):
    """Проверяем данные в response."""
    if response['homeworks'] is None:
        logger.error('Ошибка ключа homeworks или response'
                     'имеет неправильное значение.')
        raise Exception('Ошибка ключа homeworks или response'
                        'имеет неправильное значение.')
    if response['homeworks'] == []:
        return {}
    return response['homeworks'][0]


def parse_status(homework):
    """Проверка изменения статуса."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        code_api_msg = (f'недокументированный статус домашней работы,'
                        f'обнаруженный в ответе API: {homework_status}')
        logger.error(code_api_msg)
        raise Exception(code_api_msg)
    verdict = HOMEWORK_VERDICTS[homework_status]
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return message


def check_tokens():
    """Проверяем наличие переменных окружения."""
    return(all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)))


def main():
    """Основная логика работы."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        logger.critical('Нет одной или нескольких переменных окружения')
        raise Exception('Нет одной или нескольких переменных окружения')
    current_timestamp = int(time.time()) - RETRY_TIME
    tmp_status = None
    previous_error = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            tmp_status = homework
            if homework and tmp_status != homework['status']:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework['status']
            logger.debug(
                'Отсутствие в ответе новых статусов')
            continue
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != str(f'Сбой в работе программы: {previous_error}'):
                send_message(bot, message)
                previous_error = error
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
