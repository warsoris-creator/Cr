from aiogram.fsm.state import StatesGroup, State

class AddBot(StatesGroup):
    waiting_for_token = State()
    waiting_for_source_type = State()
    waiting_for_github_url = State()
    waiting_for_file = State()
