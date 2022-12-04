import requests
import vk_api

from datetime import datetime
from vk_api.longpoll import VkLongPoll, VkEventType
from random import randrange

import vk_dicts
import vk_keyboards
import db

try:
    with open('group_token.txt', mode='r') as token_file:
        group_token = token_file.read().strip()
    with open('user_token.txt', mode='r') as token_file:
        user_token = token_file.read().strip()
except FileNotFoundError:
    group_token = input('group_token: ')
    user_token = input('user_token: ')


def write_msg(user_id, message, keyboard: vk_keyboards.VkKeyboard = None, attachment: str = None):
    params = {'user_id': user_id,
              'message': message,
              'random_id': randrange(10 ** 7),
              }
    if keyboard:
        params['keyboard'] = keyboard
    if attachment:
        params['attachment'] = attachment
    vk_bot.method('messages.send', params)


def get_person_info(vk_id, fields: str):  # получает нужную инфу из профиля ВК по ID
    user = vk_bot.method('users.get', {'user_ids': vk_id, 'fields': fields})[0]
    return user


def get_search_params(user_id):  # Процедура генерит первоначальные параметры поиска, исходя из данных о пользователе
    raw_params: dict = get_person_info(user_id, 'sex, city, bdate')
    params = {}
    params["user_id"] = raw_params["id"]  # возвращается всегда
    params["relation"] = 6  # по умолчанию используем значение "в активном поиске"
    params["sex"] = 3 - raw_params["sex"]  # Пол в ВК - обязательное поле, тоже возвращается всегда
    if "city" not in raw_params.keys():  # Если у тебя не заполнен город, подставляем Москву по умолчанию
        params["city"] = "Москва"
    else:
        params["city"] = raw_params["city"]["title"]
    if "bdate" not in raw_params.keys():  # Если скрыт полностью день рождения
        my_age = 30
    elif int(raw_params["bdate"].split(".")[-1]) < 1900:  # Или скрыт только год рождения, ставим 30 по умолчанию
        my_age = 30
    else:
        my_age = datetime.today().year - int(raw_params["bdate"].split(".")[-1])
    params["min_age"] = my_age - 5
    params["max_age"] = my_age + 5
    return params


def print_search_params(search_params):
    message = f"Текущие параметры поиска:\n"
    message += f'Город: {search_params["city"]}\n'
    message += f'Пол: {vk_dicts.sex_spr[search_params["sex"]]}\n'
    message += f'СП: {vk_dicts.relation_spr[search_params["relation"]]}\n'
    message += f'Возраст:  от {search_params["min_age"]} до {search_params["max_age"]} \n'
    return message


class VKApiClient:
    def __init__(self, user_token: str, api_version: str = "5.131", base_url: str = "https://api.vk.com"):
        self.base_url = base_url
        self.user_token = user_token
        self.api_version = api_version

    def general_params(self):
        return {"access_token": self.user_token,
                "v": self.api_version}

    def get_candidate_photos(self, candidate_id):
        params = {
            'owner_id': candidate_id,
            'album_id': 'profile',
            'extended': '1',
            'photo_sizes': '1',
            'rev': '1'
        }
        response: dict = requests.get(f'{self.base_url}/method/photos.get',
                                      {**params, **self.general_params()}).json()
        if 'error' in response.keys():
            return False
        else:
            photos = []
            for photo in response['response']['items']:
                photo["popularity"] = photo["likes"]["count"] + photo["comments"]["count"]

            candidate_photos = sorted(response['response']['items'],
                                      key=lambda photo: photo["popularity"], reverse=True)
            count = 3
            if len(candidate_photos) < 3:
                count = len(candidate_photos)
            for i in range(count):
                photos.append(candidate_photos[i])
            return photos

    def get_candidates_list(self, search_params):
        params = {
            'sort': 0,
            'count': 1000,
            'status': search_params["relation"],
            'sex': search_params["sex"],
            'age_from': search_params["min_age"],
            'age_to': search_params["max_age"],
            'is_closed': False,
            'has_photo': 1,
            'hometown': search_params["city"]
        }

        candidates = requests.get(f'{self.base_url}/method/users.search',
                                  {**params, **self.general_params()}).json()["response"]["items"]

        return candidates

    def print_candidate(self, candidate_id, is_favorites_list=False):
        global counter, work_list, search_params_id
        candidate = get_person_info(candidate_id, 'bdate, about, interests, sex, relation')
        candidate["photos"] = vk_client.get_candidate_photos(candidate_id)
        attachment = ''
        # Если выводим список избранных, то не показываем счетчик просмотренных анкет
        if not is_favorites_list:
            message = f"Кандидат {counter} из {len(work_list)}:\n"
        else:
            message = ''
        message += f'{candidate["first_name"]} {candidate["last_name"]}'
        if 'bdate' in candidate.keys():
            message += f', {datetime.today().year - int(candidate["bdate"].split(".")[-1])} л.'
        message += '\n'

        if not candidate["photos"]:
            message += f"Фото недоступно, заносим в черный список!\n"
            db.record_candidate(search_params_id, candidate_id, is_blacklist=True, is_favorite=False)
        else:

            for photo in candidate["photos"]:
                attachment += f"photo{photo['owner_id']}_{photo['id']},"

            if "city" in candidate.keys():
                message += f'город {search_params["city"]}, \n'
            if "sex" in candidate.keys():
                message += f' пол: {vk_dicts.sex_spr[search_params["sex"]]}, '
            if "relation" in candidate.keys():
                message += f' СП: {vk_dicts.relation_spr[search_params["relation"]]}.'
            message += '\n'
            if "interests" in candidate.keys() and len(candidate["interests"]) > 0:
                message += f'Интересы: {candidate["interests"][:250:]}\n'
            if "about" in candidate.keys() and len(candidate["about"]) > 0:
                message += f'О себе: {candidate["about"][:250:]}\n'
        message += f"Ccылка на страницу https://vk.com/id{candidate['id']}"

        write_msg(event.user_id, message=message,
                  keyboard=vk_keyboards.kb_search.get_keyboard(),
                  attachment=attachment)
        db.record_candidate(search_params_id, candidate_id, is_checked=True)


def menu_item_begin():
    message = f"Привет, {user_name}, я бот, я тебе помогу найти пару по твоим данным"
    write_msg(event.user_id, message)
    message = print_search_params(search_params)
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_main.get_keyboard())


def menu_item_hello():
    write_msg(event.user_id, f"О, приветик, {user_name}!", keyboard=vk_keyboards.kb_main.get_keyboard())


def menu_item_goodbye():
    write_msg(event.user_id, "Пока((", keyboard=vk_keyboards.kb_hello.get_keyboard())


def menu_item_change_params():
    message = f"ОК! "
    message += print_search_params(search_params)
    message += "Что хочешь поменять?\n"
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())


def menu_item_change_params_city():
    global event, search_params
    message = f"Введи новый город:\n"
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_back.get_keyboard())
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            request: str = event.text
            if request.lower() != "назад":
                search_params["city"] = request.capitalize()
                message = f"Принято! Новый город {search_params['city']}\n"
            else:
                message = f"Оставляем г. {search_params['city']}!\n"
            message += print_search_params(search_params)
            write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())
            break


def menu_item_change_params_min_age():
    global event, search_params
    message = f"Какой минимальный возраст подойдет? \n"
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_back.get_keyboard())
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            request: str = event.text
            if request.lower() != "назад":
                if request.isnumeric():
                    search_params['min_age'] = int(request)
                    message = f"Принято! возрастной диапазон начинается с {search_params['min_age']}\n"
                    if search_params['min_age'] > search_params['max_age']:
                        search_params['max_age'] = search_params['min_age']
                        message = f"Нижняя граница больше верхней! Верхнюю тоже ставим = {search_params['max_age']}\n"
                else:
                    message = f"Непонятно. Оставляем {search_params['min_age']}!\n"
            else:
                message = f"Оставляем {search_params['min_age']}!\n"
            message += print_search_params(search_params)
            write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())
            break


def menu_item_change_params_max_age():
    global event, search_params
    message = f"Какой максимальный возраст подойдет? \n"
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_back.get_keyboard())
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            request: str = event.text
            if request.lower() != "назад":
                if request.isnumeric():
                    search_params['max_age'] = int(request)
                    message = f"Принято! возрастной диапазон заканчивается на {search_params['max_age']}\n"
                    if search_params['min_age'] > search_params['max_age']:
                        search_params['min_age'] = search_params['max_age']
                        message = f"Верхняя граница меньше нижней! Нижнюю тоже ставим = {search_params['min_age']}\n"
                else:
                    message = f"Непонятно. Оставляем {search_params['max_age']}!\n"
            else:
                message = f"Оставляем {search_params['max_age']}!\n"
            message += print_search_params(search_params)
            write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())
            break


def menu_item_change_params_relation():
    global event, search_params
    message = "В каких семейных положениях осуществлять поиск?:\n"
    message += '1: не женат/не замужем\n'
    message += '2: есть друг/есть подруга\n'
    message += '3: помолвлен/помолвлена\n'
    message += '4: женат/замужем\n'
    message += '5: всё сложно\n'
    message += '6: в активном поиске\n'
    message += '7: влюблён/влюблена\n'
    message += '8: в гражданском браке\n'
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_back.get_keyboard())
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            request: str = event.text
            if request.lower() != "назад":
                if request.isnumeric() and 0 < int(request) < 9:
                    search_params['relation'] = int(request)
                    message = f"Принято! Ищем людей в статусе: " \
                              f"{vk_dicts.relation_spr[search_params['relation']]}\n"
                else:
                    message = f"Непонятно. Оставляем {search_params['relation']}:" \
                              f" {vk_dicts.relation_spr[search_params['relation']]}!\n"
            else:
                message = f"Оставляем {search_params['relation']}: " \
                          f"{vk_dicts.relation_spr[search_params['relation']]}!\n"
            message += print_search_params(search_params)
            write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_main.get_keyboard())
            break


def menu_item_change_params_sex():
    global event, search_params
    search_params["sex"] = 3 - search_params["sex"]
    message = f"Пол изменен на {vk_dicts.sex_spr[search_params['sex']]}!\n"
    message += print_search_params(search_params)
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())


def menu_item_search_candidates():
    global event, candidates_from_search, work_list, counter
    message = print_search_params(search_params)
    message += "Ищу подходящую пару..."
    write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_search.get_keyboard())

    # Дергаем список подходящих людей с полями из ВК
    candidates_from_search = vk_client.get_candidates_list(search_params)
    if len(candidates_from_search) == 0:
        message = "По данным параметрам нет ни одного кандидата((\n"
        message += "Попробуй изменить параметры поиска"
        write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_search.get_keyboard())
    else:
        number_of_candidates = len(candidates_from_search)
        message = f"Найдено {number_of_candidates} чел.\n"
        message += "Составляю список..."

        write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_search.get_keyboard())

        # Пишем весь список в базу. Если человек уже в базе есть,
        # его атрибуты checked, favorite и blacklist при этом не затираем
        for candidate in candidates_from_search:
            db.record_candidate(search_params_id, candidate["id"])

        # читаем из базы список непросмотренных и не из черного списка
        work_list = db.read_work_list(search_params_id)
        message = f"Остались не просмотренными: {len(work_list)} чел.\n"
        message += f"В избранном: {len(db.read_favorites(search_params_id))} чел. "
        message += f"В черном списке: {len(db.read_blacklist(search_params_id))} чел.\n"
        write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_search.get_keyboard())
        if len(work_list) > 0:
            vk_client.print_candidate(work_list[counter - 1])
        else:
            menu_item_search_candidates_next()


def menu_item_search_candidates_next():
    global counter, work_list, event
    if counter <= len(work_list):
        vk_client.print_candidate(work_list[counter - 1])
    else:
        message = "Кандидаты кончились, попробуй изменить параметры"
        write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_search_end_of_list.get_keyboard())


def menu_item_search_candidates_new_rewiew():
    db.drop_search_results(search_params_id)
    menu_item_search_candidates()


def menu_item_search_candidates_add_to_blacklist():
    global work_list, counter, event
    message = f"ID: {work_list[counter - 1]} добавлен в черный список!"
    write_msg(event.user_id, message=message)
    db.record_candidate(search_params_id, work_list[counter - 1], is_blacklist=True, is_favorite=False)


def menu_item_search_candidates_add_to_favorites():
    global work_list, counter, event
    message = f"ID: {work_list[counter - 1]} добавлен в избранное!"
    write_msg(event.user_id, message=message)
    db.record_candidate(search_params_id, work_list[counter - 1], is_favorite=True, is_blacklist=False)


def menu_item_search_candidates_favorites_list():
    favorites = db.read_favorites(search_params_id)
    if len(favorites) == 0:
        message = f"В избранном пусто!\n\n"
        write_msg(event.user_id, message=message)
    else:
        print(favorites)
        message = f"Избранные кандидаты:\n\n"
        write_msg(event.user_id, message=message)
        for id in favorites:
            vk_client.print_candidate(id, is_favorites_list=True)
    write_msg(event.user_id, message="конец списка", keyboard=vk_keyboards.kb_back.get_keyboard())


def menu_item_search_candidates_blacklist():
    black_list = db.read_blacklist(search_params_id)
    if len(black_list) == 0:
        message = f"Черный список пуст!\n\n"
    else:
        print(black_list)
        message = f"Черный список:\n"
        write_msg(event.user_id, message=message)
        message = f"Загружаю...\n\n"
        write_msg(event.user_id, message=message)
        for id in black_list:
            person = get_person_info(id, '')
            message = f'{person["first_name"]} {person["last_name"]}\n https://vk.com/id{id}\n\n'
    write_msg(event.user_id, message=message[:4000:], keyboard=vk_keyboards.kb_back.get_keyboard())


vk_bot = vk_api.VkApi(token=group_token)
longpoll = VkLongPoll(vk_bot)
vk_client = VKApiClient(user_token=user_token)
where = "nowhere"  # Переменная хранит текущую позицию в меню команд бота
counter = 0
candidates_from_search = 0
work_list = []

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_name = get_person_info(event.user_id, '')['first_name']
        # Пробуем загрузить последние параметры поиска
        search_params = db.get_last_search_params(event.user_id)
        # Если пользователь новый - генерим, исходя из его данных
        if not search_params:
            search_params = get_search_params(event.user_id)

        # принимаем сообщение пользователя и реагируем
        request = event.text

        if request.lower() == "начать" and where == "nowhere":
            where = "main"
            menu_item_begin()

        elif request.lower().find("привет") + 1 > 0 and where == "nowhere":
            where = "main"
            menu_item_hello()

        elif request.lower() == "пока":
            where = "nowhere"
            menu_item_goodbye()

        # блок настройки критериев поиска
        elif request.lower() == "изменить параметры":
            where = 'in_params'
            menu_item_change_params()

        elif request.lower() == "город" and where == 'in_params':
            menu_item_change_params_city()

        elif request.lower() == "мин. возраст" and where == 'in_params':
            menu_item_change_params_min_age()

        elif request.lower() == "макс. возраст" and where == 'in_params':
            menu_item_change_params_max_age()

        elif request.lower() == "сп" and where == 'in_params':
            menu_item_change_params_relation()

        elif request.lower() == "пол" and where == 'in_params':
            menu_item_change_params_sex()

        # блок поиска
        elif request.lower() == "искать пару":
            counter = 1
            where = "in_search"
            menu_item_search_candidates()

        elif request.lower() == "следующий кандидат" and where == "in_search":
            counter += 1
            menu_item_search_candidates_next()
            # Если добрались до конца списка, бот покажет кнопку, но можно и вручную написать
        elif request.lower() == "начать сначала" and where == "in_search":
            counter = 1
            menu_item_search_candidates_new_rewiew()

        elif request.lower() == "в черный список" and where == "in_search":
            menu_item_search_candidates_add_to_blacklist()
            counter += 1
            menu_item_search_candidates_next()

        elif request.lower() == "в избранное" and where == "in_search":
            menu_item_search_candidates_add_to_favorites()
            counter += 1
            menu_item_search_candidates_next()

        elif request.lower() == "смотреть избранных" and where == "in_search":
            where = "in_favorites"
            menu_item_search_candidates_favorites_list()

        elif request.lower() == "смотреть черный список" and where == "in_search":
            where = "in_blacklist"
            menu_item_search_candidates_blacklist()

        elif request.lower() == "назад" and (where == "in_blacklist" or where == "in_favorites"):
            where = "in_search"
            counter = 1
            menu_item_search_candidates()

        else:
            write_msg(event.user_id, f"Непонятно((", keyboard=vk_keyboards.kb_main.get_keyboard())

        # В конце цикла проверяем, что параметры не изменились, т. е. ID поиска остался прежним
        search_params_id = db.store_search_params(search_params)
