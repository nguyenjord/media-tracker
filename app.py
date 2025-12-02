# Author: Jordan Nguyen
# Date: 10/28/2025 - 12/1/2025

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from secret import OMDB_API_KEY
import json, os, requests, zmq

app = Flask(__name__)
DATA_FILE = "data/items.json"
app.secret_key = os.urandom(24) # flask secure session

## zeromq
# user authentication (small pool)
auth_context = zmq.Context()
auth_socket = auth_context.socket(zmq.REQ)
auth_socket.connect("tcp://localhost:5555") 

# calender (big pool)
calender_context = zmq.Context()
calender_socket = calender_context.socket(zmq.REQ)
calender_socket.connect("tcp://localhost:5551") 

# time (big pool)
clock_context = zmq.Context()
clock_socket = clock_context.socket(zmq.REQ)
clock_socket.connect("tcp://localhost:5556") 

# counter (big pool)
counter_context = zmq.Context()
counter_socket = counter_context.socket(zmq.REQ)
counter_socket.connect("tcp://localhost:5558")


## helper funcs
def load_items(): # loads items from json file (items.json)
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_items(items): # saves items to json file (items.json)
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=2)

## microservice funcs
@app.route("/login", methods=["GET", "POST"]) 
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        request_data = {
            "action": "login",
            "username": username,
            "password": password
        }

        auth_socket.send_string(json.dumps(request_data))

        reply_json = auth_socket.recv_string()
        reply = json.loads(reply_json)

        if reply.get("status") == "ok":
            session["username"] = username
            session["session_id"] = reply.get("session_id")

            current_time = get_current_time()
            flash(f"Welcome, {username}. Logged in at {current_time}", "success")

            return redirect(url_for("home"))
        else:
            flash(reply.get("message", "Login failed"), "error")
            return redirect(url_for("login"))
        
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"]) 
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()

        if not username or not password or not confirm:
            return render_template("register.html", error = "All fields must be filled.")
        
        if password != confirm:
            return render_template("register.html", error = "Passwords do not match.")
        
        request_data = {
            "action": "register",
            "username": username,
            "password": password
        }

        auth_socket.send_string(json.dumps(request_data))
        reply_json = auth_socket.recv_string()
        reply = json.loads(reply_json)

        if reply.get("status") == "ok":
            return redirect(url_for("login"))
        else:
            return render_template("register.html", error = "Registration failed.")
        
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


def get_current_date():
    request_data = {"format": "YYYY-MM-DD"}
    calender_socket.send_json(request_data)
    date = calender_socket.recv_string()
    return date

def get_current_time():
    request_data = {"action": "get_time", "format": "12"}
    clock_socket.send_string(json.dumps(request_data))
    reply_json = clock_socket.recv_string()
    reply = json.loads(reply_json)
    
    return reply.get("time")

def item_counter():
    request_data = {"action": "counter", "counter_name": "total_items"}
    counter_socket.send_string(json.dumps(request_data))
    reply = json.loads(counter_socket.recv_string())
    
    if reply.get("status") == "ok":
        return reply.get("count")
    
def get_item_count():
    request_data = {"action": "get", "counter_name": "total_items"}
    counter_socket.send_string(json.dumps(request_data))
    reply = json.loads(counter_socket.recv_string())

    if reply.get("status") == "ok":
        return reply.get("count")
    
def reset_count():
    request_data = {"action": "reset", "counter_name": "total_items"}
    counter_socket.send_string(json.dumps(request_data))
    reply = json.loads(counter_socket.recv_string())

    return reply.get("status") == "ok"

## pages
# help page
@app.route("/help") 
def help_page():
    return render_template("help.html")

# home page
@app.route("/")
def home():
    if "username" not in session:
        return redirect(url_for("login"))

    items = load_items()
    query = request.args.get("q", "").lower()
    if query:
        # add movie i to list if title contains string
        items = [i for i in items if query in i["title"].lower()] 

    total_count = get_item_count()
    
    return render_template("home.html", items=items, total_count=total_count)

## add page

# add via omdb
@app.route("/add_omdb", methods=["GET", "POST"]) 
def add_omdb():
    if request.method == "POST": # checks if form was submitted
        title = request.form.get("title")
        if not title:
            return render_template("add_omdb.html", error="Please enter a movie title")

        params = {"t": title, "apikey": OMDB_API_KEY, "plot": "short", "r": "json"} # t = title, plot: short = short summary, r:json = response in json
        response = requests.get("http://www.omdbapi.com/", params=params)
        movie = response.json()

        if movie.get("Response") == "False":
            return render_template("add_omdb.html", error=f"Movie '{title}' not found.")

        runtime_str = movie.get("Runtime", "0 min")
    
        if runtime_str != "N/A":
            runtime = int(runtime_str.split()[0])
        else:
            runtime = 0

        
        # add to collection
        if request.form.get("action") == "add":
            items = load_items()
            new_item = { # movie details
                "id": len(items) + 1,
                "title": movie["Title"],
                "type": movie.get("Type", "Movie"),
                "year": movie.get("Year"),
                "poster": movie.get("Poster"),
                "status": "Want to Watch",
                "runtime": runtime, 
                "progress": 0,
                "date_added": get_current_date()
            }
            items.append(new_item)
            save_items(items)

            item_counter()

            return redirect(url_for("home"))
        
        return render_template("add_omdb.html",movie=movie)

    return render_template("add_omdb.html",movie=None)


# add manually
@app.route("/add_manual", methods=["GET", "POST"])
def add_manual():
    if request.method == "POST":
        title = request.form.get("title")
        movie_type = request.form.get("type")
        year = request.form.get("year")
        runtime = request.form.get("runtime")
        poster = request.form.get("poster") or None

        if not title:
            return render_template("add_manual.html", error="Title is required.")

        if runtime:
            runtime_value = int(runtime)
        else:
            runtime_value = 0

        items = load_items()
        new_item = {
            "id": len(items) + 1,
            "title": title,
            "type": movie_type,
            "year": year ,
            "poster": poster,
            "status": "Want to Watch",
            "runtime": runtime_value,
            "progress": 0,
            "date_added": get_current_date()
        }
        items.append(new_item)
        save_items(items)
        
        item_counter()

        return redirect(url_for("home"))
    
    return render_template("add_manual.html")

# update function
@app.route("/update_progress/<int:item_id>", methods=["POST"])
def update_progress(item_id):
    items = load_items()
    for item in items:
        if item["id"] == item_id:
            progress_str = request.form.get("progress", "0")
            try:
                progress_value = int(progress_str) # converts to int, 0 if invalid
            except ValueError:
                progress_value = 0

            item["progress"] = progress_value

            break
    save_items(items)
    return redirect(url_for("home"))

# remove function
@app.route("/remove_movie/<int:item_id>", methods=["POST"])
def remove_movie(item_id):
    items = load_items()

    new_items = []

    for item in items:
        if item["id"] != item_id:
            new_items.append(item)

    if len(new_items) < len(items):
        reset_count()
        for _ in new_items:
            item_counter()

    save_items(new_items)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)