from flask import Flask, render_template, g, flash, request, redirect, url_for, session
import sqlite3
import functools
import os
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = '5f21e03248d6309cfc8dae6b7f3682e22573017377f663d0'
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'
app.config['MAIL_PASSWORD'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
mail = Mail(app)

DATABASE = 'db.db'

def loginRequired(view):
	@functools.wraps(view)
	def wrapped_view(**kwargs):
		if session.get('user_id') is None:
			return redirect(url_for("login"))
		return view(**kwargs)
	return wrapped_view

def adminRequired(view):
	@functools.wraps(view)
	def wrapped_view(**kwargs):
		if not session.get('admin'):
			return redirect(url_for("viewJobs"))
		return view(**kwargs)
	return wrapped_view

def nonAdminRequired(view):
	@functools.wraps(view)
	def wrapped_view(**kwargs):
		if session.get('admin'):
			return redirect(url_for("viewJobs"))
		return view(**kwargs)
	return wrapped_view

def getDb():
	db = getattr(g, '_database', None)
	if db is None:
		db = g._database = sqlite3.connect(DATABASE)
	return db

@app.teardown_appcontext
def closeConnection(exception):
	db = getattr(g, '_database', None)
	if db is not None:
		db.close()

@app.route('/')
@app.route('/index/')
def index():
	return redirect(url_for('login'))
#	return render_template('index.html', page = 0)

@app.route('/login/', methods=('GET', 'POST'))
def login():
	return log(False)

@app.route('/login_admin/', methods=('GET', 'POST'))
def loginAdmin():
	return log(True)

def log(admin):
	error = None
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		db = getDb()
		if not username:
			error = "Username is required"
		elif not password:
			error = "Password is required"
		if error is None:
			table = "useradmin" if admin else "user"
			user = db.execute(f"SELECT id, password FROM {table} WHERE username=?",(username,)).fetchone()
			if user is None or user[1] != password:
				error = 'Incorrect username or password'
			else:
				session.clear()
				session['user_id'] = user[0]
				session['admin'] = admin
				session['username'] = username
				return redirect(url_for('viewJobs'))
	url = 'login_admin.html' if admin else 'login.html'
	return render_template(url, error = error, page = 1)

@app.route('/register/', methods=('GET', 'POST'))
def register():
	return reg(False)

@app.route('/register_admin/', methods=('GET', 'POST'))
def registerAdmin():
	return reg(True)

def reg(admin):
	error = None
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		db = getDb()
		if not username:
			error = "Username is required"
		elif not password:
			error = "Password is required"
		if error is None:
			try:
				table = "useradmin" if admin else "user"
				db.execute(f"INSERT INTO {table}(username, password) VALUES(?, ?)", (username, password))
				db.commit()
				i = db.execute(f'select seq from sqlite_sequence where name="{table}"').fetchone()
				session.clear()
				session['user_id'] = i[0]
				session['username'] = username
				session['admin'] = admin
			except db.IntegrityError:
				error = f"User {username} is already registered"
			else:
				return redirect(url_for("viewJobs"))
	url = 'register_admin.html' if admin else 'register.html'
	return render_template(url, error = error, page = 2)

@app.route('/view_jobs/', methods=('GET', 'POST'))
@loginRequired
def viewJobs():
	applied = False
	if request.method == 'POST':
		db = getDb()
		db.execute("INSERT INTO jobapplied (uid, jid) VALUES (?, ?)", (session['user_id'], request.form['job_id']))
		db.commit()
		jc = db.execute("SELECT job, company FROM job where id=?", (request.form['job_id'],)).fetchone()
		applied = True
		msg = Message('Confirmation of job application', recipients=[session['username']], sender='1923001@saec.ac.in')
		msg.html = 'This is to confirm that you have successfully applied for the role of ' + jc[0] + ' at ' + jc[1]
		mail.send(msg)
	db = getDb()
	jobs = db.execute('SELECT id, company, job, domain, salary FROM job').fetchall()
	session['jobs'] = jobs
	return render_template('view_jobs.html', applied = applied, page = 3)

@app.route('/add_jobs/', methods=('GET', 'POST'))
@loginRequired
@adminRequired
def addJobs():
	if request.method == 'POST':
		db = getDb()
		db.execute('INSERT INTO job (company, job, domain, salary) VALUES (?, ?, ?, ?)', (session['username'], request.form['job'], request.form['domain'], request.form['salary']))
		db.commit()
		return redirect(url_for('viewJobs'))
	return render_template('add_jobs.html')

@app.route('/applied_jobs/')
@loginRequired
@nonAdminRequired
def appliedJobs():
	db = getDb()
	jids = db.execute('SELECT jid FROM jobapplied WHERE uid=' + str(session['user_id'])).fetchall()
	jobs = []
	for jid in jids:
		jobs.append(db.execute('SELECT id, company, job, domain, salary FROM job WHERE id=' + str(jid[0])).fetchone())
	session['jobs'] = jobs
	return render_template('applied_jobs.html', page = 4)

@app.route('/signout/')
def signout():
	session.clear()
	return redirect(url_for('index'))

def initDb():
	with app.app_context():
		db = getDb()
		with app.open_resource('schema.sql', mode='r') as f:
			db.cursor().executescript(f.read())
		db.commit()

#initDb()

app.run()
