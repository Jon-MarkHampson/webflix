# WEBFLIX 🎬

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/) [![Flask](https://img.shields.io/badge/flask-v2.0+-blue.svg)](https://flask.palletsprojects.com/)

**WEBFLIX** is a modern Flask web application for managing users and movies—think Netflix meets your personal movie tracker. With OMDb API integration, Cloudinary image uploads, genre management, and a responsive UI, WEBFLIX is perfect for demos, learning, or as a foundation for your own project!

---

## 🚀 Features

* **User Management**

  * Create, edit, and delete users with profile pictures (via Cloudinary)
  * Session-based user switching
* **Movie Collection**

  * Search movies by title using the [OMDb API](https://www.omdbapi.com/)
  * Add movies to the global database or attach them to a user’s personal list
  * Mark movies as watched/unwatched
  * Remove movies from user lists or from the global collection
* **Genres**

  * Predefined genre seeding with CLI command
  * Assign up to 4 genres per movie
  * Filter and sort movies by genre, title, release date, or rating
* **Modern UI**

  * Responsive Jinja2 templates
  * Flash messages for real-time feedback
* **Database**

  * SQLite by default (easily switch to PostgreSQL/MySQL)
  * SQLAlchemy ORM models
* **Image Hosting**

  * User profile images stored on Cloudinary
* **Config & Secrets**

  * `.env` file support (via `python-dotenv`) for API keys and secrets

---

## 🛠️ Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/webflix.git
   cd webflix
   ```

2. **Create & activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file in the project root:

   ```ini
   SECRET_KEY=your_flask_secret_key
   OMDB_API_KEY=your_omdb_api_key
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_cloudinary_key
   CLOUDINARY_API_SECRET=your_cloudinary_secret
   ```

5. **Initialize the database**

   ```bash
   flask --app app.py init-db
   flask --app app.py seed-genres
   ```

6. **Run the application**

   ```bash
   flask --app app.py run --port 5001
   ```

   Then visit [http://localhost:5001](http://localhost:5001) in your browser.

---

## 🗂️ Project Structure

```
webflix/
├── app.py              # Flask application factory and routes
├── models.py           # SQLAlchemy models
├── api/                # REST API blueprint
├── templates/          # Jinja2 HTML templates
├── static/             # CSS
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not committed)
└── webflix.db          # SQLite database (auto-generated)
```

---

## 📖 Usage

* **Add Users**: Go to `/add_user_form` to create or edit users, including profile images.
* **Switch User**: Click a user to set them as the active session.
* **Search Movies**: Navigate to `/add-movie-search` to find and add movies via OMDb.
* **Mark Watched**: Toggle the watched status on your personal movie list.
* **Filter & Sort**: Use dropdowns on `/all-movies` or `/my-movies` to filter by genre and sort by title, year, or rating.
* **Genre Management**: Edit up to 4 genres per movie on its detail page.
* **CLI Commands**:

  * `flask --app app.py init-db`: Reset and initialize the database
  * `flask --app app.py seed-genres`: Populate predefined genres

---

## 🛡️ Security & Best Practices

* **Keep your `.env` file out of version control!**
* For production, consider:

  * Adding user authentication (Flask-Login)
  * Enabling CSRF protection (Flask-WTF)
  * Deploying with a production-ready database (PostgreSQL/MySQL)
  * Serving static assets via a CDN
  * Configuring HTTPS and secure cookies

---

## 🤝 Contributing

Contributions are welcome! Please fork the repository, make your changes, and open a pull request.

---

## 📜 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

📺 **Live Demo:** [https://jonmark.eu.pythonanywhere.com/](https://jonmark.eu.pythonanywhere.com/)
🍿 Enjoy your personal WEBFLIX!
