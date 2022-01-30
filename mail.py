# file to send mails
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import yaml

def send_mail(to, body, subject):
    try:
        with open("pw.yaml", "r") as f:
            y = yaml.safe_load(f)
            FROM_MAIL = y['FROM_MAIL']
            MAIL_PASSWORD = y['MAIL_PASSWORD']
    except Exception:
        return 0

    mail_content = str(body)

    #The mail addresses and password
    #Setup the MIME
    message = MIMEMultipart()
    message['From'] = FROM_MAIL
    message['To'] = to
    message['Subject'] = subject

    #The body and the attachments for the mail
    message.attach(MIMEText(mail_content, 'plain'))

    #Create SMTP session for sending the mail
    session = smtplib.SMTP('smtp.gmail.com', 587)
    session.starttls()

    session.login(FROM_MAIL, MAIL_PASSWORD)
    text = message.as_string()
    session.sendmail(FROM_MAIL, to, text)
    session.quit()
