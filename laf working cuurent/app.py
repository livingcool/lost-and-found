from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import os
import zipfile
import mysql.connector
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for flash messages
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create the UPLOAD_FOLDER directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


class Item:
    def __init__(self, item_type, description, location, contact_number, image_urls):
        self.item_type = item_type
        self.description = description
        self.location = location
        self.contact_number = contact_number
        self.image_urls = image_urls


class LostAndFoundCommunity:
    def __init__(self):
        self.items = []
        self.db_connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='lost_and_found'
        )
        self.db_cursor = self.db_connection.cursor()

    def post_item(self, item):
        image_paths = []  # Define the image_paths variable to store the paths of uploaded images
        for image in item.image_urls:
            _, ext = os.path.splitext(image.filename)
            filename = str(uuid.uuid4()) + ext
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            image_paths.append(image_path)

        image_urls = ','.join(image_paths)  # Convert the list of image paths to a comma-separated string
        self.db_cursor.execute(
            'INSERT INTO items (item_type, description, location, contact_number, image_url) VALUES (%s, %s, %s, %s, %s)',
            (item.item_type, item.description, item.location, item.contact_number, image_urls)
        )
        self.db_connection.commit()

    def search_by_location(self, location):
        self.db_cursor.execute('SELECT * FROM items WHERE location = %s', (location,))
        items_data = self.db_cursor.fetchall()
        items = []
        for item_data in items_data:
            item = Item(item_data[1], item_data[2], item_data[3], item_data[5], self.get_image_urls(item_data[4]))
            items.append(item)
        return items

    def get_image_urls(self, image_filenames):
        if image_filenames:
            image_urls = []
            for filename in image_filenames.split(','):
                image_urls.append(url_for('uploaded_file', filename=filename, _external=True))
            return image_urls
        else:
            return None

    def check_login(self, email, password):
        try:
            self.db_cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s',
                                   (email, password))
            result = self.db_cursor.fetchone()
            if result:
                return True
            else:
                return False
        except mysql.connector.Error as error:
            print("Error while checking login:", error)
        return False

    def register_user(self, username, email, password):
        self.db_cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                               (username, email, password))
        self.db_connection.commit()  # Commit the changes to the database


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Create a new instance of the LostAndFoundCommunity class
community = LostAndFoundCommunity()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/submit_courier', methods=['POST'])
def submit_courier():
    sender_name = request.form['senderName']
    sender_email = request.form['senderEmail']
    receiver_name = request.form['receiverName']
    receiver_address = request.form['receiverAddress']
    product_description = request.form['productDescription']
    delivery_option = request.form['deliveryOption']

    try:
        community.db_cursor.execute(
            '''
            INSERT INTO courier_details (sender_name, sender_email, receiver_name, receiver_address, product_description, delivery_option)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''',
            (sender_name, sender_email, receiver_name, receiver_address, product_description, delivery_option)
        )
        community.db_connection.commit()

        flash('Courier request submitted successfully!', 'success')  # Flash a success message
    except mysql.connector.Error as error:
        flash(f"Error occurred while submitting courier request: {str(error)}", 'error')

    return redirect(url_for('index'))




@app.route('/download_images')
def download_images():
    filenames = request.args.getlist('filenames')
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images.zip')

    # Create a zip file containing all the images
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for filename in filenames:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                zip_file.write(file_path, arcname=filename)

    # Send the zip file as a response for download
    return send_from_directory(app.config['UPLOAD_FOLDER'], 'images.zip', as_attachment=True)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        community.register_user(username, email, password)  # Register the user
        flash('User registered successfully!', 'success')  # Flash a success message
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']  # Update the field name to 'email'
        password = request.form['password']
        # Perform login logic
        if community.check_login(email, password):  # Update the parameter name to 'email'
            flash('Login successful!', 'success')
            return redirect(url_for('index'))

        flash('Incorrect email or password!', 'error')  # Update the flash message
    return render_template('login.html')


@app.route('/chatbox')
def chatbox():
    return render_template('chatbox.html')


@app.route('/courier')
def courier():
    return render_template('courier.html')


@app.route('/post_item', methods=['GET', 'POST'])
def post_item():
    if request.method == 'POST':
        item_type = request.form['item_type']
        description = request.form['description']
        location = request.form['location']
        contact_number = request.form['contact_number']
        # Retrieve the contact number from the form

        image_files = request.files.getlist('image')  # Retrieve the list of image files

        image_urls = []
        for image in image_files:
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_urls.append(image)

        item = Item(item_type, description, location, contact_number, image_urls)
        community.post_item(item)
        flash('Item posted successfully!', 'success')  # Flash a success message
        return redirect(url_for('index'))

    return render_template('post_item.html')


@app.route('/search_items', methods=['GET'])
def search_items():
    location = request.args.get('location')
    items = community.search_by_location(location)
    return render_template('search_results.html', location=location, items=items)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run()
