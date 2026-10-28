# TraefikEnjoyers

Server-based HTTPS web app for Subtask 1.1 (wild cam observation logging).

## Run

1. Generate a local self-signed certificate:
   ```bash
   openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
   ```
2. Start the HTTPS server:
   ```bash
   python app.py --host 0.0.0.0 --port 8443 --certfile cert.pem --keyfile key.pem
   ```
3. Open:
   - `https://localhost:8443` (same machine)
   - or `https://<server-ip>:8443` (remote access)

## Usage

Enter:
- animal name
- stream name
- date/time when it was visible

Click **Add observation** to append the entry to the on-screen log.
