from aiogram.fsm.state import State, StatesGroup

class DeployStates(StatesGroup):
    waiting_for_app_name = State()
    waiting_for_repo_url = State()
    waiting_for_config_vars = State()
    confirm_deploy = State()

class BillingStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment_proof = State()

class ConfigVarStates(StatesGroup):
    waiting_for_var_input = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast_msg = State()
    waiting_for_user_id_credit = State()
    waiting_for_credit_amount = State()
    waiting_for_price_update = State()
