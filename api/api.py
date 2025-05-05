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
    # Read raw data as text and split by comma
    data = request.get_data(as_text=True)
    if not data:
        return jsonify({'error': 'Request body with comma-separated titles required'}), 400
    # Split the string into titles and strip whitespace
    titles = [title.strip() for title in data.split(',') if title.strip()]
    if not titles:
        return jsonify({'error': 'No valid titles provided in the comma-separated list'}), 400

    api_key = os.environ.get('OMDB_API_KEY')
    if not api_key:
        return jsonify({'error': 'OMDB API key not configured'}), 500
    added, errors = [], []
    # Iterate over the list of titles
    for title in titles:
        imdb_id = None  # Reset imdb_id for each title
        try:
            # Search OMDb by title to get imdb_id
            resp = requests.get(
                'http://www.omdbapi.com/', params={'s': title, 'apikey': api_key, 'type': 'movie'})
            resp.raise_for_status()
            sd = resp.json()
            if sd.get('Response') != 'True' or not sd.get('Search'):
                raise ValueError(sd.get('Error', f'No results for "{title}"'))
            # Take the first result's imdbID
            imdb_id = sd['Search'][0].get('imdbID')
            if not imdb_id:
                raise ValueError(
                    f'Could not find IMDb ID for "{title}" in search results')

            # Fetch full details from OMDb using the found imdb_id
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
                # Commit movie immediately to get its ID for the link
                db.session.commit()
            # Link to user
            link = UserMovie.query.get((user_id, movie.id))
            if not link:
                link = UserMovie(user_id=user_id, movie_id=movie.id)
                db.session.add(link)
                db.session.commit()  # Commit link separately
            added.append(
                {'movie_id': movie.id, 'imdb_id': imdb_id, 'title': movie.title})
        except Exception as e:
            # Rollback potentially failed adds within the loop
            db.session.rollback()
            errors.append({'title_searched': title, 'error': str(e)})
    # Return 207 Multi-Status if there were errors, otherwise 200 OK
    status_code = 207 if errors else 200
    return jsonify({'added': added, 'errors': errors}), status_code


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
