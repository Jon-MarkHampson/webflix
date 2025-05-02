from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint

# single shared db instance
db = SQLAlchemy()

# many-to-many join table for Movie ↔ Genre
movie_genre = db.Table(
    'movie_genre',
    db.Column('movie_id', db.Integer, db.ForeignKey(
        'movies.id'),   primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey(
        'genres.id'),   primary_key=True),
)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    profile_pic_url = db.Column(db.String(512))
    favorites = db.relationship(
        'UserMovie',
        back_populates='user',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<User id={self.id} name='{self.name}'>"


class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    director = db.Column(db.String(128))
    year = db.Column(db.Integer)
    omdb_id = db.Column(db.String(32), unique=True)
    plot_short = db.Column(db.Text)
    imdb_rating = db.Column(db.String(8))
    poster_url = db.Column(db.String, nullable=True)  # Added poster URL field
    genres = db.relationship(
        'Genre', secondary=movie_genre, back_populates='movies')
    users = db.relationship(
        'UserMovie', back_populates='movie', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Movie id={self.id} title='{self.title}' year={self.year}>"


class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    movies = db.relationship(
        'Movie', secondary=movie_genre, back_populates='genres')

    def __repr__(self):
        return f"<Genre id={self.id} name='{self.name}'>"


class UserMovie(db.Model):
    __tablename__ = 'user_movies'
    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'), primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey(
        'movies.id', ondelete='CASCADE'), primary_key=True)
    rating = db.Column(db.Float)
    watched = db.Column(db.Boolean, default=False)
    added_on = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship('User',  back_populates='favorites')
    movie = db.relationship('Movie', back_populates='users')

    def __repr__(self):
        return (f"<UserMovie user_id={self.user_id} movie_id={self.movie_id} "
                f"rating={self.rating} watched={self.watched} added_on={self.added_on:%Y-%m-%d}>")
