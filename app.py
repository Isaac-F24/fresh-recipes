import os
import flask
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
import datetime
import random

# Setup

app = flask.Flask(__name__, template_folder="html")
app.secret_key = "key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.root_path, "databaseFiles", "recipes.db")

database = SQLAlchemy(app)

# /////////////////
#     Pages
# /////////////////

@app.route('/')
def home_page():
    """
    Select at most 15 random recipes to display on the main page.
    """

    logged_in = False
    if "logged_in_user" in flask.session:
        logged_in = True

    max_id_statement = database.select(Recipe).order_by(Recipe.id.desc())
    highest_entry = database.session.execute(max_id_statement).first()
    if highest_entry is None:
        return flask.render_template("home.html", logged_in=logged_in, results=None)
    
    max_id = highest_entry[0].id

    max_num = min(15, max_id+1)

    recipes = []
    seen = set()
    for i in range(max_num):

        # find a random id that we haven't seen yet
        random_id = random.randint(0, max_id)
        while random_id in seen:
            random_id = random.randint(0, max_id)
        seen.add(random_id)

        # add the recipe
        statement = database.select(Recipe).where(Recipe.id == random_id)
        result = database.session.execute(statement).first()
        if result is None:
            continue

        recipes.append(result[0])

    return flask.render_template("home.html", logged_in=logged_in, results=recipes)

@app.route('/login', methods=["GET", "POST"])
def login_page():
    """
    Show the login page if the user is not logged in.
    For POST, check the email and password and log the user in if they are correct.
    """

    if flask.request.method == "POST":

        email = flask.request.form.get("email")
        password = flask.request.form.get("password")

        statement = database.select(User).where(User.email == email)
        result = database.session.execute(statement).first()
        if result is None:
            return flask.render_template("login_page.html", error="Email not found.")
        
        result = result[0]  # access the user
        
        if result.password != password:
            return flask.render_template("login_page.html", error="Incorrect password.")
        
        flask.session["logged_in_user"] = email

        flask.flash("Logged in successfully.")
        return flask.redirect("/")
    
    else:

        if "logged_in_user" in flask.session:
            return flask.redirect("/")
        
        return flask.render_template("login_page.html")
    

@app.route('/signup', methods=["GET", "POST"])
def sign_up_page():
    """
    Show the sign up page if the user is not logged in.
    For POST, check to make sure the email is unique. Then, create a new user and log them in.
    """

    if flask.request.method == "POST":
        email = flask.request.form.get("email")
        email_confirmation = flask.request.form.get("email_confirm")
        username = flask.request.form.get("username")
        password = flask.request.form.get("password")

        if email != email_confirmation:
            return flask.render_template("signup_page.html", error="Email confirmation does not match.")

        statement = database.select(User).where(User.email == email)
        result = database.session.execute(statement).first()
        if result is not None:
            return flask.render_template("signup_page.html", error="An account already exists with that email.")

        user = User()
        user.email = email
        user.username = username
        user.password = password

        database.session.add(user)
        database.session.commit()

        flask.session["logged_in_user"] = email
        flask.flash("Account created successfully.")
        return flask.redirect("/")


    else:
        if "logged_in_user" in flask.session:
            flask.flash("You are already logged in.")
            return flask.redirect("/")

        return flask.render_template("signup_page.html")

@app.route('/account')
def account():
    """
    Display account information
    """

    if "logged_in_user" not in flask.session:
        return flask.redirect("/login")
    
    email = flask.session["logged_in_user"]

    statement = database.select(User).where(User.email == email)
    result = database.session.execute(statement).first()

    if result is None:
        flask.flash("Account not found.")
        return flask.redirect("/login")
    result = result[0]

    return flask.render_template("account.html", email=email, username=result.username, password=result.password, logged_in=True)

@app.route('/logout')
def logout():
    """
    Remove the currently logged in user from the session and redirect to the home page.
    """

    if "logged_in_user" in flask.session:
        flask.session.pop("logged_in_user")

    flask.flash("You have been logged out.")
    
    return flask.redirect("/")

@app.route('/create_recipe', methods=["GET", "POST"])
def create_recipe():
    """
    Show the create recipe page, a form, if the user is logged in.
    For POST, create a new recipe with all the given information, and
    create a new ingredient for each ingredient in the recipe. Add both to the database.
    """

    if "logged_in_user" not in flask.session:
        flask.flash("You must be logged in to create a recipe.")
        return flask.redirect("/login")
    
    logged_in = True
    
    if flask.request.method == "GET": 
        return flask.render_template("create_recipe.html", logged_in=logged_in)
    
    if flask.request.method == "POST":
        name = flask.request.form.get("name")
        type = flask.request.form.get("type")
        img = flask.request.form.get("image")
        quantities = flask.request.form.getlist("quantities")
        ingredients = flask.request.form.getlist("items")
        method = flask.request.form.get("instructions")

        if (len(quantities) != len(ingredients)):
            flask.flash("Error: Each ingredient must have a quantity.")
            return flask.redirect("/create_recipe")

        # add recipe
        recipe = Recipe()
        recipe.id = None   # auto assigned
        recipe.user_email = flask.session["logged_in_user"]
        recipe.name = name
        recipe.type = type
        recipe.photo = img
        recipe.date_posted = datetime.datetime.now()
        recipe.method = method

        database.session.add(recipe)
        database.session.commit()

        # get the id of the recipe we just added 
        new_id = recipe.id

        # add ingredients
        for i in range(len(ingredients)):
            ingredient = Ingredient()
            ingredient.recipe_id = new_id
            ingredient.name = ingredients[i]
            ingredient.quantity = quantities[i]
            ingredient.order = i
            database.session.add(ingredient)

        database.session.commit()

        flask.flash("Recipe created successfully.")
        return flask.redirect("/recipe/" + str(new_id))

@app.route('/search', methods=["GET", "POST"])
def search():
    """
    Show the advanced search page
    For POST, search the database for recipes that match the given criteria/filters
    """

    if "logged_in_user" in flask.session:
        logged_in = True
    else:
        logged_in = False

    if flask.request.method == "GET":

        return flask.render_template("search.html", logged_in=logged_in, results=None)
    
    if flask.request.method == "POST":
        name = flask.request.form.get("name")
        id = flask.request.form.get("id")
        type = flask.request.form.get("type")
        email = flask.request.form.get("email")
        min_rating = flask.request.form.get("min_rating")
        max_rating = flask.request.form.get("max_rating")
        ingredients = flask.request.form.get("ingredients")
        
        query = {}
        if len(name) != 0:
            query["name"] = name
        if len(id) != 0:
            query["id"] = id
        if len(type) != 0:
            query["type"] = type
        if len(email) != 0:
            query["email"] = email
        if len(min_rating) != 0:
            query["min_rating"] = float(min_rating)
        if len(max_rating) != 0:
            query["max_rating"] = float(max_rating)
        if len(ingredients) != 0:
            query["ingredients"] = ingredients

        recipes = advanced_search(query)
        if len(recipes) == 0:
            recipes = "empty"

        return flask.render_template("search.html", logged_in=logged_in, results=recipes)
    
@app.route('/recipe/<recipe_id>')
def recipe_page(recipe_id):
    """
    Display a recipe with the given id.
    If the user is the owner of the recipe, displays an edit button.
    """

    logged_in = False
    if "logged_in_user" in flask.session:
        logged_in = True

    statement = database.select(Recipe).where(Recipe.id == recipe_id)
    result = database.session.execute(statement).first()

    if result is None:
        flask.flash("Recipe not found.")
        return flask.redirect("/")
    
    recipe: Recipe = result[0]

    owned = False
    user = flask.session.get("logged_in_user")
    if logged_in and user == recipe.user_email:
        owned = True

    statement = database.select(Ingredient).where(Ingredient.recipe_id == recipe_id)
    result = database.session.execute(statement).all()
    ingredients = []
    for row in result:
        ingredients.append(row[0]) # Take ingredients out of the tuple

    # sort by order
    ingredients.sort(key=lambda x: x.order)

    return flask.render_template("recipe.html", recipe=recipe, logged_in=logged_in, ingredients=ingredients, owned=owned)

@app.route('/edit_recipe/<recipe_id>', methods=["GET", "POST"])
def edit_recipe(recipe_id):
    """
    Display a page that lets the user edit a recipe. Pre-fill the form with the current recipe information.
    For POST, update the recipe with the new information.
    """

    statement = database.select(Recipe).where(Recipe.id == recipe_id)
    result = database.session.execute(statement).first()
    result = result[0] # access the recipe

    # check if recipe exists
    if result is None:
        flask.flash("Recipe not found.")
        return flask.redirect("/")
    
    logged_in = False
    if "logged_in_user" in flask.session:
        logged_in = True
    
    # check if user owns the recipe
    if (not logged_in) or (flask.session["logged_in_user"] != result.user_email):
        flask.flash("You can't edit this recipe.")
        return flask.redirect("/")
    
    statement = database.select(Ingredient).where(Ingredient.recipe_id == recipe_id)

    all_ingredients = database.session.execute(statement).all()
    ingredients = []
    for row in all_ingredients:
        ingredients.append(row[0]) # Take ingredients out of the tuple
        
    ingredients.sort(key=lambda x: x.order)

    first_ingredient = ingredients[0]
    ingredients.pop(0) # remove the first ingredient

    if len(ingredients) == 0: # no additional ingredients
        ingredients = None
    
    if flask.request.method == "GET":
        return flask.render_template("edit_recipe.html", recipe=result, logged_in=logged_in, first_ingredient=first_ingredient, ingredients=ingredients)
    
    if flask.request.method == "POST":

        # update the recipe
        update_statement = database.update(Recipe).where(Recipe.id == recipe_id).values(
            name = flask.request.form.get("name"),
            type = flask.request.form.get("type"),
            photo = flask.request.form.get("image"),
            method = flask.request.form.get("instructions")
        )

        database.session.execute(update_statement)
        database.session.commit()

        # drop all the ingredients
        delete_statement = database.delete(Ingredient).where(Ingredient.recipe_id == recipe_id)
        database.session.execute(delete_statement)

        # re-add all the (edited) ingredients 
        ingredients = flask.request.form.getlist("items")
        quantities = flask.request.form.getlist("quantities")

        for i in range(len(ingredients)):
            ingredient = Ingredient()
            ingredient.recipe_id = recipe_id
            ingredient.name = ingredients[i]
            ingredient.quantity = quantities[i]
            ingredient.order = i
            database.session.add(ingredient)

        database.session.commit()

        flask.flash("Recipe updated successfully.")
        return flask.redirect("/recipe/" + recipe_id)
    
@app.route('/delete_recipe/<recipe_id>')
def delete_recipe(recipe_id):
    """
    Delete the recipe with the given id, if the user is the owner.
    """

    statement = database.select(Recipe).where(Recipe.id == recipe_id)
    result = database.session.execute(statement).first()
    result = result[0]

    if result is None:
        flask.flash("Recipe not found.")
        return flask.redirect("/")
    
    logged_in = False
    if "logged_in_user" in flask.session:
        logged_in = True

    if (not logged_in) or (flask.session["logged_in_user"] != result.user_email):
        flask.flash("You don't own this recipe.")
        return flask.redirect("/")
    
    # delete the recipe
    delete_statement = database.delete(Recipe).where(Recipe.id == recipe_id)
    database.session.execute(delete_statement)

    # delete the ingredients
    delete_statement = database.delete(Ingredient).where(Ingredient.recipe_id == recipe_id)
    database.session.execute(delete_statement)

    database.session.commit()

    flask.flash("Recipe deleted successfully.")
    return flask.redirect("/")

# /////////////////
#     Functions
# /////////////////

def advanced_search(query):

    search_statement = """SELECT recipes.id, recipes.photo, recipes.name, recipes.user_email, recipes.type, recipes.date_posted, recipes.method, avg_ratings.avg FROM 
                            recipes 
                            LEFT OUTER JOIN (SELECT recipe_id, AVG(stars) as avg FROM ratings GROUP BY recipe_id) as avg_ratings
                            ON recipes.id = avg_ratings.recipe_id
                            WHERE """
    if "name" in query:
        search_statement += "name LIKE :name AND "
        query["name"] = "%" + query["name"] + "%"
    if "id" in query:
        search_statement += "id = :id AND "
    if "type" in query:
        search_statement += "type LIKE :type AND "
        query["type"] = "%" + query["type"] + "%"
    if "email" in query:
        search_statement += "user_email = :email AND "
    if "min_rating" in query:
        search_statement += "avg_ratings.avg >= :min_rating AND "
    if "max_rating" in query:
        search_statement += "avg_ratings.avg <= :max_rating AND "
    if "ingredients" in query:
        search_statement += "id IN (SELECT recipe_id FROM ingredients WHERE name LIKE :ingredients) AND "
        query["ingredients"] = "%" + query["ingredients"] + "%"

    # trim the AND or WHERE
    if search_statement[-5:] == " AND ":
        search_statement = search_statement[:-5]
    if search_statement[-7:] == " WHERE ":
        search_statement = search_statement[:-7]

    results = database.session.execute(sqlalchemy.text(search_statement), query).all()
    return results

# /////////////////
#     Tables
# /////////////////

class User(database.Model):
    __tablename__ = "users"

    email = database.Column(database.String, primary_key=True)
    username = database.Column(database.String, nullable=False)
    password = database.Column(database.String, nullable=False)

    def __repr__(self):
        return f"User: {self.username} [{self.email}]"

class Recipe(database.Model):
    __tablename__ = "recipes"

    id = database.Column(database.Integer, primary_key=True)
    user_email = database.Column(database.String, database.ForeignKey("users.email"), nullable=False, index=True)
    name = database.Column(database.String, nullable=False, index=True)
    date_posted = database.Column(database.DateTime, nullable=False)
    type = database.Column(database.String, nullable=False, index=True)
    photo = database.Column(database.String)
    method = database.Column(database.String, nullable=False)

    def __repr__(self):
        return f"Recipe {self.id}: {self.name} ({self.type})"
    
class Ingredient(database.Model):
    __tablename__ = "ingredients"

    recipe_id = database.Column(database.Integer, database.ForeignKey("recipes.id"), primary_key=True)
    name = database.Column(database.String, primary_key=True)
    quantity = database.Column(database.String, nullable=False)
    order = database.Column(database.Integer, nullable=False)

    def __repr__(self):
        return f"{self.quantity} {self.name} [{self.recipe_id}]"
    
class Rating(database.Model):
    __tablename__ = "ratings"

    recipe_id = database.Column(database.Integer, database.ForeignKey("recipes.id"), primary_key=True)
    user_email = database.Column(database.String, database.ForeignKey("users.email"), primary_key=True)
    stars = database.Column(database.Integer, nullable=False)
    description = database.Column(database.String)


# /////////////////
#     Main
# /////////////////

with app.app_context():
    database.create_all()
    
    # Sample data
    newUsers = [
        User(username="bob", email="bob@gmail.com", password="password"),
        User(username="charlie", email="charlie@gmail.com", password="password"),
        User(username="alice", email="alice@gmail.com", password="password"),
        User(username="david", email="david@gmail.com", password="password"),
        User(username="emma", email="emma@gmail.com", password="password"),
        User(username="frank", email="frank@gmail.com", password="password"),
        User(username="grace", email="grace@gmail.com", password="password"),
        User(username="hannah", email="hannah@gmail.com", password="password"),
        User(username="ian", email="ian@gmail.com", password="password"),
        User(username="julia", email="julia@gmail.com", password="password"),
        User(username="kyle", email="kyle@gmail.com", password="password"),
        User(username="linda", email="linda@gmail.com", password="password"),
        User(username="mike", email="mike@gmail.com", password="password"),
        User(username="nina", email="nina@gmail.com", password="password"),
        User(username="oscar", email="oscar@gmail.com", password="password"),
        User(username="paul", email="paul@gmail.com", password="password"),
        User(username="quincy", email="quincy@gmail.com", password="password"),
    ]

    date = datetime.date(2024, 1, 1)

    newRecipes = []
    newIngredients = []

    newRecipes.append( Recipe(id = 1, user_email="bob@gmail.com", name="Baked Ziti", date_posted=date, type="Italian", photo=r"https://www.allrecipes.com/thmb/oXuLKPsb-Wa_LolmP3JpVl7q2ow=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/18031-baked-ziti-ii-DDMFS-4x3-45e614088a504a67b9a9dde7001be4ee.jpg", 
                              method="1. Preheat oven to 350°F.\n2. Cook pasta according to directions.\n3. Mix pasta with sauce and cheese.\n4. Bake for 20 minutes.") )
    newIngredients.append( Ingredient(recipe_id=1, name="Ziti pasta", quantity="1 box", order=1) )
    newIngredients.append( Ingredient(recipe_id=1, name="Pasta sauce", quantity="2 cups", order=2) )
    newIngredients.append( Ingredient(recipe_id=1, name="Mozzarella cheese", quantity="1 oz", order=3) )

    newRecipes.append( Recipe(id=2, user_email="charlie@gmail.com", name="Chicken Tikka Masala", date_posted=date, type="Indian", photo=r"https://www.allrecipes.com/thmb/1ul-jdOz8H4b6BDrRcYOuNmJgt4=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/239867chef-johns-chicken-tikka-masala-ddmfs-3X4-0572-e02a25f8c7b745459a9106e9eb13de10.jpg",
                            method="1. Marinate chicken in yogurt and spices for 1 hour.\n2. Cook chicken in a skillet.\n3. Simmer chicken in spiced tomato cream sauce.\n4. Serve with rice.") )
    newIngredients.append( Ingredient(recipe_id=2, name="Chicken", quantity="1 lb", order=1) )
    newIngredients.append( Ingredient(recipe_id=2, name="Yogurt", quantity="1 cup", order=2) )
    newIngredients.append( Ingredient(recipe_id=2, name="Garam masala", quantity="2 tsp", order=3) )
    newIngredients.append( Ingredient(recipe_id=2, name="Tomato puree", quantity="1 cup", order=4) )
    newIngredients.append( Ingredient(recipe_id=2, name="Heavy cream", quantity="1/2 cup", order=5) )
    newIngredients.append( Ingredient(recipe_id=2, name="Rice", quantity="2 cups", order=6) )

    newRecipes.append( Recipe(id=3, user_email="emma@gmail.com", name="Sushi Rolls", date_posted=date, type="Japanese", photo=r"https://www.sbfoods-worldwide.com/recipes/q78eit00000004lp-img/5_Dragonroll_Wasabi_recipe.jpg",
                            method="1. Cook sushi rice.\n2. Lay seaweed on bamboo mat.\n3. Spread rice, add fillings, and roll tightly.\n4. Slice into pieces.") )
    newIngredients.append( Ingredient(recipe_id=3, name="Sushi rice", quantity="1 cup", order=1) )
    newIngredients.append( Ingredient(recipe_id=3, name="Seaweed sheets", quantity="5 sheets", order=2) )
    newIngredients.append( Ingredient(recipe_id=3, name="Cucumber", quantity="1, julienned", order=3) )
    newIngredients.append( Ingredient(recipe_id=3, name="Avocado", quantity="1, sliced", order=4) )
    newIngredients.append( Ingredient(recipe_id=3, name="Imitation crab", quantity="4 oz", order=5) )

    newRecipes.append( Recipe(id=4, user_email="frank@gmail.com", name="Tacos", date_posted=date, type="Mexican", photo=r"https://www.allrecipes.com/thmb/vG-of0Xa0W0eodSXPWV1KXD009U=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/70935-taqueria-style-tacos-mfs-3x2-35-9145991a0ef94ceb8be05ae8d6be4f0f.jpg",
                            method="1. Cook ground beef with taco seasoning.\n2. Warm tortillas.\n3. Fill tortillas with meat and toppings of choice.\n4. Serve immediately.") )
    newIngredients.append( Ingredient(recipe_id=4, name="Ground beef", quantity="1 lb", order=1) )
    newIngredients.append( Ingredient(recipe_id=4, name="Taco seasoning", quantity="1 packet", order=2) )
    newIngredients.append( Ingredient(recipe_id=4, name="Tortillas", quantity="6 small", order=3) )
    newIngredients.append( Ingredient(recipe_id=4, name="Lettuce", quantity="1 cup, shredded", order=4) )
    newIngredients.append( Ingredient(recipe_id=4, name="Cheddar cheese", quantity="1 cup, shredded", order=5) )
    newIngredients.append( Ingredient(recipe_id=4, name="Sour cream", quantity="1/2 cup", order=6) )

    newRecipes.append( Recipe(id=5, user_email="hannah@gmail.com", name="Pad Thai", date_posted=date, type="Thai", photo=r"https://cdn.apartmenttherapy.info/image/upload/f_jpg,q_auto:eco,c_fill,g_auto,w_1500,ar_4:3/k%2FPhoto%2FRecipes%2F2024-04-pad-thai-190%2Fpad-thai-190-251",
                            method="1. Soak rice noodles in warm water.\n2. Stir-fry shrimp and tofu.\n3. Add noodles, sauce, and mix well.\n4. Serve with peanuts and lime.") )
    newIngredients.append( Ingredient(recipe_id=5, name="Rice noodles", quantity="1 package", order=1) )
    newIngredients.append( Ingredient(recipe_id=5, name="Shrimp", quantity="1/2 lb", order=2) )
    newIngredients.append( Ingredient(recipe_id=5, name="Tofu", quantity="1/2 lb, cubed", order=3) )
    newIngredients.append( Ingredient(recipe_id=5, name="Pad Thai sauce", quantity="1/2 cup", order=4) )
    newIngredients.append( Ingredient(recipe_id=5, name="Peanuts", quantity="1/4 cup, crushed", order=5) )
    newIngredients.append( Ingredient(recipe_id=5, name="Lime", quantity="1, cut into wedges", order=6) )

    newRecipes.append( Recipe(id=6, user_email="kyle@gmail.com", name="Beef Stroganoff", date_posted=date, type="Russian", photo=r"https://cdn.apartmenttherapy.info/image/upload/f_jpg,q_auto:eco,c_fill,g_auto,w_1500,ar_4:3/k%2FPhoto%2FRecipes%2F2024-03-beef-stroganoff-190%2Fbeef-stroganoff-190-342_1",
                            method="1. Cook beef strips with onions.\n2. Make sauce with sour cream and broth.\n3. Add beef back to the sauce.\n4. Serve over egg noodles.") )
    newIngredients.append( Ingredient(recipe_id=6, name="Beef strips", quantity="1 lb", order=1) )
    newIngredients.append( Ingredient(recipe_id=6, name="Onion", quantity="1, sliced", order=2) )
    newIngredients.append( Ingredient(recipe_id=6, name="Mushrooms", quantity="1 cup, sliced", order=3) )
    newIngredients.append( Ingredient(recipe_id=6, name="Sour cream", quantity="1 cup", order=4) )
    newIngredients.append( Ingredient(recipe_id=6, name="Beef broth", quantity="1/2 cup", order=5) )
    newIngredients.append( Ingredient(recipe_id=6, name="Egg noodles", quantity="2 cups, cooked", order=6) )

    newRecipes.append( Recipe(id=7, user_email="julia@gmail.com", name="Shrimp Tacos", date_posted=date, type="Mexican", photo=r"https://www.allrecipes.com/thmb/Zn2RPAHWj71aOmYzhiKRbRHu5yU=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/280916-shrimp-tacos-with-cilantro-lime-crema-4x3-0389-1b3aec87d6e54bd0b1f06b0e36478124.jpg",
                            method="1. Season shrimp and cook in a skillet.\n2. Warm tortillas.\n3. Fill tortillas with shrimp and toppings of choice.\n4. Serve with lime.") )
    newIngredients.append( Ingredient(recipe_id=7, name="Shrimp", quantity="1/2 lb", order=1) )
    newIngredients.append( Ingredient(recipe_id=7, name="Taco seasoning", quantity="1 tsp", order=2) )
    newIngredients.append( Ingredient(recipe_id=7, name="Tortillas", quantity="6 small", order=3) )
    newIngredients.append( Ingredient(recipe_id=7, name="Cabbage", quantity="1 cup, shredded", order=4) )
    newIngredients.append( Ingredient(recipe_id=7, name="Avocado", quantity="1, sliced", order=5) )
    newIngredients.append( Ingredient(recipe_id=7, name="Lime", quantity="1, cut into wedges", order=6) )

    newRecipes.append( Recipe(id=8, user_email="nina@gmail.com", name="Chicken Pot Pie", date_posted=date, type="American", photo=r"https://mojo.generalmills.com/api/public/content/tKec_wnrtk-lTBFsG4Vi5A_webp_base.webp?v=495880c8&t=e724eca7b3c24a8aaa6e089ed9e611fd",
                            method="1. Cook chicken and vegetables in broth.\n2. Add cream and flour to thicken.\n3. Pour into pie crust and cover with another crust.\n4. Bake at 375°F for 45 minutes.") )
    newIngredients.append( Ingredient(recipe_id=8, name="Chicken", quantity="1 lb, diced", order=1) )
    newIngredients.append( Ingredient(recipe_id=8, name="Carrots", quantity="1 cup, diced", order=2) )
    newIngredients.append( Ingredient(recipe_id=8, name="Peas", quantity="1 cup", order=3) )
    newIngredients.append( Ingredient(recipe_id=8, name="Chicken broth", quantity="2 cups", order=4) )
    newIngredients.append( Ingredient(recipe_id=8, name="Heavy cream", quantity="1/2 cup", order=5) )
    newIngredients.append( Ingredient(recipe_id=8, name="Flour", quantity="2 tbsp", order=6) )
    newIngredients.append( Ingredient(recipe_id=8, name="Pie crust", quantity="2 sheets", order=7) )

    newRecipes.append( Recipe(id=9, user_email="paul@gmail.com", name="Onion Rings", date_posted=date, type="American", photo=r"https://staticcookist.akamaized.net/wp-content/uploads/sites/22/2024/06/cheese-onion-rings.jpg",
                            method="1. Slice onions into rings.\n2. Dip rings into batter, then coat with breadcrumbs.\n3. Deep-fry until golden brown.\n4. Serve with dipping sauce.") )
    newIngredients.append( Ingredient(recipe_id=9, name="Onion", quantity="2 large", order=1) )
    newIngredients.append( Ingredient(recipe_id=9, name="Flour", quantity="1 cup", order=2) )
    newIngredients.append( Ingredient(recipe_id=9, name="Milk", quantity="1 cup", order=3) )
    newIngredients.append( Ingredient(recipe_id=9, name="Egg", quantity="1, beaten", order=4) )
    newIngredients.append( Ingredient(recipe_id=9, name="Breadcrumbs", quantity="1 cup", order=5) )
    newIngredients.append( Ingredient(recipe_id=9, name="Oil", quantity="2 cups, for frying", order=6) )

    # Uncomment these lines to add the sample data to the database

    # for r in newRecipes:
    #     database.session.add(r)

    # for i in newIngredients:
    #     database.session.add(i)

    # for u in newUsers:
    #     database.session.add(u)

    database.session.commit()

if __name__ == "__main__":
    app.run(debug=True)