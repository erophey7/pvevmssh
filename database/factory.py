from typing import Type
from .connection import DatabaseConnection
from .sqlite import SQLiteConnection
from .mariadb import MariaDBConnection

class DatabaseFactory:
    """Фабрика для создания подключений к БД."""
    
    _registry = {
        'sqlite': SQLiteConnection,
        'mariadb': MariaDBConnection,
        'mysql': MariaDBConnection,  # Алиас для MySQL
    }
    
    @classmethod
    def register(cls, db_type: str, connection_class: Type[DatabaseConnection]) -> None:
        """Регистрирует новый тип БД."""
        if not issubclass(connection_class, DatabaseConnection):
            raise TypeError("connection_class должен быть наследником DatabaseConnection")
        cls._registry[db_type.lower()] = connection_class
    
    @classmethod
    def create(cls, db_type: str, **config) -> DatabaseConnection:
        """
        Создает и возвращает экземпляр DatabaseConnection для указанного типа БД.
        
        :param db_type: тип БД ('sqlite', 'mariadb', 'mysql' и т.д.)
        :param config: параметры подключения, зависящие от типа
        :return: объект DatabaseConnection
        """
        db_type = db_type.lower()
        if db_type not in cls._registry:
            raise ValueError(f"Неподдерживаемый тип БД: {db_type}. Доступные: {list(cls._registry.keys())}")
        
        connection_class = cls._registry[db_type]
        try:
            instance = connection_class(**config)
        except TypeError as e:
            raise ValueError(f"Неверная конфигурация для {db_type}: {e}")
        
        return instance