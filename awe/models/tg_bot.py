from .mutable_sa_base_model import MutableSABaseModel

class TGBot(MutableSABaseModel):
    username: str
    token: str
    start_message: str

TGBotSAType = TGBot.to_sa_type()
