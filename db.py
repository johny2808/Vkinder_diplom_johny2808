import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy_utils import drop_database, database_exists, create_database
from settings import dsn, encoding, drop_db

Base = declarative_base()


class UserSearches(Base):
    __tablename__ = 'User_searches'
    id = sq.Column(sq.Integer, primary_key=True, autoincrement=True)
    user_vk_id = sq.Column(sq.Integer)
    param_rel = sq.Column(sq.Integer)
    param_sex = sq.Column(sq.Integer)
    param_min_age = sq.Column(sq.Integer)
    param_max_age = sq.Column(sq.Integer)
    param_city = sq.Column(sq.String)
    is_last_search = sq.Column(sq.Boolean)     # добавил поле для хранения информации о последнем поиске


class Candidates(Base):
    __tablename__ = 'Candidates'
    id = sq.Column(sq.Integer, primary_key=True, autoincrement=True)
    search_id = sq.Column(sq.Integer, sq.ForeignKey("User_searches.id", ondelete='CASCADE'), nullable=False)
    candidate_vk_id = sq.Column(sq.Integer, nullable=False)
    is_checked = sq.Column(sq.Boolean)
    is_blacklist = sq.Column(sq.Boolean)
    is_favorite = sq.Column(sq.Boolean)


def init():
    if drop_db:
        drop_database(engine.url)
        print('База очищена')
    if not database_exists(engine.url):
        create_database(engine.url)
        Base.metadata.create_all(engine)
        print('База данных создана...')


# Функция ищет сохраненные параметры подбора или создает новую запись в таблице, если не нашла, и выдает ее ID
# Поскольку она вызывается после каждой итерации главного цикла, то текущие параметры поиска всегда последние
# т.е. is_last_search = True

def store_search_params(param: dict):  # user_vk_id, rel, sex, min, max, city
    res = session.execute(
        f"""SELECT id from "User_searches" 
            where user_vk_id = {param["user_id"]} and param_rel = {param["relation"]} 
            and param_sex = {param["sex"]} and param_min_age = {param["min_age"]} 
            and param_max_age = {param["max_age"]} 
            and param_city = '{param["city"]}';""").fetchall()
    #
    if res:
        session.execute(f"""UPDATE "User_searches" set is_last_search = True where user_vk_id = {param["user_id"]}
                            and id = {res[0][0]};""")
        session.execute(f"""UPDATE "User_searches" set is_last_search = False where user_vk_id = {param["user_id"]}
                            and id <> {res[0][0]};""")
        return res[0][0]
    if not res:
        session.execute(f"""INSERT INTO "User_searches"
                        (user_vk_id, param_rel, param_sex, param_min_age, param_max_age, param_city)
                        VALUES({param["user_id"]}, {param["relation"]}, 
                        {param["sex"]}, {param["min_age"]}, {param["max_age"]}, '{param["city"]}');""")
        res = store_search_params(param)
        return res


# Загружаем последние параметры поиска
def get_last_search_params(user_id):  # user_vk_id, rel, sex, min, max, city
    res = session.execute(
        f"""SELECT * from "User_searches" 
            where user_vk_id = {user_id} and is_last_search = True;""").fetchall()
    print(res)
    if res:
        params = {}
        params["user_id"] = res[0][1]
        params["relation"] = res[0][2]
        params["sex"] = res[0][3]
        params["min_age"] = res[0][4]
        params["max_age"] = res[0][5]
        params["city"] = res[0][6]
        return params
    else:
        return False


# Дропаем всех кандидатов для нового поиска по текущим критериям
def drop_search_results(search_id):
    session.execute(
        f"""Delete from "Candidates" 
                   where search_id = {search_id};""")


# Процедура записи в базу новых кандидатов и изменения свойств старых кандидатов

def record_candidate(search_id, candidate_vk_id, **kwargs):
    res = session.execute(
        f"""SELECT * from "Candidates" 
                where search_id = {search_id} and candidate_vk_id = {candidate_vk_id};""").fetchone()
    if not res:
        session.execute(f"""INSERT INTO "Candidates"
                            (search_id, candidate_vk_id)
                            VALUES({search_id}, {candidate_vk_id});""")
    if kwargs:
        for key, value in kwargs.items():
            session.execute(f"""UPDATE "Candidates" set {key} = {value}
        where search_id = {search_id} and candidate_vk_id = {candidate_vk_id};""")


def read_work_list(search_id):
    res = session.execute(
        f"""SELECT candidate_vk_id from "Candidates" 
                where search_id = {search_id} and not (is_checked is true or is_blacklist is true);""").fetchall()

    work_list = []
    for person in res:
        work_list.append(person[0])
    return work_list


def read_blacklist(search_id):
    res = session.execute(
        f"""SELECT candidate_vk_id from "Candidates" 
                where search_id = {search_id} and is_blacklist is true;""").fetchall()

    blacklist = []
    for person in res:
        blacklist.append(person[0])
    return blacklist


def read_favorites(search_id):
    res = session.execute(
        f"""SELECT candidate_vk_id from "Candidates" 
                where search_id = {search_id} and is_favorite is true;""").fetchall()

    favorites = []
    for person in res:
        favorites.append(person[0])
    return favorites


engine = sq.create_engine(dsn, encoding=encoding)
Session = sessionmaker(bind=engine)
session = Session()
session.autocommit = True

init()
