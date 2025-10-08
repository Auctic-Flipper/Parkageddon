- The following is for Windows users

- Ensure your .env file looks something like the following:

DATABASE_URL=postgresql+psycopg2://postgres:<Your_Password_Here>@localhost:5432/parkageddon
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=changeme

- Python 3.13 will need to be installed and added to your Path.

- You will also need to setup the virtual environment and install everything from the requirements.txt file:

In Git Bash (Make sure you are in the server directory):

source venv/bin/activate
pip install -r requirements.txt
waitress-serve --listen=127.0.0.1:8000 --call "app:create_app"

Leave waitress running in that terminal and open a new one. Navigate to wherever nginx is installed and run:

./nginx.exe

- You can now navigate to 127.0.0.1:8080 in your browser. 

