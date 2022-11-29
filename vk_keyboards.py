from vk_api.keyboard import VkKeyboard

kb_hello = VkKeyboard(one_time=True, inline=False)
kb_hello.add_button(label="Привет!", color='positive')

kb_begin = VkKeyboard(one_time=False, inline=True)
kb_begin.add_button(label="Искать пару", color='positive')
kb_begin.add_button(label="Изменить параметры", color="primary")
kb_begin.add_button(label="Пока", color='negative')

kb_params = VkKeyboard(one_time=False, inline=True)
kb_params.add_button(label="Искать пару", color='positive')
kb_params.add_line()
kb_params.add_button(label="Город", color="primary")
kb_params.add_button(label="Пол", color="primary")
kb_params.add_button(label="СП", color="primary")
kb_params.add_line()
kb_params.add_button(label="Мин. возраст", color="primary")
kb_params.add_button(label="Макс. возраст", color="primary")
kb_params.add_button(label="Пока", color='negative')

kb_search = VkKeyboard(one_time=False, inline=True)
kb_search.add_button(label="Следующий кандидат", color='positive')
kb_search.add_line()
kb_search.add_button(label="В избранное", color="primary")
kb_search.add_line()
kb_search.add_button(label="Изменить параметры", color="primary")
kb_search.add_line()
kb_search.add_button(label="Пока", color='negative')
