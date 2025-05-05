from datamanager.data_manager_interface import DataManagerInterface
from models import db, User, Movie, Genre, UserMovie


class SQLiteDataManager(DataManagerInterface):
    # — User CRUD —
    def add_user(self, name, profile_pic_url=None):
        u = User(name=name, profile_pic_url=profile_pic_url)
        db.session.add(u)
        db.session.commit()
        return u

    def get_user(self, user_id):
        return User.query.get(user_id)

    def get_all_users(self):
        return User.query.all()

    def update_user(self, user_id, **kw):
        u = User.query.get(user_id)
        if not u:
            return None
        for k, v in kw.items():
            if hasattr(u, k):
                setattr(u, k, v)
        db.session.commit()
        return u

    def delete_user(self, user_id):
        u = User.query.get(user_id)
        if not u:
            return False
        db.session.delete(u)
        db.session.commit()
        return True

    # — Movie CRUD —
    def add_movie(self, title, director, year):
        m = Movie.query.filter_by(title=title, year=year).first()
        if not m:
            m = Movie(title=title, director=director, year=year)
            db.session.add(m)
            db.session.commit()
        return m

    def get_movie(self, movie_id):
        return Movie.query.get(movie_id)

    def get_all_movies(self):
        return Movie.query.all()

    def update_movie(self, movie_id, **kw):
        m = Movie.query.get(movie_id)
        if not m:
            return None
        for k, v in kw.items():
            if hasattr(m, k):
                setattr(m, k, v)
        db.session.commit()
        return m

    def delete_movie(self, movie_id):
        m = Movie.query.get(movie_id)
        if not m:
            return False
        db.session.delete(m)
        db.session.commit()
        return True

    # — User–Movie linkage —
    def get_user_movies(self, user_id):
        u = User.query.get(user_id)
        return [link.movie for link in u.favorites] if u else []

    def add_movie_for_user(self, user_id, title, director, year, rating):
        m = self.add_movie(title, director, year)
        link = UserMovie.query.get((user_id, m.id))
        if link:
            link.rating = rating
        else:
            link = UserMovie(user_id=user_id, movie_id=m.id, rating=rating)
            db.session.add(link)
        db.session.commit()
        return link

    def update_movie_for_user(self, user_id, movie_id, **kw):
        link = UserMovie.query.get((user_id, movie_id))
        if not link:
            return None
        for k, v in kw.items():
            if hasattr(link, k):
                setattr(link, k, v)
        db.session.commit()
        return link

    def delete_movie_for_user(self, user_id, movie_id):
        link = UserMovie.query.get((user_id, movie_id))
        if not link:
            return False
        db.session.delete(link)
        db.session.commit()
        return True
