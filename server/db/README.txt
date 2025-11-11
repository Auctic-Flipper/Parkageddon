You will need PostgreSQL installed:

- sudo apt update && sudo apt install postgresql postgresql-contrib -y
- sudo systemctl start postgresql
- sudo systemctl enable postgresql

The pg_hba.conf file will need to be setup properly:

- sudo nano /etc/postgresql/*/main/pg_hba.conf

Scroll down until you see the below and feel free to copy it if needed:

# Database administrative login by Unix domain socket
local   all             postgres                                peer

# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             all                                     peer
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
# Optional LAN connections (replace with your trusted network ranges)
host    all             all             192.168.0.0/16          scram-sha-256
host    all             all             10.51.0.0/16            scram-sha-256
# Allow replication connections from localhost, by a user with the
# replication privilege.
local   replication     all                                     peer
host    replication     all             127.0.0.1/32            scram-sha-256
host    replication     all             192.168.0.0/16          scram-sha-256
host    replication     all             10.51.0.0/16            scram-sha-256


To verify that PostgreSQL is running:

- sudo systemctl status postgresql

To restart after making changes:

- sudo systemctl restart postgresql

Switch to the postgres user, create the database, and initialize tables:

- sudo -i -u postgres
- createdb parkageddon
- psql -U postgres -d parkageddon -f ~/Documents/Github/Parkageddon/server/db/database_init.sql

You can exit the psql prompt with:
- \q
