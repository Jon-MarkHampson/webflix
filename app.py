import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from models import db, User, Movie, UserMovie  # Added UserMovie
import datetime
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
import requests  # Add requests import
from sqlalchemy.exc import IntegrityError  # Import IntegrityError

load_dotenv()  # Load variables from .env file into environment


def create_app():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(BASE_DIR, 'data', 'webflix.db')

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.urandom(24)

    # --- Cloudinary Configuration ---
    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True  # Use https
    )
    # --- End Cloudinary Configuration ---

    # --- OMDb API Key ---
    OMDB_API_KEY = os.environ.get("OMDB_API_KEY")
    if not OMDB_API_KEY:
        print("Warning: OMDB_API_KEY environment variable not set.")
    # --- End OMDb API Key ---

    db.init_app(app)

    @app.context_processor
    def inject_shared_data():
        user_id = session.get('user_id')
        current_user = User.query.get(user_id) if user_id else None
        return {
            'current_year': datetime.datetime.now().year,
            'current_user': current_user
        }

    @app.cli.command("init-db")
    def init_db():
        db.drop_all()
        db.create_all()
        print(f"✅ Database initialized at {db_path}")

    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/users')
    def list_users():
        users = User.query.all()
        return render_template('users.html', users=users)

    @app.route('/all-movies')
    def list_all_movies():
        movies = Movie.query.all()
        return render_template('all_movies.html', movies=movies)

    @app.route('/my-movies')
    def list_my_movies():
        user_id = session.get('user_id')
        if not user_id:
            flash('Please select a user to see their movies.', 'warning')
            return redirect(url_for('list_users'))

        current_user = User.query.get(user_id)
        if not current_user:
            flash('Selected user not found.', 'danger')
            session.pop('user_id', None)
            return redirect(url_for('list_users'))

        # Get the list of UserMovie association objects
        user_movies = current_user.favorites
        # movies = [um.movie for um in user_movies] # Removed this line

        # Pass the list of UserMovie objects to the template under the key 'movies'
        return render_template('my_movies.html', movies=user_movies, user=current_user)

    # --- Route to show edit user form ---
    @app.route('/user/<int:user_id>/edit', methods=['GET'])
    def edit_user_form(user_id):
        user = User.query.get_or_404(user_id)  # Get user or return 404
        return render_template('edit_user.html', user=user)

    # --- Route to handle user update ---
    @app.route('/user/<int:user_id>/update', methods=['POST'])
    def update_user(user_id):
        user = User.query.get_or_404(user_id)
        new_name = request.form.get('name')
        profile_pic_file = request.files.get('profile_pic')

        if not new_name:
            flash('User name cannot be empty.', 'danger')
            return redirect(url_for('edit_user_form', user_id=user_id))

        # Check if name is being changed to one that already exists (excluding the current user)
        existing_user = User.query.filter(
            User.name == new_name, User.id != user_id).first()
        if existing_user:
            flash(
                f'Another user with the name "{new_name}" already exists.', 'warning')
            return redirect(url_for('edit_user_form', user_id=user_id))

        try:
            old_pic_url = user.profile_pic_url  # Store old URL for potential deletion

            # Handle picture update
            if profile_pic_file and profile_pic_file.filename != '':
                # Upload new picture
                upload_result = cloudinary.uploader.upload(
                    profile_pic_file,
                    folder="webflix",
                    resource_type="image"
                )
                new_pic_url = upload_result.get('secure_url')
                if not new_pic_url:
                    flash('Failed to upload new image to Cloudinary.', 'danger')
                    return redirect(url_for('edit_user_form', user_id=user_id))
                user.profile_pic_url = new_pic_url

                # Try to delete old picture from Cloudinary if it existed
                if old_pic_url:
                    try:
                        # Extract public_id from old URL (basic parsing)
                        parts = old_pic_url.split('/')
                        if 'webflix' in parts:
                            public_id_with_ext = parts[-1]
                            public_id = os.path.splitext(public_id_with_ext)[0]
                            cloudinary.uploader.destroy(
                                f"webflix/{public_id}", resource_type="image")
                    except Exception as delete_error:
                        # Log error but continue
                        print(
                            f"Warning: Failed to delete old Cloudinary image {old_pic_url}: {delete_error}")

            # Update name
            user.name = new_name
            db.session.commit()
            flash(f'User "{user.name}" updated successfully!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
            # Redirect back to edit form on error
            return redirect(url_for('edit_user_form', user_id=user_id))

        return redirect(url_for('list_users'))

    @app.route('/add_user', methods=['POST'])
    def add_user():
        name = request.form.get('name')
        profile_pic_file = request.files.get('profile_pic')
        profile_pic_url = None

        if not name:
            flash('User name is required.', 'danger')
            return redirect(url_for('list_users'))

        # Check if user already exists
        existing_user = User.query.filter_by(name=name).first()
        if existing_user:
            flash(f'User "{name}" already exists.', 'warning')
            return redirect(url_for('list_users'))

        try:
            if profile_pic_file and profile_pic_file.filename != '':
                # Upload to Cloudinary in the 'webflix' folder
                upload_result = cloudinary.uploader.upload(
                    profile_pic_file,
                    folder="webflix",  # Specify the folder
                    resource_type="image"  # Ensure it's treated as an image
                )
                profile_pic_url = upload_result.get('secure_url')
                if not profile_pic_url:
                    flash('Failed to upload image to Cloudinary.', 'danger')
                    return redirect(url_for('list_users'))

            # Create new user
            new_user = User(name=name, profile_pic_url=profile_pic_url)
            db.session.add(new_user)
            db.session.commit()
            flash(f'User "{name}" added successfully!', 'success')

        except Exception as e:
            db.session.rollback()  # Rollback in case of error during commit or upload
            flash(f'Error adding user: {str(e)}', 'danger')

        return redirect(url_for('list_users'))

    # --- Delete User Route ---
    @app.route('/user/<int:user_id>/delete', methods=['POST'])
    def delete_user(user_id):
        user = User.query.get_or_404(user_id)
        try:
            user_name = user.name  # Get name for flash message
            pic_url_to_delete = user.profile_pic_url  # Get URL before deleting user

            # Delete user from DB (cascades should handle UserMovie entries)
            db.session.delete(user)
            db.session.commit()

            # Try to delete picture from Cloudinary if it existed
            if pic_url_to_delete:
                try:
                    parts = pic_url_to_delete.split('/')
                    if 'webflix' in parts:
                        public_id_with_ext = parts[-1]
                        public_id = os.path.splitext(public_id_with_ext)[0]
                        cloudinary.uploader.destroy(
                            f"webflix/{public_id}", resource_type="image")
                except Exception as delete_error:
                    print(
                        f"Warning: Failed to delete Cloudinary image {pic_url_to_delete} for deleted user {user_name}: {delete_error}")

            # Clear session if the deleted user was the current user
            if session.get('user_id') == user_id:
                session.pop('user_id', None)
                flash(
                    f'User "{user_name}" deleted. You have been logged out as this user.', 'info')
            else:
                flash(f'User "{user_name}" deleted successfully!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting user: {str(e)}', 'danger')

        return redirect(url_for('list_users'))

    # --- Delete Movie Route ---
    @app.route('/movie/<int:movie_id>/delete', methods=['POST'])
    def delete_movie(movie_id):
        movie = Movie.query.get_or_404(movie_id)
        try:
            movie_title = movie.title  # Get title for flash message

            # Deleting the movie should automatically delete related UserMovie entries
            # due to cascade='all, delete-orphan' on the relationships.
            db.session.delete(movie)
            db.session.commit()
            flash(
                f'Movie "{movie_title}" deleted successfully from the main database!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting movie: {str(e)}', 'danger')

        # Redirect back to the all movies list
        return redirect(url_for('list_all_movies'))
    # --- End Delete Movie Route ---

    # --- Movie Detail Route ---
    @app.route('/movie/<int:movie_id>')
    def movie_detail(movie_id):
        movie = Movie.query.get_or_404(movie_id)
        return render_template('movie_detail.html', movie=movie)
    # --- End Movie Detail Route ---

    # --- OMDb Movie Search Route ---
    @app.route('/search_movies')
    def search_movies():
        search_title = request.args.get('title')
        add_to_user_flag = request.args.get(
            'add_to_user', 'false').lower() == 'true'

        if not search_title:
            flash('Please enter a movie title to search.', 'warning')
            # Redirect back based on context? For now, redirect home.
            return redirect(url_for('home'))

        if not OMDB_API_KEY:
            flash('OMDb API key is not configured. Cannot search for movies.', 'danger')
            # Redirect back to the page the search was initiated from
            if add_to_user_flag and session.get('user_id'):
                return redirect(url_for('list_my_movies'))
            else:
                return redirect(url_for('list_all_movies'))

        search_results = []
        error_message = None
        try:
            # Use 's' parameter for searching by title (returns list)
            params = {'s': search_title,
                      'apikey': OMDB_API_KEY, 'type': 'movie'}
            response = requests.get("http://www.omdbapi.com/", params=params)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            if data.get('Response') == 'True':
                search_results = data.get('Search', [])
            else:
                error_message = data.get('Error', 'Unknown error from OMDb.')

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to OMDb: {e}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"

        if error_message:
            flash(f"OMDb Search Error: {error_message}", 'danger')

        return render_template('search_results.html',
                               results=search_results,
                               search_title=search_title,
                               add_to_user=add_to_user_flag)
    # --- End OMDb Movie Search Route ---

    # --- Add Movie Route (Implementation) ---
    # Allow POST requests from the form
    @app.route('/add_movie/<imdb_id>', methods=['POST'])
    def add_movie_from_omdb(imdb_id):
        add_to_user_flag = request.form.get(
            'add_to_user', 'false').lower() == 'true'
        current_user_id = session.get('user_id')
        movie = None
        new_movie_added = False

        # 1. Check if movie already exists in our DB
        movie = Movie.query.filter_by(omdb_id=imdb_id).first()

        if not movie:
            # 2. If not, fetch details from OMDb using IMDb ID ('i' parameter)
            if not OMDB_API_KEY:
                flash(
                    'OMDb API key is not configured. Cannot add movie details.', 'danger')
                # Redirect back based on context
                redirect_url = url_for(
                    'list_my_movies') if add_to_user_flag and current_user_id else url_for('list_all_movies')
                return redirect(redirect_url)

            try:
                params = {'i': imdb_id, 'apikey': OMDB_API_KEY,
                          'plot': 'short'}  # Get short plot
                response = requests.get(
                    "http://www.omdbapi.com/", params=params)
                response.raise_for_status()
                data = response.json()

                if data.get('Response') == 'True':
                    # Convert year safely
                    year = None
                    try:
                        year_str = data.get('Year')
                        # Handle year ranges like "2001-2003"
                        if year_str and '-' in year_str:
                            year_str = year_str.split(
                                '-')[0]  # Take the start year
                        if year_str and year_str.isdigit():
                            year = int(year_str)
                    except (ValueError, TypeError):
                        year = None  # Keep as None if conversion fails

                    # 3. Create and save the new movie
                    movie = Movie(
                        title=data.get('Title', 'N/A'),
                        director=data.get('Director', 'N/A'),
                        year=year,
                        omdb_id=imdb_id,
                        plot_short=data.get('Plot', ''),
                        # Fetch IMDb rating
                        imdb_rating=data.get('imdbRating', 'N/A'),
                        poster_url=data.get('Poster') if data.get(
                            'Poster') != 'N/A' else None  # Store Poster URL
                    )
                    db.session.add(movie)
                    db.session.commit()
                    flash(
                        f'Movie "{movie.title}" added to the main database.', 'success')
                    new_movie_added = True
                else:
                    flash(
                        f"Error fetching details from OMDb: {data.get('Error', 'Unknown error')}", 'danger')
                    # Redirect back
                    redirect_url = url_for(
                        'list_my_movies') if add_to_user_flag and current_user_id else url_for('list_all_movies')
                    return redirect(redirect_url)

            except requests.exceptions.RequestException as e:
                db.session.rollback()
                flash(f"Error connecting to OMDb: {e}", 'danger')
                redirect_url = url_for(
                    'list_my_movies') if add_to_user_flag and current_user_id else url_for('list_all_movies')
                return redirect(redirect_url)
            # Catch potential unique constraint errors (e.g., omdb_id)
            except IntegrityError:
                db.session.rollback()
                flash(
                    f"Database error: Movie with OMDb ID {imdb_id} might already exist.", 'warning')
                # Try fetching again in case of race condition
                movie = Movie.query.filter_by(omdb_id=imdb_id).first()
                if not movie:  # If still not found after rollback, something else is wrong
                    flash("Could not retrieve movie after database error.", 'danger')
                    redirect_url = url_for(
                        'list_my_movies') if add_to_user_flag and current_user_id else url_for('list_all_movies')
                    return redirect(redirect_url)
            except Exception as e:
                db.session.rollback()
                flash(
                    f"An unexpected error occurred while adding movie: {e}", 'danger')
                redirect_url = url_for(
                    'list_my_movies') if add_to_user_flag and current_user_id else url_for('list_all_movies')
                return redirect(redirect_url)
        else:
            if not new_movie_added:  # Only flash if we didn't just add it
                flash(
                    f'Movie "{movie.title}" already exists in the database.', 'info')

        # 4. If add_to_user flag is set, add to user's list
        if add_to_user_flag:
            if not current_user_id:
                flash('You must be logged in to add movies to your list.', 'warning')
            # Ensure we have a movie object (either found or newly created)
            elif movie:
                current_user = User.query.get(current_user_id)
                if current_user:
                    # Check if the association already exists
                    existing_user_movie = UserMovie.query.filter_by(
                        user_id=current_user_id, movie_id=movie.id).first()
                    if not existing_user_movie:
                        try:
                            user_movie_link = UserMovie(
                                user_id=current_user_id, movie_id=movie.id)
                            db.session.add(user_movie_link)
                            db.session.commit()
                            flash(
                                f'Movie "{movie.title}" added to your list.', 'success')
                        except Exception as e:
                            db.session.rollback()
                            flash(
                                f"Error adding movie to your list: {e}", 'danger')
                    else:
                        flash(
                            f'Movie "{movie.title}" is already in your list.', 'info')
                else:
                    # Should not happen if session is valid
                    flash('Current user not found.', 'danger')

        # 5. Redirect back
        redirect_url = url_for(
            'list_my_movies') if add_to_user_flag and current_user_id else url_for('list_all_movies')
        return redirect(redirect_url)
    # --- End Add Movie Route ---

    @app.route('/set_user/<int:user_id>')
    def set_user(user_id):
        user = User.query.get(user_id)
        if user:
            session['user_id'] = user_id
            flash(f'User set to {user.name}.', 'success')
        else:
            flash('User not found.', 'danger')
        return redirect(url_for('list_users'))

    @app.route('/logout')
    def logout():
        session.pop('user_id', None)
        flash('You have been logged out.', 'info')
        return redirect(url_for('home'))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(port=5001, debug=True)
