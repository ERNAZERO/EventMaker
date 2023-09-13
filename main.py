from flask import Flask, render_template, request, redirect, flash, url_for, session
from flask_login import login_required, current_user, LoginManager, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import threading
from models import db, Users, Occurrence, Friendship
import datetime
import schedule
import time
from peewee import *
import base64

app = Flask(__name__, static_url_path='/static')
app.secret_key = os.urandom(24)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Users.select().where(Users.id==int(user_id)).first()


@app.before_request
def before_request():
    db.connect()


@app.after_request
def after_request(response):
    db.close()
    return response


@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        user = Users.select().where(Users.email==email).first()
        if not user or not check_password_hash(user.password, password):
            flash('Please check your login details and try again.')
            return redirect('/login/')
        else:
            login_user(user)
            return redirect('/')
    return render_template('login.html')


@app.route('/logout/')
def logout():
    logout_user()
    return redirect('/')


def validate_password(password):
    if len(password) < 8 and len(password)>32:
        return False
    if not any(char.isdigit() for char in password):
        return False
    if not any(char.islower() for char in password):
        return False
    if not any(char.isupper() for char in password):
        return False
    return True



@app.route('/register/', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        age = request.form['age']
        email = request.form['email']
        password = request.form['password']
        file = request.files['avatar']
        user = Users.select().where(Users.email == email).first()
        # if file.filename == '':
        #     avatar_data = save_default_avatar()
        # else:
        avatar_data = file.read()
        if user:
            flash('email address already exists')
            return redirect('/register/')
        if Users.select().where(Users.username == username).first():
            flash('username already exists')
            return redirect('/register/')
        else:
            if validate_password(password):
                Users.create(
                    username=username,
                    age=age,
                    email=email,
                    password=generate_password_hash(password),
                    avatar=avatar_data
                )
                return redirect('/login/')
            else:
                flash('wrong password')
                return redirect('/register/')
    return render_template('register.html')





def save_default_event_image():
    with open('./static/images/Why You Should Do Nothing.jpeg', 'rb') as default_post_image_file:
        default_post_image_data = default_post_image_file.read()
        return  default_post_image_data


@app.route('/create_event/', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        planned_date = request.form['planned_date']
        planned_hour = int(request.form['planned_hour'])
        planned_minute = int(request.form['planned_minute'])
        # public_event = request.form['public_event']

        if 'public_event' in request.form:
            public_event = True
        else:
            public_event = False

        file = request.files['post_image']
        planned_datetime = datetime.datetime.strptime(planned_date, '%Y-%m-%d')
        planned_datetime = planned_datetime.replace(hour=planned_hour, minute=planned_minute)

        if file.filename == '':
            event_image_data = save_default_event_image()
        else:
            event_image_data = file.read()
        Occurrence.create(
            author=current_user,
            title=title,
            content=content,
            planned_date=planned_datetime,
            public=public_event,
            post_image=event_image_data
        )

        return redirect('/')
    return render_template('create_event.html')


@app.route('/<int:id>/')
@login_required
def get_event(id):
    occurrence = Occurrence.select().where(((current_user.id == Occurrence.author) | (Occurrence.public == True )) & (Occurrence.id == id)).first()
    if occurrence:
        return render_template('event_detail.html', occurrence=occurrence, bytea_to_base64=bytea_to_base64)
    return f'Event with id = {id} does not exists'


@app.route('/<int:id>/update/', methods=('GET', 'POST'))
@login_required
def update(id):
    occurrence = Occurrence.select().where(Occurrence.id==id).first()
    if request.method == 'POST':
        if occurrence:
            content = request.form['content']
            # post_image_data = filename.read()
            planned_date = request.form['planned_date']
            planned_hour = int(request.form['planned_hour'])
            planned_minute = int(request.form['planned_minute'])
            planned_datetime = datetime.datetime.strptime(planned_date, '%Y-%m-%d')
            planned_datetime = planned_datetime.replace(hour=planned_hour, minute=planned_minute)

            obj = Occurrence.update({
                    Occurrence.content: content,
                    Occurrence.planned_date: planned_datetime
            }).where(Occurrence.id == id)
            obj.execute()
            return redirect(f'/{id}/')
        return f'Post with id = {id} does not exists'
    return render_template('update.html', occurrence=occurrence)


@app.route('/delete_event/<int:id>', methods=['DELETE'])
def delete_event(id):
    try:
        occurrence = Occurrence.select().where(Occurrence.id==id).first()
        occurrence.delete_instance()
        return 'Успешно удалено', 200
    except Occurrence.DoesNotExist:
        return 'Событие не найдено', 404


@app.route('/search_events/', methods=['GET', 'POST'])
def search():
    current_user_id = current_user.id if current_user.is_authenticated else None
    if request.method == 'POST':
        query = request.form.get('query')
    else:
        query = request.args.get('query')
    if query:
        occurrences = Occurrence.select().where(Occurrence.title.contains(query), Occurrence.author == current_user_id )
    else:
        occurrences = Occurrence.select().where(Occurrence.author == current_user)
    return render_template('search_results.html', occurrences=occurrences)


@app.route('/')
def index():
    deleted_count = delete_old_occurrences()
    occurrences = Occurrence.select().where(Occurrence.author == current_user)
    return render_template('index.html', occurrences=occurrences, deleted_count=deleted_count, bytea_to_base64=bytea_to_base64)


@app.route('/event_image/<int:id>/', methods=['GET'])
def event_detail(id):
    event = Occurrence.get_or_none(id=id)
    if event:
        event_planned_date_str = event.planned_date.strftime('%Y-%m-%dT%H:%M:%S')
        return render_template('event_detail.html', event=event, event_planned_date=event_planned_date_str, bytea_to_base64=bytea_to_base64)
    return f'Событие с id = {id} не найдено.'


def bytea_to_base64(bytea_data):
    return base64.b64encode(bytea_data).decode('utf-8')


@app.route('/search_friends/', methods=['GET', 'POST'])
@login_required
def search_friends():
    if request.method == 'POST':
        # Получаем значение из поискового поля
        search_username = request.form['search_username']

        # Вызываем функцию для поиска пользователей по имени
        users = Users.select().where(Users.username.contains(search_username))
        # Отображаем результаты на HTML странице
        if users:
            return render_template('search_friends.html', users=users)

    return render_template('search_friends.html')


@app.route('/current_profile/')
@login_required
def my_profile():
    return render_template('profile.html', users=current_user, bytea_to_base64=bytea_to_base64)


@app.route('/profile/<int:id>/')
@login_required
def profile(id):
    user = Users.select().where(Users.id == id).first()
    occurrences = Occurrence.select().where((Occurrence.author == user) & (Occurrence.public == True))
    if user:
        return render_template('profile.html', users=user, occurrences=occurrences, bytea_to_base64=bytea_to_base64)
    else:
        return 'Error'


@app.route('/update_profile/', methods=('GET', 'POST'))
@login_required
def profile_update():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        age = request.form['age']
        file = request.files['avatar']
        avatar_data = file.read()

        obj = Users.update({
            Users.username: username,
            Users.email: email,
            Users.age: age,


            Users.avatar: avatar_data
        }).where(Users.id == current_user.id)
        obj.execute()
        return redirect(f'/current_profile/')
    return render_template('profile_update.html', user=current_user)


def save_default_avatar():
    with open('./static/images/img.png', 'rb') as default_avatar_file:
        default_avatar_data = default_avatar_file.read()
        return default_avatar_data


def delete_old_occurrences():
    now = datetime.datetime.now()
    query = Occurrence.delete().where(Occurrence.planned_date < now)
    deleted_count = query.execute()
    return deleted_count



if __name__ == '__main__':


    app.debug = True
    app.run()