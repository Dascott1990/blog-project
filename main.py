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
from forms import ContactForm
import hashlib
import time
import glob

# Load environment variables from .env file
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
ckeditor = CKEditor(app)
Bootstrap5(app)

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


# Use SQLite database - this will preserve your existing data
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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


@app.route('/profile')
def profile():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template('profile.html', user=current_user, gravatar_url=gravatar_url)


def gravatar_url(email, size=80):
    hash_email = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash_email}?s={size}&d=identicon"


# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


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


def load_email_templates():
    """Load email templates from text files"""
    templates = []
    template_files = glob.glob('email_templates/template_*.txt')

    if not template_files:
        logging.warning("No email template files found. Using fallback template.")
        return [{
            "subject": "Verification Code Required",
            "body": "Your verification code is: {verification_code}\n\nThis code expires in 10 minutes."
        }]

    for file_path in template_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                # Split subject and body (first line is subject, rest is body)
                lines = content.split('\n')
                subject = lines[0].strip()
                body = '\n'.join(lines[1:]).strip()

                templates.append({
                    "subject": subject,
                    "body": body
                })
        except Exception as e:
            logging.error(f"Error loading email template {file_path}: {e}")

    return templates


def send_verification_email(user_email, verification_code):
    # Load templates dynamically
    templates = load_email_templates()

    if not templates:
        logging.error("No email templates available")
        return False

    # Select a random template for variety across 21,000+ users
    template = random.choice(templates)

    email_message = f"""Subject: {template['subject']}

{template['body'].format(verification_code=verification_code)}

---
This is an automated message. Please do not reply to this email.
For support, contact our help desk at dascottblog@gmail.com
"""

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as connection:
            connection.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            connection.sendmail(EMAIL_ADDRESS, user_email, email_message)
        print(f"Verification email sent successfully to {user_email}!")
        return True
    except Exception as e:
        logging.error(f"Error sending verification email to {user_email}: {e}")
        return False


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
        session['user_name'] = form.name.data
        session['registration_time'] = time.time()

        # Generate the 6-digit verification code
        verification_code = generate_verification_code()
        session['verification_code'] = verification_code
        session['verification_attempts'] = 0

        # Send the verification email to the user's email
        if send_verification_email(form.email.data, verification_code):
            flash("A verification code has been sent to your email. Please check your inbox.")
            return redirect(url_for('verify_email'))
        else:
            flash("Failed to send verification email. Please try again.")
            return redirect(url_for('register'))

    return render_template("register.html", form=form, current_user=current_user)


@app.route('/verify', methods=["GET", "POST"])
def verify_email():
    form = VerificationForm()

    # Check if verification code has expired (10 minutes)
    registration_time = session.get('registration_time')
    if registration_time and time.time() - registration_time > 600:  # 10 minutes
        flash("Verification code has expired. Please register again.")
        session.clear()
        return redirect(url_for('register'))

    if form.validate_on_submit():
        verification_attempts = session.get('verification_attempts', 0) + 1
        session['verification_attempts'] = verification_attempts

        if verification_attempts > 5:
            flash("Too many failed attempts. Please register again.")
            session.clear()
            return redirect(url_for('register'))

        if form.verification_code.data == session.get('verification_code'):
            flash("Email verified successfully! Welcome to our community.")
            session.pop('verification_code', None)
            session.pop('verification_attempts', None)
            session.pop('registration_time', None)

            # Retrieve email, password, and name from session
            email = session.get('user_email')
            password = session.get('user_password')
            name = session.get('user_name')
            password_hash = generate_password_hash(password)

            # Create the user in the database
            new_user = User(
                email=email,
                name=name,
                password=password_hash
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)

            # Clear session data after user is created
            session.pop('user_email', None)
            session.pop('user_password', None)
            session.pop('user_name', None)

            return redirect(url_for('get_all_posts'))
        else:
            remaining_attempts = 5 - verification_attempts
            flash(f"Invalid verification code. {remaining_attempts} attempts remaining.")

    return render_template("verify.html", form=form)


@app.route('/resend-verification-code', methods=["GET"])
def resend_verification_code():
    if 'user_email' in session:
        # Check if we can resend (prevent spam)
        last_resend = session.get('last_resend_time', 0)
        if time.time() - last_resend < 60:  # 1 minute cooldown
            flash("Please wait a moment before requesting a new code.")
            return redirect(url_for('verify_email'))

        verification_code = generate_verification_code()
        session['verification_code'] = verification_code
        session['last_resend_time'] = time.time()

        if send_verification_email(session['user_email'], verification_code):
            flash("A new verification code has been sent to your email.")
        else:
            flash("Failed to send verification code. Please try again.")
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
            flash(f"Welcome back, {user.name}!")
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out successfully.")
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
        flash("Comment added successfully!")
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
        flash("Post created successfully!")
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
        flash("Post updated successfully!")
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    flash("Post deleted successfully!")
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    msg_sent = False

    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        phone = form.phone.data
        message = form.message.data

        # Construct email message
        email_subject = f"New Contact Form Submission from {name}"
        email_body = f"Name: {name}\nEmail: {email}\nPhone: {phone}\n\nMessage:\n{message}"

        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.sendmail(EMAIL_ADDRESS, "dascottblog@gmail.com", f"Subject: {email_subject}\n\n{email_body}")
            msg_sent = True
            flash("Your message has been sent successfully!")
        except Exception as e:
            print(f"Error sending email: {e}")
            flash("Sorry, there was an error sending your message. Please try again.")

    return render_template("contact.html", form=form, msg_sent=msg_sent)


@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}


@app.route('/healthz')
def health_check():
    return "OK", 200


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)