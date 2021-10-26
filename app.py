import os
from flask import (
    Flask, flash, render_template,
    redirect, request, session, url_for)
from flask_pymongo import PyMongo
from bson.objectid import ObjectId  # to render an object id in a bson format
if os.path.exists("env.py"):
    import env
    from werkzeug.security import generate_password_hash, check_password_hash


# create an instance of Flask called app
app = Flask(__name__)

# retieving the hidden env variable for use in the app
app.config["MONGO_DB"] = os.environ.get("MONGO_DB")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

# create instance of pymongo using contructor with app
mongo = PyMongo(app)


@app.route("/")
@app.route("/home", methods=["GET", "POST"])
def home():
    return render_template("home.html")

@app.route("/get_all_genre")
def get_all_genre():
    genre_list = mongo.db.genre.find()
    return render_template("genre-management.html", genre_list=genre_list)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        requested_username = request.form.get("username")
        existing_user = mongo.db.users.find_one(
            {"username": requested_username.lower()}
        )

        if existing_user:
            flash("Username ${requested_username.capitalize()} already exists")
            return redirect(url_for("signup"))

        register = {
            "username": request.form.get("username").lower(),
            "password": generate_password_hash(request.form.get("password")),
            "firstname": request.form.get("firstname").lower(),
            "lastname": request.form.get("lastname").lower(),
            "dob": request.form.get("dob"),
            "email": request.form.get('email'),
            "favourite-genre": request.form.getlist('favourite-genre')
        }
        mongo.db.users.insert_one(register)

        # put the user into session
        session['user'] = request.form.get("username").lower()
        flash("Registration Successful ${session['user]}!")
    genre_list = mongo.db.genre.find()
    return render_template("signup.html", genre_list=genre_list)


@app.route("/signin")
def signin():
    return render_template("signin.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    return render_template("contact.html")


# application running instructions by retieving hidden env variables
if __name__ == "__main__":
    # retrieve the hidden env values and set them in variables
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)  # this only used in development to debug
