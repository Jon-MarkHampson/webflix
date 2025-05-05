from abc import ABC, abstractmethod


class DataManagerInterface(ABC):

    # User CRUD
    @abstractmethod
    def add_user(self, name: str, profile_pic_url: str = None):
        pass

    @abstractmethod
    def get_user(self, user_id: int):
        pass

    @abstractmethod
    def get_all_users(self):
        pass

    @abstractmethod
    def update_user(self, user_id: int, **kwargs):
        pass

    @abstractmethod
    def delete_user(self, user_id: int):
        pass

    # Movie CRUD
    @abstractmethod
    def add_movie(self, title: str, director: str, year: int):
        pass

    @abstractmethod
    def get_movie(self, movie_id: int):
        pass

    @abstractmethod
    def get_all_movies(self):
        pass

    @abstractmethod
    def update_movie(self, movie_id: int, **kwargs):
        pass

    @abstractmethod
    def delete_movie(self, movie_id: int):
        pass

    # User–Movie association
    @abstractmethod
    def get_user_movies(self, user_id: int):
        pass

    @abstractmethod
    def add_movie_for_user(self, user_id: int, title: str, director: str, year: int, rating: float):
        pass

    @abstractmethod
    def update_movie_for_user(self, user_id: int, movie_id: int, **kwargs):
        pass

    @abstractmethod
    def delete_movie_for_user(self, user_id: int, movie_id: int):
        pass
