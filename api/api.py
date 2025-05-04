from flask import Blueprint, jsonify, request
import os
import requests
from models import User, UserMovie, Movie, db

api = Blueprint('api', __name__)


@api.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([
        {"id": u.id, "name": u.name, "profile_pic_url": u.profile_pic_url}
        for u in users
    ])


@api.route('/users/<int:user_id>/movies', methods=['GET'])
def get_user_movies(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify([
        {
            'id': um.movie.id,
            'title': um.movie.title,
            'director': um.movie.director,
            'year': um.movie.year,
            'omdb_id': um.movie.omdb_id,
            'poster_url': um.movie.poster_url,
            'rating': um.rating,
            'watched': um.watched,
            'added_on': um.added_on.isoformat()
        }
        for um in user.favorites
    ])


@api.route('/users/<int:user_id>/add-movies', methods=['POST'])
def add_favorite_movies(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    items = data if isinstance(data, list) else [data]
    api_key = os.environ.get('OMDB_API_KEY')
    if not api_key:
        return jsonify({'error': 'OMDB API key not configured'}), 500
    added, errors = [], []
    for item in items:
        title = item.get('title')
        imdb_id = item.get('imdb_id')
        if not (title or imdb_id):
            errors.append(
                {'movie': item, 'error': 'title or imdb_id required'})
            continue
        try:
            # If title provided, search OMDb to get imdb_id
            if title and not imdb_id:
                resp = requests.get(
                    'http://www.omdbapi.com/', params={'s': title, 'apikey': api_key, 'type': 'movie'})
                resp.raise_for_status()
                sd = resp.json()
                if sd.get('Response') != 'True' or not sd.get('Search'):
                    raise ValueError(sd.get('Error', 'No results'))
                imdb_id = sd['Search'][0].get('imdbID')
            # Fetch full details from OMDb
            resp = requests.get(
                'http://www.omdbapi.com/', params={'i': imdb_id, 'apikey': api_key, 'plot': 'short'})
            resp.raise_for_status()
            details = resp.json()
            if details.get('Response') != 'True':
                raise ValueError(details.get('Error', 'Detail fetch failed'))
            # Parse year
            year_val = None
            yr = details.get('Year')
            if yr:
                if '-' in yr:
                    yr = yr.split('-')[0]
                if yr.isdigit():
                    year_val = int(yr)
            # Create or get movie
            movie = Movie.query.filter_by(omdb_id=imdb_id).first()
            if not movie:
                movie = Movie(
                    title=details.get('Title'),
                    director=details.get('Director'),
                    year=year_val,
                    omdb_id=imdb_id,
                    plot_short=details.get('Plot', ''),
                    imdb_rating=details.get('imdbRating'),
                    poster_url=(details.get('Poster') if details.get(
                        'Poster') != 'N/A' else None)
                )
                db.session.add(movie)
                db.session.commit()
            # Link to user
            link = UserMovie.query.get((user_id, movie.id))
            if not link:
                link = UserMovie(user_id=user_id, movie_id=movie.id)
                db.session.add(link)
                db.session.commit()
            added.append(
                {'movie_id': movie.id, 'imdb_id': imdb_id, 'title': movie.title})
        except Exception as e:
            errors.append({'movie': item, 'error': str(e)})
    return jsonify({'added': added, 'errors': errors}), 200


@api.route('/users/<int:user_id>/remove-movies', methods=['POST'])
def remove_favorite_movies(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    items = data if isinstance(data, list) else [data]
    removed, errors = [], []
    for item in items:
        movie_id = item.get('movie_id')
        if not movie_id:
            errors.append(
                {'movie': item, 'error': 'movie_id required'})
            continue
        try:
            link = UserMovie.query.get((user_id, movie_id))
            if link:
                db.session.delete(link)
                db.session.commit()
                removed.append(movie_id)
            else:
                errors.append(
                    {'movie': item, 'error': 'Movie not found in favorites'})
        except Exception as e:
            errors.append({'movie': item, 'error': str(e)})
    return jsonify({'removed': removed, 'errors': errors}), 200