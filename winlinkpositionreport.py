from socket import *
import imaplib
import email
import re
import time

# APRS-IS login info
serverHost = 'rotate.aprs2.net'
serverPort = 14580
aprsUser = 'CALL'
aprsPass = 'PASS'
default_btext = 'Winlink Position Packet'  #Default if no comment is found in the email body

# create socket & connect to server
sSock = socket(AF_INET, SOCK_STREAM)
sSock.connect((serverHost, serverPort))
# logon
login_str = 'user {} pass {} vers WPR 1.0\r\n'.format(aprsUser, aprsPass)
sSock.send(login_str.encode())  # Encode the string before sending

# Function to send an APRS packet
def send_aprs_packet(callsign, lat, lon, text):
    aprs_packet = '{}>APRS:!{}/{}r{}\r\n'.format(callsign, lat, lon, text)
    sSock.send(aprs_packet.encode())

# Function to convert decimal degrees to DDMM.MM format
def decimal_to_ddmmmm(coord):
    d = int(coord)
    m = abs((coord - d) * 60)
    return d, m

# Function to format DDMM.MM coordinates
def format_ddmmmm(coord, indicator):
    formatted_coord = "{:02d}{:05.2f}".format(coord[0], coord[1])
    formatted_coord = formatted_coord.replace('-', '')
#    formatted_coord = formatted_coord.rstrip('0').rstrip('.')
    return formatted_coord + indicator

def get_email_body(email_message):
    if email_message.is_multipart():
        # If the email is multipart, extract the text content
        for part in email_message.walk():
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if payload and content_type == "text/plain":
                return payload.decode().strip()
    else:
        # If the email is plain text, return the body
        payload = email_message.get_payload(decode=True)
        if payload:
            return payload.decode().strip()
    return None

# Function to parse email subject and body
def parse_email(msg):
    subject = msg["Subject"]
    body = get_email_body(msg)

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if payload and content_type == "text/plain":
                return subject, payload.decode().strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return subject, payload.decode().strip()

    return subject, None

# Function to extract callsign from the email body using regex
def extract_callsign(body):
    match = re.search(r'@([A-Za-z0-9\-]+)', body)
    if match:
        return match.group(1)
    return None

# Function to extract comment text from the email body using regex
def extract_comment_text(body):
    match = re.search(r'@([A-Za-z0-9\-]+)\s+(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s+(.*)', body)
    if match:
        return match.group(4).strip()
    return None

# Email listener setup
email_user = 'YOUREMAIL@gmail.com'  # Replace with your Gmail address
email_pass = 'APP_PASSWORD'   # Replace with your Gmail password

while True:
    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select("inbox")

        # Search for unread emails with subject "APRS"
        status, messages = mail.search(None, '(UNSEEN SUBJECT "APRS")')

        if status == "OK":
            for num in messages[0].split():
                typ, msg_data = mail.fetch(num, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, body = parse_email(msg)

                        if body:
                            callsign = extract_callsign(body)
                            if callsign:
                                # Extract latitude and longitude from the body using regex
                                match = re.search(r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)', body)
                                if match:
                                    lat, lon = map(float, match.groups())
                                    lat_dd, lat_mm = decimal_to_ddmmmm(lat)
                                    lon_dd, lon_mm = decimal_to_ddmmmm(lon)
                                    lat_indicator = "N" if lat >= 0 else "S"
                                    lon_indicator = "E" if lon >= 0 else "W"
                                    ddmmmm_lat = format_ddmmmm((lat_dd, lat_mm), lat_indicator)
                                    ddmmmm_lon = format_ddmmmm((lon_dd, lon_mm), lon_indicator)

                                    # Extract comment text from the email body
                                    comment_text = extract_comment_text(body)
                                    btext = comment_text if comment_text else default_btext

                                    # Get the "from" email address
                                    from_address = msg["From"]

                                    # Verbose output
                                    print("Received email from:", from_address)
                                    print("Subject:", subject)
                                    print("Body:", body)
                                    print("Callsign:", callsign)
                                    print("Latitude (dd):", lat)
                                    print("Longitude (dd):", lon)
                                    print("Latitude (DDMM.MM):", ddmmmm_lat)
                                    print("Longitude (DDMM.MM):", ddmmmm_lon)
                                    print("Text:", btext)

                                    # Send the APRS packet
                                    send_aprs_packet(callsign, ddmmmm_lat, ddmmmm_lon, btext)

        # Close the email connection and wait for the next fetch
        mail.logout()
        time.sleep(0)  # Wait for 60 seconds before checking for new emails again
    except Exception as e:
        print("Error in email listener:", e)
