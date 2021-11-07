import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId  # to render an object id in a bson format
if os.path.exists("env.py"):
    import env


# create an instance of Flask called app
app = Flask(__name__)

# retieving the hidden env variable for use in the app
app.config["MONGO_DB"] = os.environ.get("MONGO_DB")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

# create instance of pymongo using contructor with app
mongo = PyMongo(app)


# Functions
def is_admin():
    if session and session["user"] and session["is_superuser"] == "True":
        return True
    else:
        flash(f"You need to be an Administrator to access that! \nPlease sign"
              f"into your Admin account and try again")
        return redirect(url_for('home'))


def is_logged_in():
    if session and session["user"]:
        return True
    else:
        flash(f"You need to be signed in to access that! \n"
              f"Please create an account or sign in and try again")
        return redirect(url_for('signin'))


def create_single_review():
    review = {
        "reviewer": session['user'],
        "review_title": request.form.get("review-title").lower(),
        "review": request.form.get("movie-review"),
        "review_date": datetime.now(),
        "star_rating": int(request.form.get("star-count"))
    }
    return review


def mongo_prefix_select(collection_name):
    search_prefix = {
        "users": mongo.db.users,
        "movies": mongo.db.movies,
        "genre": mongo.db.genre
    }
    mongo_prefix = search_prefix[collection_name]
    return mongo_prefix


def find_one_with_key(collection_name, search_key, search_value):
    movie = mongo_prefix_select(collection_name).find_one(
        {search_key: search_value})
    return movie


def update_collection_item_dict(collection_name, search_key, search_value,
                                update_operator, array_to_update,
                                array_search_key, array_search_value):
    mongo_prefix_select(collection_name).update_one(
        {search_key: search_value},
        {update_operator: {array_to_update:
                           {array_search_key: array_search_value}}})


def update_collection_item(collection_name, search_key, search_value,
                           update_operator, new_key, new_value):
    mongo_prefix_select(collection_name).update_one(
        {search_key: search_value},
        {update_operator: {new_key: new_value}})


def delete_collection_item(collection_name, search_key, search_value):
    mongo_prefix_select(collection_name).delete_one({search_key: search_value})


def add_collection_item(collection_name, search_key, search_value):
    mongo_prefix_select(collection_name).insert_one({search_key: search_value})


def generate_average_review_score(movie_id):
    movie = find_one_with_key("movies", "_id", movie_id)
    # generate an average reviews score
    total_review_score = 0
    # add all the review scores together from the data pulled from
    # the DB
    for review in movie["reviews"]:
        total_review_score += int(review["star_rating"])
    # divide the result by the amount of old scores plus 1 for the
    # score just added
    new_average_review_score = round(total_review_score/(len(
                                    movie["reviews"])), 2)
    # set the variable in the DB to the new value
    mongo.db.movies.update_one({"_id": ObjectId(
                                movie["_id"])},
                               {"$set": {"average_review_score":
                                         new_average_review_score}})


def convert_string_to_datetime(string_date):
    datetime_date = datetime.strptime(
        string_date, '%Y-%m-%d %H:%M:%S.%f')
    return datetime_date


def add_review_to_latest_reviews_dicts(movie, new_review_dict):
    user = find_one_with_key("users", "_id", ObjectId(session["id"]))

    arrays_to_add_review_to = [user["user_latest_reviews"],
                               movie["latest_reviews"]]

    for array in arrays_to_add_review_to:
        if len(array) > 2:
            array[0:2]
        array.append(new_review_dict)

    update_collection_item("users", '_id', ObjectId(session['id']), "$set",
                           "user_latest_reviews", arrays_to_add_review_to[0])
    update_collection_item("movies", '_id', ObjectId(movie['_id']), "$set",
                           "latest_reviews", arrays_to_add_review_to[1])

def consolidate_matching_array_dicts(list_1, list_2):
    """
    function to compare 2 lists matching values under append any matching dicts to a new list.
    """
    print(list_1, list_2)
    new_list = set(list_1).intersection(list_2)
    print(new_list)
    return new_list

# app.route
@app.route("/")
@app.route("/home")
def home():
    movies = list(mongo.db.movies.find({}, {"movie_title": 1,
                                            "average_rating": 1,
                                            "release_date": 1,
                                            "genre": 1,
                                            "image_link": 1}))
    # sorted alphabeticallly by title with max of 15
    all_movies = sorted(movies, key=lambda d: d['movie_title'])[:15]
    # sorted by average rating by title with max of 15
    highest_rated = sorted(movies, key=lambda d: d['average_rating'], reverse=True)[:15]
    # sorted by release date by title with max of 15
    latest_releases = sorted(movies, key=lambda d: d['release_date'], reverse=True)[:15]

    if session and session["user"]:
        user = find_one_with_key("users", "_id", ObjectId(session["id"]))
        # generate suggested_movies list
        suggested_movies = []
        for item in movies:
            if set(user["favourite_genres"]).intersection(item["genre"]):
                suggested_movies.append(item)
        movies_for_you = sorted(suggested_movies, key=lambda d: d[
                                'average_rating'])[:15]
        # generate want_to_watch list
        want_to_watch = []
        for item in user["movies_to_watch"]:
            for movie in movies:
                if movie["movie_title"] == item:
                    want_to_watch.append(movie)
        want_to_watch = sorted(want_to_watch, key=lambda d: d[
                                'average_rating'])[:15]

    return render_template("home.html", all_movies=all_movies,
                            highest_rated=highest_rated,
                            latest_releases=latest_releases,
                            movies_for_you=movies_for_you,
                            want_to_watch=want_to_watch)


@app.route("/movie-title-search", methods=["GET", "POST"])
def movie_title_search():
    query = request.form.get("movie_title_search")
    searched_movies = list(mongo.db.movies.find({"$text": {"$search": query}}))
    return render_template("movie-search.html", movies=searched_movies)


@app.route("/genre")
def get_all_genre():
    genre_list = list(mongo.db.genre.find())
    return render_template("genre-management.html", genre_list=genre_list)


@app.route("/genre/add", methods=["POST"])
def add_genre():
    new_genre_name = request.form.get('genre-name')
    mongo.db.genre.insert_one({
        "genre_name": new_genre_name.lower()
    })
    flash("Genre " + new_genre_name.title() + " added!")
    return redirect(url_for('get_all_genre'))


@app.route("/genre/delete/<genre_id>")
def delete_genre(genre_id):
    mongo.db.genre.remove({
        "_id": ObjectId(genre_id)
    })
    flash("Genre Deleted")
    return redirect(url_for('get_all_genre'))


def add_data_user_data_to_session_storage(user_dict, new_id=None):
    if new_id is None:
        session["id"] = str(user_dict['_id'])
    else:
        session["id"] = str(new_id)
    session['user'] = user_dict['username']
    session['email'] = user_dict['email']
    session['full-name'] = user_dict[
        'firstname'] + " " + user_dict['lastname']


@app.route("/genre/update/<genre_name>,<genre_id>", methods=["POST"])
def update_genre(genre_id, genre_name):
    """
    function to update a genre name in the DB
    """
    # store input data in a variable using the genre_name to make up the input
    # name value and removing any spaces
    new_genre_name = request.form.get(genre_name.replace(
                                        " ", "-") + '-replacement-genre-name')
    # updating the informatiion in the DB using the _id to find the documnet
    mongo.db.genre.update({"_id": ObjectId(genre_id)}, {
                                "genre_name": new_genre_name.lower()})
    flash("Genre Updated")
    return redirect(url_for('get_all_genre'))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        requested_username = request.form.get("username")
        existing_user = mongo.db.users.find_one(
            {"username": requested_username.lower()}
        )

        if existing_user:
            flash("Username " + requested_username.capitalize() +
                  " already exists")
            return redirect(url_for("signup"))

        register = {
            "username": request.form.get("username").lower(),
            "password": generate_password_hash(request.form.get("password")),
            "firstname": request.form.get("firstname").lower(),
            "lastname": request.form.get("lastname").lower(),
            "dob": request.form.get("dob"),
            "email": request.form.get('email'),
            "favourite_genres": request.form.getlist('favourite-genre'),
            "date_joined":  datetime.now(),
            # unfilled fields
            "movies_reviewed": [],
            "movies_watched": [],
            "movies_to_watch": [],
            "user_latest_reviews": [],
        }

        new_id = mongo.db.users.insert_one(register).inserted_id
        add_data_user_data_to_session_storage(register, new_id)

        # put the user into session and load profile page
        flash("Registration Successful " + session["user"].capitalize() + "!")
        return redirect(url_for('profile', username=session['user']))

    genre_list = mongo.db.genre.find()
    return render_template("signup.html", genre_list=genre_list)


@app.route("/profile/<user_id>/edit", methods=["GET", "POST"])
def edit_user_profile(user_id):
    if request.method == "POST":
        user = mongo.db.users.find_one({"_id": ObjectId(session['id'])},
                                       {"password": 0})

        requested_username = request.form.get("username").lower()
        existing_user = mongo.db.users.find_one(
            {"username": requested_username.lower()},
            {"password": 0})

        if existing_user and existing_user["username"] != user["username"]:
            flash("Username " + requested_username.capitalize() +
                  " already exists")
            return redirect(url_for("edit_user_profile",
                                    user_id=session['id']))

        updated_profile_dict = {
            "username": request.form.get("username").lower(),
            "firstname": request.form.get("firstname").lower(),
            "lastname": request.form.get("lastname").lower(),
            "dob": request.form.get("dob"),
            "email": request.form.get('email'),
            "favourite_genres": request.form.getlist('movie-genre')
        }

        mongo.db.users.update_one({"_id": ObjectId(session['id'])},
                                  {"$set": updated_profile_dict})
        
        add_data_user_data_to_session_storage(updated_profile_dict,
                                              ObjectId(session["id"]))

        flash(f"Successfully Updated {session['user'].capitalize()} Account!")
        return redirect(url_for('profile', username=session['user']))

    user = find_one_with_key("users", "_id", ObjectId(user_id))
    user["dob"] = datetime.strptime(user["dob"], '%Y-%m-%d')

    genre_list = mongo.db.genre.find()
    genre_list = sorted(genre_list, key=lambda d: d['genre_name'])
    for genre in genre_list:
        if genre["genre_name"].lower() in user["favourite_genres"]:
            genre["checked"] = True
    return render_template("edit-user-profile.html", genre_list=genre_list,
                           user=user)


@app.route("/profile/<user_id>/delete")
def delete_user_profile(user_id):
    mongo.db.users.remove({
        "_id": ObjectId(user_id)
    })
    username = session["user"].title()
    session.clear()
    flash(f"User Profile {username} Deleted")
    return redirect(url_for('home'))


@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        # check if username is on the BD
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()}
        )
        if existing_user:
            if check_password_hash(existing_user["password"],
                                   request.form.get("password")):

                add_data_user_data_to_session_storage(existing_user)

                flash("Welcome " + session["user"].capitalize())

                return redirect(url_for('profile', username=session['user']))
            else:
                flash("The information entered is incorrect")
                return redirect(url_for('signin'))

        else:
            flash("The information entered is incorrect")
            return redirect(url_for('signin'))

    return render_template("signin.html")


@app.route("/signout")
def signout():
    flash("You have signed out")
    session.clear()
    movie_list = mongo.db.movies.find()
    return render_template("home.html", movies=movie_list)


@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    user = mongo.db.users.find_one(
            {"username": username},
            {"password": 0})

    # generate suggested_movies list
    suggested_movies = []
    movies = list(mongo.db.movies.find())
    for item in movies:
        if set(user["favourite_genres"]).intersection(item["genre"]):
            suggested_movies.append(item)

    user_latest_reviews = sorted(user["user_latest_reviews"], key=lambda d: d[
                          'review_date'], reverse=True)

    return render_template("profile.html", user=user,
                           suggested_movies=suggested_movies,
                           user_latest_reviews=user_latest_reviews)


def generate_movie_image_link():
    if request.form.get("image-link"):
        image_link = request.form.get("image-link")
    else:
        image_link = "../static/img/movie-placeholder.png"
    return image_link


def add_series_information_to_dict(new_movie):
    if request.form.get("submit-series-info"):
        new_movie["is_part_of_series"] = True
        new_movie["series_position"] = request.form.get(
                                            "series-checkboxes")
        new_movie["series_name"] = request.form.get("series-name").lower()
        if new_movie["series_position"] == "start":
            new_movie["next_movie_title"] = request.form.get(
                                        "next-movie-name").lower()
        elif new_movie["series_position"] == "end":
            new_movie["previous_movie_title"] = request.form.get(
                                            "previous-movie-name").lower()
        else:
            new_movie["previous_movie_title"] = request.form.get(
                                            "previous-movie-name").lower()
            new_movie["next_movie_title"] = request.form.get(
                                        "next-movie-name").lower()


def add_review_to_dict(new_movie):
    if request.form.get("submit-movie-review"):
        review = create_single_review()
        review["review_for"] = new_movie["movie_title"]
        new_movie["reviews"].append(review)
        new_movie["latest_reviews"].append(review)
        new_movie["average_rating"] = review["star_rating"]


def generate_new_movie_dict():
    image_link = generate_movie_image_link()
    new_movie = {
            "movie_title": request.form.get("movie-title").lower(),
            "release_date": datetime.strptime(request.form.get(
                                              "release-date"), '%Y-%m-%d'),
            "age_rating": request.form.get("age-rating"),
            "duration": request.form.get("duration"),
            "genre": request.form.getlist("movie-genre"),
            "director": request.form.get("director").lower(),
            "cast_members": request.form.get("cast-members").lower(
                            ).split(","),
            "movie_synopsis": request.form.get("movie-synopsis"),
            "movie_description": request.form.get("movie-description"),
            "image_link": image_link,
            "reviews": [],
            "latest_reviews": [],
            "created_by": session['user'],
            "is_part_of_series": False,
            "average_rating": 0.0
        }
    add_series_information_to_dict(new_movie)
    add_review_to_dict(new_movie)
    return new_movie


@app.route("/create-movie", methods=["GET", "POST"])
def create_movie():
    if request.method == "POST":
        new_movie = generate_new_movie_dict()
        new_id = mongo.db.movies.insert_one(new_movie).inserted_id

        if request.form.get("seen-movie-checkbox"):
            update_collection_item("users", "username", session["user"],
                                   "$push", "movies_watched",  new_id)
        if request.form.get("submit-movie-review"):
            update_collection_item("users", "username", session["user"],
                                   "$push", "movies_reviewed", new_id)

        update_collection_item("users", '_id', ObjectId(session['id']), "$set",
                               "user_latest_reviews", new_movie[
                                   "latest_reviews"])

        flash("New Movie Added")
        return redirect(url_for("view_movie", movie_id=new_id))

    genre_list = mongo.db.genre.find()
    return render_template("create-movie.html", genre_list=genre_list)


@app.route("/edit-movie/<movie_id>", methods=["GET", "POST"])
def edit_movie(movie_id):
    if request.method == "POST":
        updated_movie = generate_new_movie_dict()
        mongo.db.movies.update({"_id": ObjectId(movie_id)}, updated_movie)
        if request.form.get("submit-movie-review"):
            update_collection_item("users", "username", session["user"],
                                   "$push", "movies_reviewed", movie_id)

        flash("Movie Profile Successfully Updated")
        return redirect(url_for("view_movie", movie_id=movie_id))

    movie = find_one_with_key("movies", "_id", ObjectId(movie_id))
    genre_list = list(mongo.db.genre.find().sort("genre_name"))
    age_ratings = mongo.db.uk_age_ratings.find().sort("uk_rating_order")
    for genre in genre_list:
        if genre["genre_name"].lower() in movie["genre"]:
            genre["checked"] = True
    # make into function - list from array of dicts with key
    movie_reviewers = []
    for review in movie["reviews"]:
        movie_reviewers.append(review["reviewer"])

    cast_members_string = ', '.join(name.title() for name in movie["cast_members"])
    return render_template("edit-movie.html", genre_list=genre_list,
                           movie=movie, age_ratings=age_ratings,
                           cast_members_string=cast_members_string,
                           movie_reviewers=movie_reviewers)


@app.route("/movie/<movie_id>/delete")
def delete_movie(movie_id):
    mongo.db.movies.remove({
        "_id": ObjectId(movie_id)
    })
    flash("Movie Deleted")
    return redirect(url_for('home'))


@app.route("/view-movie/<movie_id>")
def view_movie(movie_id):
    movie = mongo.db.movies.find_one(
            {'_id': ObjectId(movie_id)})

    user_want_to_watch = False
    user_watched = False

    if session["user"] is not None:
        user = mongo.db.users.find_one(
            {"username": session["user"]},
            {"_id": 0, "movies_watched": 1, "movies_to_watch": 1}
        )

        if movie["_id"] in user["movies_watched"]:
            user_watched = True

        if movie["_id"] in user["movies_to_watch"]:
            user_want_to_watch = True

    # generate similar_movies list
    similar_movies = []
    movies = list(mongo.db.movies.find())
    for item in movies:
        if set(movie["genre"]).intersection(item["genre"]):
            similar_movies.append(item)

    movie__genre_text_list = ', '.join(name.title() for name in movie["genre"])
    movie["genre"] = movie__genre_text_list
    latest_reviews = sorted(movie["latest_reviews"], key=lambda d: d['review_date'], reverse=True)
    list(movie)
    return render_template("view-movie.html", movie=movie,
                           user_watched=user_watched,
                           user_want_to_watch=user_want_to_watch,
                           similar_movies=similar_movies,
                           latest_reviews=latest_reviews)


@app.route("/create-review", defaults={'selected_movie_title': None},
           methods=["GET", "POST"])
@app.route("/create-review/<selected_movie_title>", methods=["GET", "POST"])
def create_review(selected_movie_title):
    if request.method == "POST":
        requested_movie_name = request.form.get("selected-movie-title").lower()
        movie = mongo.db.movies.find_one({
                                "movie_title": requested_movie_name})
        if movie:
            new_review = create_single_review()
            new_review["review_for"] = movie["movie_title"]
            mongo.db.movies.update_one({"_id": ObjectId(
                                        movie["_id"])},
                                       {"$push": {"reviews": new_review}})

            generate_average_review_score(ObjectId(movie["_id"]))

            add_review_to_latest_reviews_dicts(movie, new_review)

            return redirect(url_for('view_reviews', movie_id=movie["_id"]))

        else:
            flash(f"There is no movie called '{requested_movie_name.title()}' "
                  f"in the database.\nEither create a profile for this movie "
                  f"or try a different Movie Title")
        return redirect(url_for('create_review'))

    movie_title_list = mongo.db.movies.find({}, {"movie_title": 1})
    return render_template(
        "create-review.html", movie_title_list=movie_title_list,
        selected_movie_title=selected_movie_title)


@app.route("/review/<movie_id>/<review_date>/edit", methods=["GET", "POST"])
def edit_review(movie_id, review_date):
    if request.method == "POST":
        movie = find_one_with_key("movies", "_id", movie_id)

        updated_review = create_single_review()
        updated_review["review_for"] = movie["movie_title"].lower

        update_collection_item_dict("movies", "_id", ObjectId(movie_id),
                                    "$pull", "reviews", "review_date",
                                    convert_string_to_datetime(review_date))
        mongo.db.movies.update_one({"_id": ObjectId(movie_id)},
                                   {"$push": {"reviews": updated_review,
                                              "latest_reviews":
                                              updated_review}})

        add_review_to_latest_reviews_dicts(movie, updated_review)

        return redirect(url_for('view_reviews', movie_id=movie_id))

    movie = find_one_with_key("movies", "_id", ObjectId(movie_id))
    movie_review = [review for review in movie["reviews"]
                    if review["review_date"] ==
                    convert_string_to_datetime(review_date)][0]
    movie_title_list = mongo.db.movies.find({}, {"movie_title": 1})
    return render_template(
        "edit-review.html", movie_title_list=movie_title_list,
        selected_movie=movie, movie_review=movie_review)


@app.route("/view-reviews/<movie_id>")
def view_reviews(movie_id):
    movie = find_one_with_key("movies", "_id", ObjectId(movie_id))
    list(movie)
    return render_template("view-reviews.html", movie=movie)


@app.route("/delete-review/<movie_id>/<review_date>")
def delete_review(movie_id, review_date):
    update_collection_item_dict("movies", "_id", ObjectId(movie_id),
                                "$pull", "reviews", "review_date",
                                convert_string_to_datetime(review_date))

    update_collection_item_dict("movies", "_id", ObjectId(movie_id),
                                "$pull", "latest_reviews", "review_date",
                                convert_string_to_datetime(review_date))

    update_collection_item_dict("users", "_id", ObjectId(session['id']),
                                "$pull", "user_latest_reviews", "review_date",
                                convert_string_to_datetime(review_date))

    flash("Review deleted")
    movie = find_one_with_key("movies", "_id", ObjectId(movie_id))
    generate_average_review_score(ObjectId(movie["_id"]))
    list(movie)
    return redirect(url_for('view_reviews', movie_id=movie["_id"]))


@app.route("/user/add-watched-movie/<movie_id>")
def add_watched_movie(movie_id):
    update_collection_item("users", "username", session["user"], "$push",
                           "movies_watched", ObjectId(movie_id))
    return redirect(url_for("view_movie", movie_id=movie_id))


@app.route("/user/remove-watched-movie/<movie_id>")
def remove_watched_movie(movie_id):
    mongo_prefix_select("users").update_one(
            {"username": session["user"]},
            {"$pull": {"movies_watched": ObjectId(movie_id)}})
    return redirect(url_for("view_movie", movie_id=movie_id))


@app.route("/user/add-want-to-watch-movie/<movie_id>")
def add_want_to_watch_movie(movie_id):
    update_collection_item("users", "username", session["user"], "$push",
                           "movies_to_watch", ObjectId(movie_id))
    return redirect(url_for("view_movie", movie_id=movie_id))


@app.route("/user/remove-want-to-watch-movie/<movie_id>")
def remove_want_to_watch_movie(movie_id):
    mongo_prefix_select("users").update_one(
            {"username": session["user"]},
            {"$pull": {"movies_to_watch": ObjectId(movie_id)}})
    return redirect(url_for("view_movie", movie_id=movie_id))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        mongo.db.messages.insert_one({
            "sender_name": request.form.get("full-name"),
            "sender_email": request.form.get("email"),
            "message": request.form.get("message"),
            "datetime_sent": datetime.now()
        })
        flash("Message Sent Successfully!")

    return render_template("contact.html")


# application running instructions by retieving hidden env variables
if __name__ == "__main__":
    # retrieve the hidden env values and set them in variables
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)  # this only used in development to debug
