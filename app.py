# Author: Jordan Nguyen
# Date: 10/28/2025

from flask import Flask, render_template, request, redirect, url_for, jsonify
from secret import OMDB_API_KEY
import json, os, requests

app = Flask(__name__)
DATA_FILE = "data/items.json"

# helpers (future ref: used https://www.geeksforgeeks.org/python/reading-and-writing-json-to-a-file-in-python/ and stackoverflow)
def load_items(): # loads items from json file (items.json)
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_items(items): # saves items to json file (items.json)
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=2)

# flask routes

# help page (future ref: flask uses routes instead of mapping to different pages via html)
@app.route("/help") 
def help_page():
    return render_template("help.html")

# home page
@app.route("/")
def home():
    items = load_items()
    query = request.args.get("q", "").lower()
    if query:
        # add movie i to list if title contains string
        items = [i for i in items if query in i["title"].lower()] 
    return render_template("home.html", items=items)

# add page

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
                "progress": 0
            }
            items.append(new_item)
            save_items(items)
            return redirect(url_for("home"))

        return render_template("add_omdb.html", movie=movie)

    return render_template("add_omdb.html")


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
            "progress": 0
        }
        items.append(new_item)
        save_items(items)

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

    save_items(new_items)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)