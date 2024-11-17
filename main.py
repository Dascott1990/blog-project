import os
from datetime import datetime, date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, VerificationForm
import smtplib
import random
import string
from dotenv import load_dotenv
import logging
import ssl
from flask_migrate import Migrate
from flask import redirect




# Load environment variables from .env file
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
ckeditor = CKEditor(app)
Bootstrap5(app)



@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def redirect_to_www(path):
    return redirect(f"https://www.dask.com.ng/{path}", code=301)


# Configured Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Configure Gravatar for profile images
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# Initialize Migrate
migrate = Migrate(app, db)

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")


with app.app_context():
    db.create_all()

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)  # Changed this to work with Flask-Login

# Admin decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Helper function to generate a 6-digit verification code
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(user_email, verification_code):
    email_message = f"""
    Subject: Email Verification Code

    We sent an email with a verification code to {user_email}.
    Enter it below to confirm your email.

    Verification code: {verification_code}

    A verification code is required.
    """
    try:
        context = ssl.create_default_context()
        # Use SMTP_SSL directly for SSL encryption
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as connection:
            connection.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            connection.sendmail(EMAIL_ADDRESS, user_email, email_message)
        print("Verification email sent successfully!")
    except Exception as e:
        logging.error(f"Error sending verification email: {e}")


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if the email is already in the database
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        # Store email, password, and name in session
        session['user_email'] = form.email.data
        session['user_password'] = form.password.data
        session['user_name'] = form.name.data  # Store the name in the session

        # Generate the 6-digit verification code
        verification_code = generate_verification_code()

        # Store the verification code in the session
        session['verification_code'] = verification_code

        # Send the verification email to the user's email
        send_verification_email(form.email.data, verification_code)

        # Redirect to the verification page
        return redirect(url_for('verify_email'))  # Redirecting to verify page

    return render_template("register.html", form=form, current_user=current_user)

@app.route('/verify', methods=["GET", "POST"])
def verify_email():
    form = VerificationForm()
    if form.validate_on_submit():
        # Check if the code entered by the user matches the code stored in the session
        if form.verification_code.data == session.get('verification_code'):
            flash("Email verified successfully!")
            session.pop('verification_code', None)

            # Retrieve email, password, and name from session
            email = session.get('user_email')
            password = session.get('user_password')
            name = session.get('user_name')  # Get the name from the session
            password_hash = generate_password_hash(password)

            # Create the user in the database
            new_user = User(
                email=email,
                name=name,  # Use the name from the session
                password=password_hash
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)

            # Clear session data after user is created
            session.pop('user_email', None)
            session.pop('user_password', None)
            session.pop('user_name', None)  # Clear the name from the session

            return redirect(url_for('get_all_posts'))  # Redirect to homepage after successful verification
        else:
            flash("Invalid verification code. Please try again.")

    return render_template("verify.html", form=form)

@app.route('/resend-verification-code', methods=["GET"])
def resend_verification_code():
    if 'user_email' in session:
        verification_code = generate_verification_code()
        session['verification_code'] = verification_code
        send_verification_email(session['user_email'], verification_code)
        flash("A new verification code has been sent to your email.")
        return redirect(url_for('verify_email'))
    flash("No email found in session.")
    return redirect(url_for('register'))

@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, current_user=current_user, form=comment_form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        data = request.form
        send_email("Contact Form Message", data["message"], "admin@example.com")
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)

@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}

@app.route('/healthz')
def health_check():
    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
