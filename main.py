import requests
import vk_api

from datetime import datetime
from vk_api.longpoll import VkLongPoll, VkEventType
from random import randrange

import vk_dicts
import vk_keyboards
import db

try:
    with open('group_token.txt.txt', mode='r') as token_file:
        group_token = token_file.read().strip()
    with open('user_token.txt', mode='r') as token_file:
        user_token = token_file.read().strip()
except FileNotFoundError:
    group_token = input('group_token: ')
    user_token = input('user_token: ')


def write_msg(user_id, message, keyboard: vk_keyboards.VkKeyboard = None, attachment: str = None):
    params = {'user_id': user_id,
              'message': message,
              'random_id': randrange(10 ** 7)}
    if keyboard:
        params['keyboard'] = keyboard
    if attachment:
        params['attachment'] = attachment
    vk_bot.method('messages.send', params)


def get_user_info(id, fields: str):
    user = vk_bot.method('users.get', {'user_ids': id, 'fields': fields})[0]
    return user


def get_search_params(user_id):
    raw_params = get_user_info(user_id, 'relation, sex, city, bdate')
    params = {}
    params["user_id"] = raw_params["id"]
    params["relation"] = 6
    params["sex"] = 3 - raw_params["sex"]
    params["city"] = raw_params["city"]["title"]
    if int(raw_params["bdate"].split(".")[-1]) > 1900:
        params['my_age'] = datetime.today().year - int(raw_params["bdate"].split(".")[-1])
    else:
        params['my_age'] = 30
    params["min_age"] = params['my_age'] - 5
    params["max_age"] = params['my_age'] + 5
    return params


def print_search_params(search_params):
    message = f"Текущие параметры поиска:\n"
    message += f'Город: {search_params["city"]}\n'
    message += f'Пол: {vk_dicts.sex_spr[search_params["sex"]]}\n'
    message += f'СП: {vk_dicts.relation_spr[search_params["relation"]]}\n'
    if search_params['my_age']:
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
            'hometown': search_params["city"],
            'fields': 'last_name, first_name, about'
        }
        candidates = requests.get(f'{self.base_url}/method/users.search',
                                  {**params, **self.general_params()}).json()["response"]["items"]
        for candidate in candidates:
            candidate["checked"] = 0
            candidate["favorite"] = 0
            candidate["black_list"] = 0

        return candidates

    def print_candidate(self, candidate):
        temp_candidate = get_user_info(candidate["id"], 'bdate, about, interests, sex, relation')
        if "bdate" in temp_candidate.keys():
            candidate["bdate"] = temp_candidate["bdate"]
        if "about" in temp_candidate.keys():
            candidate["about"] = temp_candidate["about"]
        if "interests" in temp_candidate.keys():
            candidate["interests"] = temp_candidate["interests"]
        attachment = ''
        for photo in candidate["photos"]:
            attachment += f"photo{photo['owner_id']}_{photo['id']},"
        message = f'{candidate["first_name"]} {candidate["last_name"]}, '
        message += f'город {search_params["city"]}, '
        message += f'{datetime.today().year - int(candidate["bdate"].split(".")[-1])} л. \n'
        message += f' пол: {vk_dicts.sex_spr[search_params["sex"]]}. \n'
        message += f' СП: {vk_dicts.relation_spr[search_params["relation"]]}. \n'
        if "interests" in candidate.keys():
            message += f'Интересы: {candidate["interests"]}\n'
        if "about" in candidate.keys():
            message += f'О себе: {candidate["about"]}\n'
        message += f"CСылка на страницу https://vk.com/id{candidate['id']}"

        write_msg(event.user_id, message=message,
                  keyboard=vk_keyboards.kb_search.get_keyboard(),
                  attachment=attachment)


vk_bot = vk_api.VkApi(token=group_token)
longpoll = VkLongPoll(vk_bot)
vk_client = VKApiClient(user_token=user_token)
search_params = None
params_changed = 1

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_name = get_user_info(event.user_id, '')['first_name']
        if not search_params:
            search_params = get_search_params(event.user_id)
            search_params_id = db.store_search_params(search_params)

        request = event.text
        if request.lower() == "начать":
            message = f"Привет, {user_name}, я бот, я тебе помогу найти пару по твоим данным"
            write_msg(event.user_id, message)
            message = print_search_params(search_params)
            write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_begin.get_keyboard())
        elif request.lower() == "искать пару":
            message = f"Ищем...\n"
            message += print_search_params(search_params)
            message += "Ищу пару..."
            write_msg(event.user_id, message=message)
            if params_changed:
                params_changed = 0
                candidates = vk_client.get_candidates_list(search_params)
                message = f"Найдено {len(candidates)} кандидатов"
            write_msg(event.user_id, message=message)
            exit_flag = 0
            for candidate in candidates:
                db.record_candidate(search_params_id, candidate["id"])
                if exit_flag > 0:
                    break
                photos = vk_client.get_candidate_photos(candidate["id"])
                if not photos:
                    candidate["black_list"] = 1
                    db.record_candidate(search_params_id, candidate["id"], is_blacklist=True)
                else:
                    candidate["photos"] = photos
                if not candidate["black_list"] and not candidate["checked"]:
                    vk_client.print_candidate(candidate)
                    candidate["checked"] = 1
                    db.record_candidate(search_params_id, candidate["id"], is_checked=True)
                    for event in longpoll.listen():
                        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                            request = event.text
                            if request.lower() == "следующий кандидат":
                                break
                            elif request.lower() == "в избранное":
                                candidate["favorite"] = 1
                                db.record_candidate(search_params_id, candidate["id"], is_favorite=True)
                                write_msg(event.user_id, message=f'id {candidate["id"]} добавлен в избранное',
                                          keyboard=vk_keyboards.kb_search.get_empty_keyboard())
                                break
                            elif request.lower() == "изменить параметры":
                                message = f"Возвращаемся к выбору параметров?\n"
                                exit_flag = 1
                                write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_begin.get_keyboard())
                                break
                            elif request.lower() == "пока":
                                exit_flag = 2
                                write_msg(event.user_id, "Пока((", keyboard=vk_keyboards.kb_hello.get_keyboard())
                                break
                            else:
                                write_msg(event.user_id, f"Непонятно((", keyboard=vk_keyboards.kb_begin.get_keyboard())
                                break

        elif request.lower() == "изменить параметры":
            message = f"ОК! "
            message += print_search_params(search_params)
            message += "Что хочешь поменять?\n"
            write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    request = event.text
                    kb_back = vk_keyboards.VkKeyboard(one_time=False, inline=True)
                    kb_back.add_button(label="Назад", color="primary")
                    if request.lower() == "город":
                        message = f"Введи новый город:\n"
                        write_msg(event.user_id, message=message, keyboard=kb_back.get_keyboard())
                        for event in longpoll.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                request: str = event.text
                                if request.lower() != "назад":
                                    search_params["city"] = request.capitalize()
                                    params_changed = 1
                                    search_params_id = db.store_search_params(search_params)
                                    message = f"Принято! Новый город {search_params['city']}\n"
                                else:
                                    message = f"Оставляем г. {search_params['city']}!\n"
                                message += print_search_params(search_params)
                                write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_begin.get_keyboard())
                                break

                    elif request.lower() == "мин. возраст":
                        message = f"Какой минимальный возраст подойдет:\n"
                        write_msg(event.user_id, message=message, keyboard=kb_back.get_keyboard())
                        for event in longpoll.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                request: str = event.text
                                if request.isnumeric():
                                    search_params['min_age'] = int(request)
                                    params_changed = 1
                                    message = f"Принято! возрастной диапазон начинается с {search_params['min_age']}\n"
                                    if search_params['min_age'] > search_params['max_age']:
                                        search_params['max_age'] = search_params['min_age']
                                        message = f"Нижняя граница больше верхней! Верхнуюю тоже ставим = {search_params['max_age']}\n"
                                elif request.lower() == "назад":
                                    message = f"Оставляем {search_params['min_age']}!\n"
                                else:
                                    message = f"Непонятно. Оставляем {search_params['min_age']}!\n"
                                message += print_search_params(search_params)
                                write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_begin.get_keyboard())
                                break

                    elif request.lower() == "макс. возраст":
                        message = f"Какой максимальный возраст подойдет?\n"
                        write_msg(event.user_id, message=message, keyboard=kb_back.get_keyboard())
                        for event in longpoll.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                request: str = event.text
                                if request.isnumeric():
                                    search_params['max_age'] = int(request)
                                    params_changed = 1
                                    search_params_id = db.store_search_params(search_params)
                                    message = f"Принято! возрастной диапазон заканчивается на {search_params['max_age']}\n"
                                    if search_params['min_age'] > search_params['max_age']:
                                        search_params['min_age'] = search_params['max_age']
                                        message = f"Верхняя граница меньше нижней! Нижнюю тоже ставим = {search_params['min_age']}\n"
                                elif request.lower() == "назад":
                                    message = f"Оставляем {search_params['min_age']}!\n"
                                else:
                                    message = f"Непонятно. Оставляем {search_params['min_age']}!\n"
                                message += print_search_params(search_params)
                                write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_begin.get_keyboard())
                                break

                    elif request.lower() == "сп":
                        message = "В каких семейных положениях осуществлять поиск?:\n"
                        message += '1: не женат/не замужем\n'
                        message += '2: есть друг/есть подруга\n'
                        message += '3: помолвлен/помолвлена\n'
                        message += '4: женат/замужем\n'
                        message += '5: всё сложно\n'
                        message += '6: в активном поиске\n'
                        message += '7: влюблён/влюблена\n'
                        message += '8: в гражданском браке\n'
                        write_msg(event.user_id, message=message, keyboard=kb_back.get_keyboard())
                        for event in longpoll.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                request: str = event.text
                                if request.isnumeric() and 0 < int(request) < 9:
                                    search_params['relation'] = int(request)
                                    params_changed = 1
                                    search_params_id = db.store_search_params(search_params)
                                    message = f"Принято! Ищем людей в статусе: {vk_dicts.relation_spr[search_params['relation']]}\n"

                                elif request.lower() == "назад":
                                    message = f"Оставляем {search_params['relation']}: {vk_dicts.relation_spr[search_params['relation']]}!\n"
                                else:
                                    message = f"Непонятно. Оставляем {search_params['relation']}: {vk_dicts.relation_spr[search_params['relation']]}!\n"
                                message += print_search_params(search_params)
                                write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_begin.get_keyboard())
                                break

                    elif request.lower() == "пол":
                        search_params["sex"] = 3 - search_params["sex"]
                        params_changed = 1
                        search_params_id = db.store_search_params(search_params)
                        message = f"Пол изменен на {vk_dicts.sex_spr[search_params['sex']]}!\n"
                        message += print_search_params(search_params)
                        write_msg(event.user_id, message=message, keyboard=vk_keyboards.kb_params.get_keyboard())

                    elif request.lower() == "пока":
                        write_msg(event.user_id, "Пока((", keyboard=vk_keyboards.kb_hello.get_keyboard())

                    else:
                        write_msg(event.user_id, f"Непонятно((", keyboard=vk_keyboards.kb_begin.get_keyboard())
                        break
                    break

        elif request.lower().find("привет") + 1 > 0:
            write_msg(event.user_id, f"О, приветик, {user_name}!", keyboard=vk_keyboards.kb_begin.get_keyboard())

        elif request.lower() == "пока":
            write_msg(event.user_id, "Пока((", keyboard=vk_keyboards.kb_hello.get_keyboard())
        else:
            write_msg(event.user_id, f"Непонятно((", keyboard=vk_keyboards.kb_begin.get_keyboard())
