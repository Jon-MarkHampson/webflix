import os
from flask import Flask, render_template, session, redirect, url_for, flash, request
from models import db, User, Movie, UserMovie, Genre
import datetime
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import requests
from sqlalchemy.exc import IntegrityError
from api.api import api
from sqlalchemy import asc, desc, func

load_dotenv()


def create_app():
    """Create and configure the Flask application.

    - Sets up database URI, secret key, Cloudinary, and OMDb API key check.
    - Registers blueprints, context processors, CLI commands, and routes.

    Returns:
        Flask: The configured Flask application instance.
    """
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(BASE_DIR, "data", "webflix.db")

    app = Flask(__name__)
    app.register_blueprint(api, url_prefix="/api")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.urandom(24)

    # Set up Cloudinary configuration
    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True,  # Use https
    )

    # Check if OMDB API key is set
    OMDB_API_KEY = os.environ.get("OMDB_API_KEY")
    if not OMDB_API_KEY:
        print("Warning: OMDB_API_KEY environment variable not set.")

    db.init_app(app)

    @app.context_processor
    def inject_shared_data():
        """Inject common data into all templates.

        Returns:
            dict: current_year and current_user for template context.
        """
        user_id = session.get("user_id")
        current_user = User.query.get(user_id) if user_id else None
        return {
            "current_year": datetime.datetime.now().year,
            "current_user": current_user,
        }

    @app.cli.command("init-db")
    def init_db():
        """Drop all tables and recreate them to initialize the database."""
        db.drop_all()
        db.create_all()
        print(f"✅ Database initialized at {db_path}")

    @app.cli.command("seed-genres")
    def seed_genres():
        """Seed the database with a predefined list of movie genres."""
        genres_to_add = [
            "Action",
            "Adventure",
            "Animation",
            "Biography",
            "Comedy",
            "Crime",
            "Documentary",
            "Drama",
            "Family",
            "Fantasy",
            "Film Noir",
            "History",
            "Horror",
            "Music",
            "Musical",
            "Mystery",
            "Romance",
            "Sci-Fi",
            "Short Film",
            "Sport",
            "Superhero",
            "Thriller",
            "War",
            "Western",
        ]
        count = 0
        for genre_name in genres_to_add:
            # Check if genre already exists (case-insensitive)
            existing_genre = Genre.query.filter(
                func.lower(Genre.name) == func.lower(genre_name)
            ).first()
            if not existing_genre:
                try:
                    new_genre = Genre(name=genre_name)
                    db.session.add(new_genre)
                    db.session.commit()
                    count += 1
                except Exception as e:
                    db.session.rollback()
                    print(f"Error adding genre '{genre_name}': {e}")

        if count > 0:
            print(f"✅ Added {count} new genres to the database.")
        else:
            print("ℹ️ All predefined genres already exist in the database.")

    @app.route("/")
    def home():
        """Render the home page."""
        return render_template("home.html")

    @app.route("/users")
    def list_users():
        """Display a list of all users."""
        users = User.query.all()
        return render_template("users.html", users=users)

    @app.route("/add_user_form")
    def add_user_form():
        """Render the form to add a new user."""
        users = User.query.all()
        return render_template("add_user.html", users=users)

    @app.route("/all-movies")
    def list_all_movies():
        """List all movies with optional sorting and genre filtering."""
        # Get sorting/filtering parameters from query string, with defaults
        sort_by = request.args.get("sort_by", "title")
        sort_dir = request.args.get("sort_dir", "asc")
        # Change filter param to expect genre ID, default to 'all'
        filter_genre_id = request.args.get("filter_genre_id", "all")

        # Fetch all genres for the dropdown
        all_genres = Genre.query.order_by(Genre.name).all()

        # Base query
        query = Movie.query

        # Apply genre filter using the relationship
        if filter_genre_id != "all":
            try:
                genre_id_int = int(filter_genre_id)
                # Filter movies that have the selected genre ID in their genres relationship
                query = query.filter(Movie.genres.any(Genre.id == genre_id_int))
            except ValueError:
                flash("Invalid genre selected.", "warning")
                # Optionally reset filter_genre_id to 'all' or handle error differently
                filter_genre_id = "all"

        # Determine sort direction
        direction = asc if sort_dir == "asc" else desc

        # Apply sorting - handle case-insensitivity for text fields
        if sort_by == "title":
            query = query.order_by(direction(func.lower(Movie.title)))
        elif sort_by == "release_date":
            query = query.order_by(direction(Movie.year))
        elif sort_by == "rating":
            query = query.order_by(direction(Movie.imdb_rating))

        movies = query.all()

        # Pass current sort/filter values and all genres to template
        return render_template(
            "all_movies.html",
            movies=movies,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filter_genre_id=filter_genre_id,
            all_genres=all_genres,
        )

    @app.route("/my-movies")
    def list_my_movies():
        """List movies in the current user's personal collection."""
        user_id = session.get("user_id")
        if not user_id:
            flash("Please select a user to see their movies.", "warning")
            return redirect(url_for("list_users"))

        current_user = User.query.get(user_id)
        if not current_user:
            flash("Selected user not found.", "danger")
            session.pop("user_id", None)
            return redirect(url_for("list_users"))

        # Get sorting/filtering parameters, with defaults
        sort_by = request.args.get("sort_by", "title")
        sort_dir = request.args.get("sort_dir", "asc")
        filter_watched = request.args.get("filter_watched", "all")
        filter_genre_id = request.args.get("filter_genre_id", "all")

        # Fetch all genres for the dropdown
        all_genres = Genre.query.order_by(Genre.name).all()

        # Base query for UserMovie association objects, joining with Movie
        query = UserMovie.query.filter_by(user_id=user_id).join(Movie)

        # Apply watched filter
        if filter_watched == "watched":
            query = query.filter(UserMovie.watched)
        elif filter_watched == "unwatched":
            query = query.filter(~UserMovie.watched)

        # Apply genre filter using the relationship on the joined Movie
        if filter_genre_id != "all":
            try:
                genre_id_int = int(filter_genre_id)
                # Filter based on the joined Movie's genres
                query = query.filter(Movie.genres.any(Genre.id == genre_id_int))
            except ValueError:
                flash("Invalid genre selected.", "warning")
                filter_genre_id = "all"

        # Determine sort direction
        direction = asc if sort_dir == "asc" else desc

        # Apply sorting based on Movie attributes
        if sort_by == "title":
            query = query.order_by(direction(func.lower(Movie.title)))
        elif sort_by == "release_date":
            query = query.order_by(direction(Movie.year))
        elif sort_by == "rating":
            query = query.order_by(direction(Movie.imdb_rating))
        # Sorting by genre name is complex here too.

        user_movies = query.all()

        if (
            not user_movies
            and filter_watched == "all"
            and sort_by == "title"
            and sort_dir == "asc"
        ):
            # Only show "no movies" if there are truly no movies, not just filtered out
            flash("No movies found for this user.", "info")

        # Pass current sort/filter values and all genres to template
        return render_template(
            "my_movies.html",
            movies=user_movies,
            user=current_user,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filter_watched=filter_watched,
            filter_genre_id=filter_genre_id,
            all_genres=all_genres,
        )

    @app.route("/add-movie-search")
    def add_movie_search_page():
        """Render the search page for finding and adding movies."""
        # Determine if the user is logged in to set the context for adding
        add_to_user = "user_id" in session
        return render_template("add_movie_search.html", add_to_user=add_to_user)

    # --- Route to handle user editing ---
    @app.route("/user/<int:user_id>/edit", methods=["GET"])
    def edit_user_form(user_id):
        """Render the edit form for an existing user.

        Args:
            user_id (int): ID of the user to edit.
        """
        user = User.query.get_or_404(user_id)
        return render_template("edit_user.html", user=user)

    # --- Route to handle user update ---
    @app.route("/user/<int:user_id>/update", methods=["POST"])
    def update_user(user_id):
        """Process the user update form submission.

        Args:
            user_id (int): ID of the user to update.
        """
        user = User.query.get_or_404(user_id)
        new_name = request.form.get("name")
        profile_pic_file = request.files.get("profile_pic")

        if not new_name:
            flash("User name cannot be empty.", "danger")
            return redirect(url_for("edit_user_form", user_id=user_id))

        # Check if name is being changed to one that already exists (excluding the current user)
        existing_user = User.query.filter(
            User.name == new_name, User.id != user_id
        ).first()
        if existing_user:
            flash(f'Another user with the name "{new_name}" already exists.', "warning")
            return redirect(url_for("edit_user_form", user_id=user_id))

        # Store old URL for potential deletion
        try:
            old_pic_url = user.profile_pic_url

            # Handle picture update
            if profile_pic_file and profile_pic_file.filename != "":
                # Upload new picture
                upload_result = cloudinary.uploader.upload(
                    profile_pic_file, folder="webflix", resource_type="image"
                )
                new_pic_url = upload_result.get("secure_url")
                if not new_pic_url:
                    flash("Failed to upload new image to Cloudinary.", "danger")
                    return redirect(url_for("edit_user_form", user_id=user_id))
                user.profile_pic_url = new_pic_url

                # Try to delete old picture from Cloudinary if it existed
                if old_pic_url:
                    try:
                        # Extract public_id from old URL (basic parsing)
                        parts = old_pic_url.split("/")
                        if "webflix" in parts:
                            public_id_with_ext = parts[-1]
                            public_id = os.path.splitext(public_id_with_ext)[0]
                            cloudinary.uploader.destroy(
                                f"webflix/{public_id}", resource_type="image"
                            )
                    except Exception as delete_error:
                        # Log error but continue
                        print(
                            f"Warning: Failed to delete old Cloudinary image {old_pic_url}: {delete_error}"
                        )

            # Update name
            user.name = new_name
            db.session.commit()
            flash(f'User "{user.name}" updated successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating user: {str(e)}", "danger")
            # Redirect back to edit form on error
            return redirect(url_for("edit_user_form", user_id=user_id))

        return redirect(url_for("list_users"))

    # --- Route to handle adding a new user ---
    @app.route("/add_user", methods=["POST"])
    def add_user():
        """Handle creation of a new user from form data."""
        name = request.form.get("name")
        profile_pic_file = request.files.get("profile_pic")
        profile_pic_url = None

        if not name:
            flash("User name is required.", "danger")
            return redirect(url_for("add_user_form"))

        # Check if user already exists
        existing_user = User.query.filter_by(name=name).first()
        if existing_user:
            flash(f'User "{name}" already exists.', "warning")
            return redirect(url_for("add_user_form"))

        try:
            if profile_pic_file and profile_pic_file.filename != "":
                # Upload to Cloudinary in the 'webflix' folder
                upload_result = cloudinary.uploader.upload(
                    profile_pic_file,
                    folder="webflix",  # Specify the folder
                    resource_type="image",  # Ensure it's treated as an image
                )
                profile_pic_url = upload_result.get("secure_url")
                if not profile_pic_url:
                    flash("Failed to upload image to Cloudinary.", "danger")
                    return redirect(url_for("add_user_form"))

            # Create new user
            new_user = User(name=name, profile_pic_url=profile_pic_url)
            db.session.add(new_user)
            db.session.commit()
            flash(f'User "{name}" added successfully!', "success")

        except Exception as e:
            # Rollback in case of error during commit or upload
            db.session.rollback()
            flash(f"Error adding user: {str(e)}", "danger")

        return redirect(url_for("list_users"))

    # --- Delete User Route ---
    @app.route("/user/<int:user_id>/delete", methods=["POST"])
    def delete_user(user_id):
        """Delete a user (and their Cloudinary image), handling session cleanup.

        Args:
            user_id (int): ID of the user to delete.
        """
        user = User.query.get_or_404(user_id)
        try:
            # Get name for flash message and URL before deletion
            user_name = user.name
            pic_url_to_delete = user.profile_pic_url

            # Delete user from DB (cascades should handle UserMovie entries)
            db.session.delete(user)
            db.session.commit()

            # Try to delete picture from Cloudinary if it existed
            if pic_url_to_delete:
                try:
                    parts = pic_url_to_delete.split("/")
                    if "webflix" in parts:
                        public_id_with_ext = parts[-1]
                        public_id = os.path.splitext(public_id_with_ext)[0]
                        cloudinary.uploader.destroy(
                            f"webflix/{public_id}", resource_type="image"
                        )
                except Exception as delete_error:
                    print(
                        f"Warning: Failed to delete Cloudinary image {pic_url_to_delete} for deleted user {user_name}: {delete_error}"
                    )

            # Clear session if the deleted user was the current user
            if session.get("user_id") == user_id:
                session.pop("user_id", None)
                flash(
                    f'User "{user_name}" deleted. You have been logged out as this user.',
                    "info",
                )
            else:
                flash(f'User "{user_name}" deleted successfully!', "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting user: {str(e)}", "danger")

        return redirect(url_for("list_users"))

    # --- Delete Movie Route ---
    @app.route("/movie/<int:movie_id>/delete", methods=["POST"])
    def delete_movie(movie_id):
        """Delete a movie from the database and all user associations.

        Args:
            movie_id (int): ID of the movie to delete.
        """
        movie = Movie.query.get_or_404(movie_id)
        try:
            # Get title for flash message
            movie_title = movie.title

            # Deleting the movie should automatically delete related UserMovie entries
            # due to cascade='all, delete-orphan' on the relationships.
            db.session.delete(movie)
            db.session.commit()
            flash(
                f'Movie "{movie_title}" deleted successfully from the main database!',
                "success",
            )

        except Exception as e:
            db.session.rollback()
            flash(f"Error deleting movie: {str(e)}", "danger")

        # Redirect back to the all movies list
        return redirect(url_for("list_all_movies"))

    # --- Movie Detail Route ---
    @app.route("/movie/<int:movie_id>")
    def movie_detail(movie_id):
        """Show the detail page for a single movie.

        Args:
            movie_id (int): ID of the movie to display.
        """
        movie = Movie.query.get_or_404(movie_id)
        user_movie = None
        all_genres = Genre.query.order_by(Genre.name).all()

        # Check if a user is logged in
        user_id = session.get("user_id")
        if user_id:
            # Try to find the specific UserMovie association for this user and movie
            user_movie = UserMovie.query.filter_by(
                user_id=user_id, movie_id=movie_id
            ).first()

        # Pass the movie, user_movie, and all genres to the template
        return render_template(
            "movie_detail.html",
            movie=movie,
            user_movie=user_movie,
            all_genres=all_genres,
        )

    # --- OMDb Movie Search Route ---
    @app.route("/search_movies")
    def search_movies():
        """Search for movies via the OMDb API by title and show results."""
        search_title = request.args.get("title")
        # Determine the context (add to user or global) based on who initiated the search
        # This comes from the dedicated search page's context
        add_to_user_flag = request.args.get("add_to_user", "false").lower() == "true"

        if not search_title:
            flash("Please enter a movie title to search.", "warning")
            # Redirect back to the search page
            return redirect(url_for("add_movie_search_page"))

        if not OMDB_API_KEY:
            flash("OMDb API key is not configured. Cannot search for movies.", "danger")
            # Redirect back to the search page
            return redirect(url_for("add_movie_search_page"))

        search_results = []
        error_message = None
        try:
            # Use 's' parameter for searching by title (returns list)
            params = {"s": search_title, "apikey": OMDB_API_KEY, "type": "movie"}
            response = requests.get("http://www.omdbapi.com/", params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("Response") == "True":
                search_results = data.get("Search", [])
            else:
                error_message = data.get("Error", "Unknown error from OMDb.")

        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to OMDb: {e}"
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"

        if error_message:
            flash(f"OMDb Search Error: {error_message}", "danger")
            # Redirect back to the search page
            return redirect(url_for("add_movie_search_page"))

        # Render the results page, passing the context flag
        return render_template(
            "search_results.html",
            results=search_results,
            search_title=search_title,
            add_to_user=add_to_user_flag,
        )

    # --- Add Movie Route ---
    # Allow POST requests from the form
    @app.route("/add_movie/<imdb_id>", methods=["POST"])
    def add_movie_from_omdb(imdb_id):
        """Add a movie from OMDb to the database and optionally to the user's list.

        Args:
            imdb_id (str): IMDb ID of the movie to add.
        """
        add_to_user_flag = request.form.get("add_to_user", "false").lower() == "true"
        current_user_id = session.get("user_id")
        movie = None
        new_movie_added = False
        # Get original search term for redirection
        originating_search_title = request.form.get("search_title", "")

        # Determine the redirect URL early based on the context
        # If adding to user, redirect to user's movies, otherwise to all movies.
        # Consider redirecting back to search results? For now, stick to lists.
        if add_to_user_flag and current_user_id:
            success_redirect_url = url_for("list_my_movies")
            # Redirect back to search results with the original query on failure/info
            failure_redirect_url = url_for(
                "search_movies", title=originating_search_title, add_to_user="true"
            )
        else:
            success_redirect_url = url_for("list_all_movies")
            # Redirect back to search results with the original query on failure/info
            failure_redirect_url = url_for(
                "search_movies", title=originating_search_title, add_to_user="false"
            )

        # 1. Check if movie already exists in our DB
        movie = Movie.query.filter_by(omdb_id=imdb_id).first()

        if not movie:
            # 2. If not, fetch details from OMDb using IMDb ID ('i' parameter)
            if not OMDB_API_KEY:
                flash(
                    "OMDb API key is not configured. Cannot add movie details.",
                    "danger",
                )
                return redirect(failure_redirect_url)

            try:
                # Get short plot
                params = {"i": imdb_id, "apikey": OMDB_API_KEY, "plot": "short"}
                response = requests.get("http://www.omdbapi.com/", params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("Response") == "True":
                    # Convert year safely
                    year = None
                    try:
                        year_str = data.get("Year")
                        # Handle year ranges like "2001-2003"
                        if year_str and "-" in year_str:
                            year_str = year_str.split("-")[0]  # Take the start year
                        if year_str and year_str.isdigit():
                            year = int(year_str)
                    except (ValueError, TypeError):
                        year = None  # Keep as None if conversion fails

                    # 3. Create and save the new movie
                    movie = Movie(
                        title=data.get("Title", "N/A"),
                        director=data.get("Director", "N/A"),
                        year=year,
                        omdb_id=imdb_id,
                        plot_short=data.get("Plot", ""),
                        # Fetch IMDb rating
                        imdb_rating=data.get("imdbRating", "N/A"),
                        poster_url=(
                            data.get("Poster") if data.get("Poster") != "N/A" else None
                        ),  # Store Poster URL
                    )
                    db.session.add(movie)
                    db.session.commit()
                    flash(
                        f'Movie "{movie.title}" added to the main database.', "success"
                    )
                    new_movie_added = True
                else:
                    flash(
                        f"Error fetching details from OMDb: {data.get('Error', 'Unknown error')}",
                        "danger",
                    )
                    return redirect(failure_redirect_url)

            except requests.exceptions.RequestException as e:
                db.session.rollback()
                flash(f"Error connecting to OMDb: {e}", "danger")
                return redirect(failure_redirect_url)
            # Catch potential unique constraint errors (e.g., omdb_id)
            except IntegrityError:
                db.session.rollback()
                flash(
                    f"Database error: Movie with OMDb ID {imdb_id} might already exist.",
                    "warning",
                )
                # Try fetching again in case of race condition
                movie = Movie.query.filter_by(omdb_id=imdb_id).first()
                if (
                    not movie
                ):  # If still not found after rollback, something else is wrong
                    flash("Could not retrieve movie after database error.", "danger")
                    return redirect(failure_redirect_url)
            except Exception as e:
                db.session.rollback()
                flash(f"An unexpected error occurred while adding movie: {e}", "danger")
                return redirect(failure_redirect_url)
        else:
            # Only flash if we didn't just add it and are trying to add globally
            if not new_movie_added and not add_to_user_flag:
                flash(f'Movie "{movie.title}" already exists in the database.', "info")

        # 4. If add_to_user flag is set AND user is logged in, add to user's list
        if add_to_user_flag:
            if not current_user_id:
                flash("You must be logged in to add movies to your list.", "warning")
                # Redirect to login or user list? Redirecting to failure URL (search results) for now.
                return redirect(failure_redirect_url)
            # Ensure we have a movie object (either found or newly created)
            elif movie:
                current_user = User.query.get(current_user_id)
                if current_user:
                    # Check if the association already exists
                    existing_user_movie = UserMovie.query.filter_by(
                        user_id=current_user_id, movie_id=movie.id
                    ).first()
                    if not existing_user_movie:
                        try:
                            user_movie_link = UserMovie(
                                user_id=current_user_id, movie_id=movie.id
                            )
                            db.session.add(user_movie_link)
                            db.session.commit()
                            flash(
                                f'Movie "{movie.title}" added to your list.', "success"
                            )
                        except Exception as e:
                            db.session.rollback()
                            flash(f"Error adding movie to your list: {e}", "danger")
                            # Redirect to failure URL on error adding to user list
                            return redirect(failure_redirect_url)
                    else:
                        flash(f'Movie "{movie.title}" is already in your list.', "info")
                else:
                    # Should not happen if session is valid
                    flash("Current user not found.", "danger")
                    # Redirect back to search on error
                    return redirect(failure_redirect_url)
            else:
                # Should not happen if movie wasn't found/created correctly
                flash("Could not find or create movie to add to your list.", "danger")
                # Redirect back to search on error
                return redirect(failure_redirect_url)

        # 5. Redirect to the appropriate success page
        return redirect(success_redirect_url)

    # --- Set User Route ---
    @app.route("/set_user/<int:user_id>")
    def set_user(user_id):
        """Set the current session user.

        Args:
            user_id (int): ID of the user to set in session.
        """
        user = User.query.get(user_id)
        if user:
            session["user_id"] = user_id
            # flash(f'User set to {user.name}.', 'success')
        else:
            flash("User not found.", "danger")
        return redirect(url_for("list_users"))

    @app.route("/logout")
    def logout():
        """Log out the current user by clearing session data."""
        session.pop("user_id", None)
        flash("You have been logged out.", "info")
        return redirect(url_for("home"))

    # --- Toggle Watched Status Route ---
    @app.route(
        "/user/<int:user_id>/movie/<int:movie_id>/toggle-watched", methods=["POST"]
    )
    def toggle_watched(user_id, movie_id):
        """Toggle the watched status for a user's movie.

        Args:
            user_id (int): ID of the user.
            movie_id (int): ID of the movie.
        """
        user_movie = UserMovie.query.filter_by(
            user_id=user_id, movie_id=movie_id
        ).first()
        if user_movie:
            try:
                # Toggle the status
                user_movie.watched = not user_movie.watched
                db.session.commit()
                status = "watched" if user_movie.watched else "not watched"
                flash(
                    f'Movie "{user_movie.movie.title}" marked as {status}.', "success"
                )
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating watched status: {str(e)}", "danger")
        else:
            flash("Movie not found in your list.", "warning")

        return redirect(url_for("list_my_movies", user_id=user_id))

    # --- Delete movie from user's list Route ---
    @app.route("/users/<int:user_id>/movies/<int:movie_id>/delete", methods=["POST"])
    def delete_user_movie(user_id, movie_id):
        """Remove a movie from a user's list without deleting it globally.

        Args:
            user_id (int): ID of the user.
            movie_id (int): ID of the movie to remove.
        """
        # Check if the movie is in the user's list
        user_movie = UserMovie.query.filter_by(
            user_id=user_id, movie_id=movie_id
        ).first()

        if user_movie:
            try:
                # Get movie title for the flash message
                movie_title = user_movie.movie.title

                # Delete the association
                db.session.delete(user_movie)
                db.session.commit()

                flash(f'"{movie_title}" has been removed from your list.', "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error removing movie from your list: {str(e)}", "danger")
        else:
            flash("This movie is not in your list.", "warning")

        # Redirect back to the user's movie list
        return redirect(url_for("list_my_movies"))

    # --- Update Movie Genres Route ---
    @app.route("/movie/<int:movie_id>/update_genres", methods=["POST"])
    def update_movie_genres(movie_id):
        """Update the genres associated with a movie (max 4).

        Args:
            movie_id (int): ID of the movie to update genres for.
        """
        movie = Movie.query.get_or_404(movie_id)
        # Get list of selected genre IDs from the form. Use getlist for multi-select.
        selected_genre_ids = request.form.getlist("genre_ids")

        # Limit to a maximum of 4 genres
        if len(selected_genre_ids) > 4:
            flash("You can select a maximum of 4 genres.", "warning")
            return redirect(url_for("movie_detail", movie_id=movie_id))

        try:
            # Fetch the Genre objects corresponding to the selected IDs
            selected_genres = Genre.query.filter(Genre.id.in_(selected_genre_ids)).all()

            # Update the movie's genres relationship
            movie.genres = selected_genres

            db.session.commit()
            flash("Movie genres updated successfully!", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating genres: {str(e)}", "danger")

        return redirect(url_for("movie_detail", movie_id=movie_id))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(port=5001, debug=True)
