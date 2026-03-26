import logging



############ Logger Initialization ############
logger = logging.getLogger(__name__)

async def authenticate(username: str, password: str = None, pkey: str = None):
    """
    ########## User Authentication Handler ##########
    
    Async function to handle user authentication for SSH connections.
    
    Parameters:
        username (str): Username of the connecting client
        password (str, optional): Password provided by the client
        key (str, optional): Public key provided by the client
    
    Returns:
        bool: True if authentication is successful, False otherwise
    """
    logger.debug(f"Authenticating user: {username}, password: {password}, key: {pkey}")

    if pkey:
        # В будущем здесь будет запрос к БД: "SELECT pubkey FROM users WHERE..."
        # Допустим, мы получили строку из базы:
        #db_pubkey_string = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..." # Пример

        # Сейчас мы просто разрешаем любой ключ, но логируем его данные
        logger.debug(f"User {username} trying key: {pkey.get_algorithm()} {pkey.get_fingerprint()}")

        # ЛОГИКА СРАВНЕНИЯ (для будущего):
        # target_key = asyncssh.import_public_key(db_pubkey_string)
        # if pkey == target_key:
        #     return {"status": True}

        # Пока разрешаем всё:
        return {"status": True}



    # Temporary implementation: allow any login/password combination
    status = True
    actual_username = username[:-1]

    return {"status": status, "actual_username": actual_username}
