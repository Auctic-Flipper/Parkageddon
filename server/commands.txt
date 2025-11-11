In the terminal:
- mkdir -p ~/Documents/Github
- cd ~/Documents/Github
- git clone https://github.com/Auctic-Flipper/Parkageddon.git
- sudo apt update && sudo apt install python3 python3-pip -y
- cd ~/Documents/Github/Parkageddon/server
- python3 -m venv venv
- source venv/bin/activate
- pip install -r requirements.txt
- waitress-serve --listen=127.0.0.1:8000 --call "app:create_app"

In a different terminal (Make sure you've downloaded the certificates and the nginx configuration first):

- sudo apt update && sudo apt install nginx -y
- sudo cp ~/Downloads/ca.crt /usr/local/share/ca-certificates/
- sudo update-ca-certificates
- sudo mkdir -p /etc/nginx/certs
- sudo cp ~/Downloads/parkageddon.crt /etc/nginx/certs/
- sudo cp ~/Downloads/Parkageddon.key /etc/nginx/certs/
- sudo cp ~/Downloads/nginx.conf /etc/nginx/nginx.conf
- sudo chown -R root:root /etc/nginx/certs
- sudo chmod 644 /etc/nginx/certs/parkageddon.crt
- sudo chmod 600 /etc/nginx/certs/Parkageddon.key
- sudo nginx -t
- sudo systemctl start nginx

You can now open your browser and connect to https://<private_ip_here> (Browswers like Firefox have a separate certificate store. You can import ca.crt on such browsers)

You can update your firewall rules to allow inbound connections for 443/tcp and 8080/tcp if you want to host this on your network:

- sudo ufw enable
- sudo ufw default deny incoming
- sudo ufw default allow outgoing
- sudo ufw allow 443/tcp
- sudo ufw allow 8080/tcp
- sudo ufw reload
